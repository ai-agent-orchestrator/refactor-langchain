"""LLM 출력 계약. HTTP 응답의 camelCase 변환과는 별개다."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ReplyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    reply: str = Field(min_length=1, description="사장님이 확인할 정중한 한국어 답글 초안")
    tone: Literal["사과", "감사", "일반"] = Field(description="불만은 사과, 칭찬은 감사, 나머지는 일반")
    needs_followup: bool = Field(description="환불·이물질·지연·불만처럼 직접 확인할 후속 조치가 필요한가")
