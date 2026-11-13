import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda

from app.clients.llm_client import FakeLlmClient
from app.core.config import Settings
from app.dependencies import get_reply_graph
from app.main import create_app
from app.workflows.reply_graph import ReplyGrade, build_graph

INITIAL = {"review_text": "배달이 늦었어요", "customer_name": "손님", "rating": 1,
           "reply": "", "feedback": "", "attempts": 0, "draft_count": 0, "completed": False}


@pytest.mark.parametrize("verdicts,expected", [([True], 0), ([False, True], 1), ([False, False, False], 2)])
def test_retry_cap_and_feedback(verdicts, expected):
    drafts, reviews = [], iter(verdicts)
    async def draft(inputs):
        drafts.append(inputs)
        return "정중한 답글입니다."
    async def review(inputs):
        return ReplyGrade(passed=next(reviews), reason="핵심 불만을 언급하세요", tone="사과", needs_followup=True)
    graph = build_graph(FakeLlmClient(0), draft_chain=RunnableLambda(draft), review_chain=RunnableLambda(review))
    result = asyncio.run(graph.ainvoke(INITIAL))
    assert result["attempts"] == expected
    assert len(drafts) == expected + 1
    assert result["completed"] is True
    if expected:
        assert drafts[1]["feedback"] == "핵심 불만을 언급하세요"
        assert drafts[1]["previous_reply"] == "정중한 답글입니다."


def parse_frames(text):
    frames = []
    for frame in text.split("\n\n"):
        if not frame.strip():
            continue
        lines = frame.splitlines()
        frames.append((lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))))
    return frames


def test_sse_tokens_final_and_missing():
    with TestClient(create_app(Settings(_env_file=None, fake_llm=True, fake_llm_delay_seconds=0))) as api:
        assert api.post("/api/reviews/999/reply/stream").status_code == 404
        api.post("/api/reviews", json={"customerName": "손님", "rating": 5, "content": "감사합니다"})
        response = api.post("/api/reviews/1/reply/stream")
        assert response.status_code == 200 and "text/event-stream" in response.headers["content-type"]
        frames = parse_frames(response.text)
        tokens = [d["text"] for e, d in frames if e == "token"]
        assert len(tokens) > 5
        assert frames[-1][0] == "done"
        assert "".join(tokens) == frames[-1][1]["reply"]
        assert "FAKE_PATH_ONLY" not in "".join(tokens)  # 검토 내부 출력 제외


def test_stream_failure_is_error_event_after_200():
    class BrokenGraph:
        async def astream(self, *args, **kwargs):
            raise RuntimeError("sensitive upstream details")
            yield
    app = create_app(Settings(_env_file=None, fake_llm=True, fake_llm_delay_seconds=0))
    app.dependency_overrides[get_reply_graph] = lambda: BrokenGraph()
    with TestClient(app) as api:
        api.post("/api/reviews", json={"customerName": "손님", "rating": 1, "content": "불만"})
        response = api.post("/api/reviews/1/reply/stream")
        assert response.status_code == 200
        assert parse_frames(response.text)[-1][0] == "error"
        assert "sensitive" not in response.text and "event: done" not in response.text


def test_cancelled_stream_propagates():
    from app.services.graph_reply_service import GraphReplyService
    class Cancelled:
        async def astream(self, *args, **kwargs):
            raise asyncio.CancelledError()
            yield
    async def run():
        with pytest.raises(asyncio.CancelledError):
            async for _ in GraphReplyService(None, None, Cancelled()).stream_reply(1, INITIAL):
                pass
    asyncio.run(run())
