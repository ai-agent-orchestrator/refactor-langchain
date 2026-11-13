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
            app = create_app(settings(fake_llm=False, openai_api_key="invalid-key"))
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
