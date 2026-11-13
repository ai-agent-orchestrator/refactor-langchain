from pydantic import Field

from app.schemas.base import CamelModel


class ReviewCreateRequest(CamelModel):
    customer_name: str = Field(min_length=1, max_length=50)
    rating: int = Field(ge=1, le=5, strict=True)
    content: str = Field(min_length=1, max_length=2000)


class ReviewResponse(CamelModel):
    review_id: int
    customer_name: str
    rating: int
    content: str


class ReplyResponse(CamelModel):
    review_id: int
    reply: str
    model: str
    tone: str
    needs_followup: bool
    passed: bool = False
    attempts: int = 0


class ReplyRevisionRequest(CamelModel):
    instruction: str = Field(min_length=1, max_length=500, description="이전 답글의 말투·길이에 대한 수정 지시")
