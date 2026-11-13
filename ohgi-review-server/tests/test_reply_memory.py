import asyncio

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.runnables import RunnableLambda

from app.clients.llm_client import FakeLlmClient
from app.core.config import Settings
from app.main import create_app
from app.workflows.reply_graph import ReplyGrade, build_graph


def config():
    return Settings(_env_file=None, fake_llm=True, fake_llm_delay_seconds=0)


def test_revision_previous_context_isolated_and_reset():
    app = create_app(config())
    with TestClient(app) as api:
        for rating in (1, 5):
            api.post("/api/reviews", json={"customerName": "손님", "rating": rating, "content": "배달 문제" if rating == 1 else "맛있어요"})
        assert api.post("/api/reviews/1/reply/revise", json={"instruction": "한 문장으로 줄여 줘"}).status_code == 409
        original = api.post("/api/reviews/1/reply").json()
        other = api.post("/api/reviews/2/reply").json()
        revised = api.post("/api/reviews/1/reply/revise", json={"instruction": "한 문장으로 줄여 줘"})
        assert revised.status_code == 200
        assert revised.json()["reply"] == original["reply"].split(".", 1)[0] + "."
        assert "죄송" in revised.json()["reply"]
        assert revised.json()["attempts"] == 0
        state = asyncio.run(app.state.reply_graph.aget_state({"configurable": {"thread_id": "2"}}))
        assert state.values["reply"] == other["reply"]
        assert api.post("/api/reviews/1/reply/revise", json={"instruction": "  "}).status_code == 422
        assert api.post("/api/reviews/999/reply/revise", json={"instruction": "짧게"}).status_code == 404
    with TestClient(app) as restarted:
        restarted.post("/api/reviews", json={"customerName": "새 손님", "rating": 5, "content": "칭찬"})
        assert restarted.post("/api/reviews/1/reply/revise", json={"instruction": "한 문장으로"}).status_code == 409


def test_graph_restores_original_review_and_latest_reply():
    seen = []
    async def draft(value):
        seen.append(value)
        return "첫 초안" if not value["previous_reply"] else "수정된 초안"
    async def grade(value):
        return ReplyGrade(passed=True, reason="OK", tone="감사", needs_followup=False)
    async def run():
        graph = build_graph(FakeLlmClient(0), draft_chain=RunnableLambda(draft), review_chain=RunnableLambda(grade), checkpointer=InMemorySaver())
        cfg = {"configurable": {"thread_id": "review-a"}}
        await graph.ainvoke({"review_text": "원래 리뷰 내용", "customer_name": "손님", "rating": 5, "draft_count": 0}, cfg)
        await graph.ainvoke({"revision_instruction": "짧게", "draft_count": 0, "feedback": ""}, cfg)
        assert seen[-1]["previous_reply"] == "첫 초안"
        assert "원래 리뷰 내용" in seen[-1]["review_json"]
        assert seen[-1]["revision_instruction"] == "짧게"
    asyncio.run(run())
