"""오프라인 데모 모델: 의미 품질 평가용이 아닌 비동기·스트리밍 경로 대역."""
import asyncio
import json
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field


class FakeReviewChatModel(BaseChatModel):
    delay_seconds: float = Field(default=0.0, ge=0)

    @property
    def _llm_type(self) -> str:
        return "fake-review-async"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any):
        raise RuntimeError("데모 모델도 비동기 ainvoke/astream으로 실행하세요.")

    def _text(self, messages) -> str:
        prompt = str(messages[-1].content)
        start = prompt.find("{")
        data = json.JSONDecoder().raw_decode(prompt[start:])[0] if start >= 0 else {}
        content = data.get("content", "")
        if "수정 지시:\n" in prompt:
            instruction = prompt.split("수정 지시:\n", 1)[1]
            previous = prompt.split("이전 초안:\n", 1)[1].split("\n검토 피드백:", 1)[0]
            if previous and "한 문장" in instruction:
                return previous.split(".", 1)[0] + "."
            if previous and "정중" in instruction:
                return previous.rstrip(".") + ". 소중한 말씀에 깊이 감사드립니다."
        if data.get("rating", 5) <= 2:
            return "불편을 드려 죄송합니다. 남겨주신 문제를 담당자가 확인하겠습니다."
        return "소중한 의견 감사합니다. 더 나은 서비스를 준비하겠습니다."

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs: Any):
        await asyncio.sleep(self.delay_seconds)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self._text(messages)))])

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs: Any):
        for char in self._text(messages):
            await asyncio.sleep(self.delay_seconds)
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=char))
            if run_manager:
                await run_manager.on_llm_new_token(char, chunk=chunk)
            yield chunk
