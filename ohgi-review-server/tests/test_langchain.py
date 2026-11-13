import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_openai import ChatOpenAI

from app.core.config import Settings
from app.main import create_app


def settings(**kwargs):
    return Settings(_env_file=None, fake_llm_delay_seconds=0, **kwargs)


@pytest.mark.parametrize("status,code", [(401, "invalid_api_key"), (404, "model_not_found"), (429, "rate_limit_exceeded"), (500, "server_error")])
def test_real_chatopenai_error_becomes_502(status, code):
    """실제 ChatOpenAI와 SDK를 통과하되 HTTP 전송만 대체한다."""
    requests = []

    async def respond(request):
        requests.append(request)
        return httpx.Response(status, json={"error": {"message": "secret upstream detail", "type": code, "code": code}}, request=request)

    async def run():
        transport = httpx.MockTransport(respond)
        async with httpx.AsyncClient(transport=transport) as http:
            llm = ChatOpenAI(model="invalid-model", api_key="invalid-key", max_retries=0, http_async_client=http)
            client = SimpleNamespace(model="invalid-model", llm=llm, close=AsyncMock())
            app = create_app(settings(fake_llm=False, openai_api_key="invalid-key", rag_enabled=False))
            with patch("app.main.OpenAiLlmClient", return_value=client):
                async with app.router.lifespan_context(app):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as api:
                        await api.post("/api/reviews", json={"customerName": "손님", "rating": 1, "content": "환불 요청"})
                        result = await api.post("/api/reviews/1/reply")
                        assert result.status_code == 502
                        assert result.json()["code"] == "AI_REQUEST_FAILED"
                        assert "secret" not in result.text and "invalid-key" not in result.text
            client.close.assert_awaited_once()
        assert len(requests) == 1  # SDK 자동 재시도 비활성화
    asyncio.run(run())


def test_lifespan_builds_once_reuses_and_closes():
    from app.main import FakeLlmClient
    client = FakeLlmClient(0)
    client.close = AsyncMock()
    with patch("app.main.FakeLlmClient", return_value=client) as factory:
        app = create_app(settings())
        with TestClient(app) as api:
            chain = app.state.reply_chain
            api.post("/api/reviews", json={"customerName": "손님", "rating": 5, "content": "감사합니다"})
            for _ in range(2):
                assert api.post("/api/reviews/1/reply").status_code == 200
                assert app.state.reply_chain is chain
            factory.assert_called_once()
        client.close.assert_awaited_once()


@pytest.mark.parametrize("rating,content,tone,followup", [
    (1, "음식에서 이물질이 나왔어요", "사과", True),
    (2, "배달이 늦었어요", "사과", True),
    (5, "맛있고 친절합니다", "감사", False),
    (3, "보통입니다", "일반", False),
    (5, "맛있지만 환불 내역 확인 부탁해요", "감사", True),
])
def test_structured_reply_and_openapi(rating, content, tone, followup):
    with TestClient(create_app(settings())) as api:
        api.post("/api/reviews", json={"customerName": "손님", "rating": rating, "content": content})
        response = api.post("/api/reviews/1/reply")
        assert response.status_code == 200
        assert response.json()["tone"] == tone
        assert response.json()["needsFollowup"] is followup
        assert set(response.json()) == {"reviewId", "reply", "model", "tone", "needsFollowup", "passed", "attempts", "sources"}
        properties = api.get("/openapi.json").json()["components"]["schemas"]["ReplyResponse"]["properties"]
        assert "needsFollowup" in properties and "tone" in properties


def test_actual_structured_chain_parses_pydantic_without_network():
    from app.domain.reply import ReplyDraft
    from app.services.reply_service import build_reply_chain

    async def run():
        async def respond(request):
            body = json.loads(request.content)
            assert body["response_format"]["type"] == "json_schema"
            assert body["response_format"]["json_schema"]["strict"] is True
            assert "content" in body["messages"][-1]["content"]
            return httpx.Response(200, json={
                "id": "chat-test", "object": "chat.completion", "created": 0, "model": "test",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps({"reply": "감사합니다.", "tone": "감사", "needs_followup": False}, ensure_ascii=False)}}],
            }, request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            llm = ChatOpenAI(model="test", api_key="test", http_async_client=http, max_retries=0)
            result = await build_reply_chain(SimpleNamespace(llm=llm, model="test")).ainvoke({"review_json": json.dumps({"content": "고마워요", "rating": 5})})
            assert isinstance(result, ReplyDraft)
            assert result.tone == "감사"
    asyncio.run(run())
