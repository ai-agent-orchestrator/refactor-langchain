import asyncio
import json
from unittest.mock import patch

import httpx

from app.core.config import Settings
from app.rag.policy_index import DemoPolicyEmbeddings, OpenAIEmbeddings, build_policy_index


def test_persistent_chroma_reopens_without_reembedding_documents(tmp_path):
    """실제 디스크 DB와 실제 OpenAI 어댑터. HTTP 전송만 로컬 대역이다."""
    requests = []
    async def respond(request):
        body = json.loads(request.content)
        requests.append(body["input"])
        values = body["input"]
        encoder = DemoPolicyEmbeddings()
        return httpx.Response(200, request=request, json={"object": "list", "model": body["model"],
            "data": [{"object": "embedding", "index": i, "embedding": encoder.embed_query(value)} for i, value in enumerate(values)],
            "usage": {"prompt_tokens": 1, "total_tokens": 1}})

    async def run():
        settings = Settings(_env_file=None, fake_llm=False, openai_api_key="stub-key", chroma_path=tmp_path / "chroma")
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            def factory(**kwargs):
                return OpenAIEmbeddings(**{**kwargs, "http_async_client": http})
            with patch("app.rag.policy_index.OpenAIEmbeddings", side_effect=factory):
                index = await build_policy_index(settings)
                try:
                    name = index.collection_name
                    assert any("03페이지" in d.metadata["section"] for d in await index.retriever().ainvoke("환불"))
                finally:
                    await index.close()
                after_first = len(requests)
                reopened = await build_policy_index(settings)
                try:
                    assert reopened.collection_name == name
                    assert len(requests) == after_first  # 시작 시 문서 재임베딩 없음
                    assert await reopened.retriever().ainvoke("환불")
                    assert len(requests) == after_first + 1  # 질문만 임베딩
                finally:
                    await reopened.close()
    asyncio.run(run())
