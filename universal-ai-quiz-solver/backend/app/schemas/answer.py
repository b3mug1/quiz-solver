from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.question import QuestionType


class Answer(BaseModel):
    question_id: str
    question_type: QuestionType
    selected_option_ids: list[str] = Field(default_factory=list)
    text_answer: str | None = None
    explanation: str = Field(max_length=8000)
    confidence: float = Field(ge=0, le=1)
    status: Literal["solved", "uncertain", "error"]
    error: str | None = None
    cached: bool = False
    input_tokens: int | None = None
    output_tokens: int | None = None


class BatchResponse(BaseModel):
    answers: list[Answer]
