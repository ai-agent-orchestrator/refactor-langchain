import asyncio
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from langchain_openai import OpenAIEmbeddings

from app.clients.llm_client import FakeLlmClient
from app.core.config import Settings
from app.core.exceptions import AiRequestError
from app.main import create_app
from app.rag.policy_index import DemoPolicyEmbeddings, PolicyRetriever, build_policy_index, split_policy
from app.workflows.reply_graph import ReplyGrade, SAFE_POLICY_REPLY, build_graph, has_unsupported_promise

POLICY = Path(__file__).resolve().parents[1] / "policies" / "store_policy.md"
INITIAL = {"review_text": "배달 문제 때문에 환불을 요청합니다", "customer_name": "손님", "rating": 1,
           "reply": "", "feedback": "", "attempts": 0, "draft_count": 0, "completed": False}


def test_policy_split_has_twelve_sections_and_source_metadata():
    text, docs = split_policy(POLICY)
    assert text.count("## ") == 12
    assert len({d.metadata["section"] for d in docs if "페이지" in d.metadata["section"]}) == 12
    assert all(d.metadata["source"] == "store_policy.md" for d in docs)
    assert len({d.metadata["chunk_id"] for d in docs}) == len(docs)
    assert all(len(d.page_content) <= 700 for d in docs)


def test_real_chroma_ingestion_retrieval_and_cleanup():
    async def run():
        index = await build_policy_index(Settings(_env_file=None, fake_llm=True))
        try:
            docs = await index.retriever(4).ainvoke("환불 요청을 확인해주세요")
            assert docs
            assert any("03페이지" in d.metadata["section"] for d in docs)
            assert all(d.metadata["policy_version"] for d in docs)
            assert index.client.get_collection(index.collection_name).count() >= 12
        finally:
            # 실제 삭제를 실행하며 호출도 계측한다. 종료된 Rust 연결을 다시 사용하지 않는다.
            delete = index.store.delete_collection
            with patch.object(type(index.store), "delete_collection", side_effect=delete) as cleanup:
                await index.close()
                cleanup.assert_called_once()
    asyncio.run(run())


def test_rag_api_sources_revision_and_stream():
    app = create_app(Settings(_env_file=None, fake_llm=True, fake_llm_delay_seconds=0))
    with TestClient(app) as api:
        api.post("/api/reviews", json={"customerName": "손님", "rating": 1, "content": INITIAL["review_text"]})
        result = api.post("/api/reviews/1/reply")
        assert result.status_code == 200
        body = result.json()
        assert body["sources"] and any("03페이지" in s["section"] for s in body["sources"])
        assert "확인" in body["reply"] and not has_unsupported_promise(body["reply"])
        assert all(set(s) == {"source", "section", "chunkId", "policyVersion"} for s in body["sources"])
        revised = api.post("/api/reviews/1/reply/revise", json={"instruction": "한 문장으로 줄여 줘"})
        assert revised.status_code == 200 and revised.json()["sources"]
        assert revised.json()["reply"] == body["reply"].split(".", 1)[0] + "."
        streamed = api.post("/api/reviews/1/reply/stream")
        assert streamed.status_code == 200 and "event: done" in streamed.text
        assert "policyVersion" in streamed.text


@pytest.mark.parametrize("empty", [False, True])
def test_no_evidence_or_invented_compensation_fails_closed_with_bounded_rewrites(empty):
    calls = []
    async def retrieve(query):
        return [] if empty else [Document(page_content="환불은 담당자가 확인 후 안내한다. 자동 보상은 없다.", metadata={
            "source": "store_policy.md", "section": "환불", "chunk_id": "policy-a", "policy_version": "test-v1"})]
    async def draft(inputs):
        calls.append(inputs)
        return "전액 환불해 드리고 쿠폰을 제공하겠습니다."
    async def review(inputs):
        # 심판 모델이 잘못 승인하더라도 규칙이 대표적인 확약을 차단한다.
        return ReplyGrade(passed=True, reason="FAKE_APPROVAL", tone="사과", needs_followup=True)
    graph = build_graph(FakeLlmClient(0), draft_chain=RunnableLambda(draft), review_chain=RunnableLambda(review), policy_retriever=RunnableLambda(retrieve))
    result = asyncio.run(graph.ainvoke(INITIAL))
    assert result["attempts"] == 2 and result["passed"] is False
    assert result["reply"] == SAFE_POLICY_REPLY
    assert len(calls) == (0 if empty else 3)
    if calls:
        assert "자동 보상은 없다" in calls[0]["policy_context"]


def test_retriever_uses_native_async_embedding_and_moves_chroma_off_event_loop():
    class AsyncEmbeddings(DemoPolicyEmbeddings):
        def embed_query(self, text):
            raise AssertionError("동기 원격 임베딩을 호출하면 안 됩니다")
        async def aembed_query(self, text):
            await asyncio.sleep(0)
            return [0.0, 1.0]
    # 타입 검증은 실제 저장소로 통과한 후 검색 메서드 경계만 계측한다.
    async def run():
        index = await build_policy_index(Settings(_env_file=None, fake_llm=True))
        try:
            retriever = PolicyRetriever(store=index.store, embeddings=AsyncEmbeddings())
            loop_thread = threading.get_ident()
            def search(*args, **kwargs):
                assert threading.get_ident() != loop_thread
                return []
            with patch.object(type(index.store), "similarity_search_by_vector", side_effect=search):
                assert await retriever.ainvoke("환불") == []
        finally:
            await index.close()
    asyncio.run(run())


def test_query_embedding_failure_becomes_existing_502():
    app = create_app(Settings(_env_file=None, fake_llm=True, fake_llm_delay_seconds=0))
    with TestClient(app) as api:
        api.post("/api/reviews", json={"customerName": "손님", "rating": 1, "content": "환불 문의"})
        async def broken(_):
            raise RuntimeError("private embedding failure")
        with patch.object(DemoPolicyEmbeddings, "aembed_query", side_effect=broken):
            response = api.post("/api/reviews/1/reply")
            assert response.status_code == 502
            assert response.json()["code"] == "AI_REQUEST_FAILED"
            assert "private" not in response.text
            stream = api.post("/api/reviews/1/reply/stream")
            assert stream.status_code == 200 and "event: error" in stream.text
            assert "event: done" not in stream.text and "private" not in stream.text


def test_actual_openai_async_embedding_adapter_with_http_transport_stub():
    seen = []
    async def respond(request):
        body = json.loads(request.content)
        seen.append(body)
        assert body["model"] == "text-embedding-3-small"
        items = body["input"]
        return httpx.Response(200, request=request, json={"object": "list", "model": body["model"],
            "data": [{"object": "embedding", "index": i, "embedding": [0.5, 0.5]} for i in range(len(items))],
            "usage": {"prompt_tokens": 1, "total_tokens": 1}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key="stub-key", http_async_client=http,
                                         check_embedding_ctx_length=False, max_retries=0)
            assert await embeddings.aembed_query("환불") == [0.5, 0.5]
            assert await embeddings.aembed_documents(["규정A", "규정B"]) == [[0.5, 0.5], [0.5, 0.5]]
        assert len(seen) == 2
    asyncio.run(run())
