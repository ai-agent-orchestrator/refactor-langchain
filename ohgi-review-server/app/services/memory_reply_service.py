"""같은 리뷰의 실행을 직렬화하고 체크포인트의 이전 초안을 수정한다."""
from anyio import to_thread
from fastapi import HTTPException

from app.core.exceptions import AiRequestError
from app.services.graph_reply_service import GraphReplyService, UPSTREAM_ERRORS


class MemoryReplyService(GraphReplyService):
    def __init__(self, repository, client, graph, locks):
        super().__init__(repository, client, graph)
        self.locks = locks

    def config(self, review_id: int) -> dict:
        return {"configurable": {"thread_id": str(review_id)}, "recursion_limit": 20}

    async def prepare(self, review_id: int) -> dict:
        return {**await super().prepare(review_id), "revision_instruction": ""}

    async def create_reply(self, review_id: int):
        async with self.locks[review_id]:
            return await super().create_reply(review_id)

    async def stream_reply(self, review_id: int, inputs: dict):
        # 같은 리뷰의 단건/스트리밍/수정을 겹쳐 체크포인트가 섞이지 않게 한다.
        async with self.locks[review_id]:
            async for frame in super().stream_reply(review_id, inputs):
                yield frame

    async def revise_reply(self, review_id: int, instruction: str):
        await to_thread.run_sync(self.repository.find_by_id, review_id)
        async with self.locks[review_id]:
            snapshot = await self.graph.aget_state(self.config(review_id))
            if not snapshot.values.get("completed") or not snapshot.values.get("reply") or snapshot.next:
                raise HTTPException(status_code=409, detail="먼저 답글 초안을 완성한 뒤 수정해 주세요.")
            try:
                # 원본 리뷰·이전 답글은 전달하지 않는다. saver가 thread의 상태를 복원한다.
                result = await self.graph.ainvoke({
                    "revision_instruction": instruction, "feedback": "", "attempts": 0,
                    "draft_count": 0, "completed": False,
                }, config=self.config(review_id))
            except UPSTREAM_ERRORS as exc:
                raise AiRequestError("OpenAI 호출 또는 응답 검증에 실패했습니다.") from exc
            return self.response(review_id, result)
