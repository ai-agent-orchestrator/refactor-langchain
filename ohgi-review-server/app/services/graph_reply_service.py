"""일반 응답과 SSE에서 같은 비동기 그래프를 실행한다."""
import asyncio
import json
import logging

from anyio import to_thread
from langchain_core.exceptions import OutputParserException
from openai import OpenAIError
from pydantic import ValidationError

from app.core.exceptions import AiRequestError
from app.schemas.review import ReplyResponse

logger = logging.getLogger("uvicorn.error")
UPSTREAM_ERRORS = (OpenAIError, OutputParserException, ValidationError)


def sse(event: str, data: dict) -> str:
    # JSON으로 직렬화하여 본문의 줄바꿈이 SSE 프레임을 깨지 않게 한다.
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class GraphReplyService:
    def __init__(self, repository, client, graph):
        self.repository, self.client, self.graph = repository, client, graph

    async def prepare(self, review_id: int) -> dict:
        review = await to_thread.run_sync(self.repository.find_by_id, review_id)
        return {"customer_name": review.customer_name, "rating": review.rating, "review_text": review.content,
                "reply": "", "feedback": "", "attempts": 0, "draft_count": 0, "completed": False}

    def config(self, review_id: int) -> dict:
        return {"recursion_limit": 20}

    def response(self, review_id: int, state: dict) -> ReplyResponse:
        return ReplyResponse(review_id=review_id, model=self.client.model, reply=state["reply"],
                             tone=state["tone"], needs_followup=state["needs_followup"],
                             passed=state["passed"], attempts=state["attempts"], sources=state.get("sources", []))

    async def create_reply(self, review_id: int) -> ReplyResponse:
        inputs = await self.prepare(review_id)
        try:
            result = await self.graph.ainvoke(inputs, config=self.config(review_id))
        except UPSTREAM_ERRORS as exc:
            raise AiRequestError("OpenAI 호출 또는 응답 검증에 실패했습니다.") from exc
        return self.response(review_id, result)

    async def stream_reply(self, review_id: int, inputs: dict):
        state = dict(inputs)
        last_step = None
        attempt = -1
        try:
            # messages는 실시간 토큰, updates는 최종 상태/재작성 결과를 얻는다.
            async for mode, data in self.graph.astream(inputs, config=self.config(review_id), stream_mode=["messages", "updates"]):
                # 수업 11 §5-2/§6: 다중 모드 + async streaming. model 필터를 draft로 변경.
                if mode == "messages":
                    chunk, metadata = data
                    if metadata.get("langgraph_node") != "draft":
                        continue
                    step = metadata.get("langgraph_step")
                    if step != last_step:
                        last_step = step
                        attempt += 1
                        yield sse("draft_start", {"attempts": attempt, "provisional": True})
                    text = chunk.content if isinstance(chunk.content, str) else "".join(
                        block.get("text", "") for block in chunk.content if isinstance(block, dict) and block.get("type") == "text")
                    if text:
                        yield sse("token", {"text": text, "attempts": attempt})
                elif mode == "updates":
                    for node, update in data.items():
                        if isinstance(update, dict):
                            state.update(update)
                            if node == "review":
                                yield sse("review", {"passed": state["passed"], "attempts": state["attempts"]})
            yield sse("done", self.response(review_id, state).model_dump(by_alias=True))
        except asyncio.CancelledError:
            raise  # 연결 취소를 삼키지 않아 그래프 실행도 취소한다.
        except Exception as exc:
            logger.warning("[stream:error] type=%s", type(exc).__name__)
            yield sse("error", {"code": "AI_REQUEST_FAILED", "detail": "답글 스트리밍에 실패했습니다. 다시 요청해 주세요."})
