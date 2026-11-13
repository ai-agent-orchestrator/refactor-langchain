"""모델 생성과 연결 종료. 프롬프트와 실행은 서비스에서 담당한다."""
import logging
from threading import current_thread
from typing import Protocol
import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_openai import ChatOpenAI
from app.core.config import Settings
from app.clients.fake_chat_model import FakeReviewChatModel

logger = logging.getLogger("uvicorn.error")

class LlmClient(Protocol):
    model: str
    llm: BaseChatModel
    async def close(self) -> None: ...

class FakeLlmClient:
    model = "fake-llm"
    def __init__(self, delay_seconds: float):
        self.llm = FakeReviewChatModel(delay_seconds=delay_seconds)
        logger.info("[model:create] fake thread=%s", current_thread().name)
    async def close(self) -> None:
        pass

class OpenAiLlmClient:
    def __init__(self, settings: Settings):
        key = settings.openai_api_key
        if key is None or not key.get_secret_value().strip():
            raise ValueError("실제 호출 모드에는 OPENAI_API_KEY가 필요합니다.")
        self.model = settings.openai_model
        self._http = httpx.Client()
        self._async_http = httpx.AsyncClient()
        self.llm = ChatOpenAI(
            model=self.model, api_key=key.get_secret_value(),
            timeout=settings.openai_timeout_seconds, max_retries=0,
            max_completion_tokens=settings.openai_max_output_tokens,
            http_client=self._http, http_async_client=self._async_http,
            model_kwargs={"store": False},
        )
        logger.info("[model:create] ChatOpenAI thread=%s", current_thread().name)
    async def close(self) -> None:
        await self._async_http.aclose()
        self._http.close()
