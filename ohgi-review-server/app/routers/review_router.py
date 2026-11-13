import logging
from threading import current_thread

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.dependencies import ReplyServiceDep, ReviewServiceDep
from app.schemas.review import ReplyResponse, ReplyRevisionRequest, ReviewCreateRequest, ReviewResponse

router = APIRouter(prefix="/api/reviews", tags=["리뷰"])
logger = logging.getLogger("uvicorn.error")


@router.post("", response_model=ReviewResponse, status_code=201)
def register_review(body: ReviewCreateRequest, service: ReviewServiceDep) -> ReviewResponse:
    logger.info("[register] thread=%s", current_thread().name)
    return service.register(body)


@router.get("/{review_id}", response_model=ReviewResponse)
def find_review(review_id: int, service: ReviewServiceDep) -> ReviewResponse:
    logger.info("[find] thread=%s reviewId=%s", current_thread().name, review_id)
    return service.find(review_id)


@router.post("/{review_id}/reply", response_model=ReplyResponse)
async def create_reply(review_id: int, service: ReplyServiceDep) -> ReplyResponse:
    logger.info("[reply] thread=%s reviewId=%s", current_thread().name, review_id)
    return await service.create_reply(review_id)


@router.post("/{review_id}/reply/stream", response_class=StreamingResponse,
             responses={200: {"content": {"text/event-stream": {}}, "description": "draft_start/token/review/done/error 이벤트"}})
async def stream_reply(review_id: int, service: ReplyServiceDep):
    logger.info("[stream] thread=%s reviewId=%s", current_thread().name, review_id)
    inputs = await service.prepare(review_id)  # 헤더 전 없는 리뷰는 기존 404로 처리
    return StreamingResponse(service.stream_reply(review_id, inputs), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{review_id}/reply/revise", response_model=ReplyResponse)
async def revise_reply(review_id: int, body: ReplyRevisionRequest, service: ReplyServiceDep):
    logger.info("[revise] thread=%s reviewId=%s", current_thread().name, review_id)
    return await service.revise_reply(review_id, body.instruction)
