from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

QuestionType = Literal[
    "single_choice", "multiple_choice", "true_false", "fill_blank",
    "short_answer", "matching", "ordering", "math", "programming", "image",
]


class Option(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=4000)


class Question(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=2, max_length=12000)
    question_type: QuestionType
    options: list[Option] = Field(default_factory=list, max_length=100)
    image_data: str | None = Field(default=None, max_length=3_000_000)
    image_mime_type: Literal["image/png", "image/jpeg", "image/webp"] | None = None
    source_url: HttpUrl | None = None
    extraction_confidence: float = Field(default=1.0, ge=0, le=1)

    @model_validator(mode="after")
    def validate_question(self):
        ids = [option.id for option in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError("option identifiers must be unique")
        if self.question_type in ("single_choice", "multiple_choice", "true_false") and len(ids) < 2:
            raise ValueError("choice questions need at least two options")
        if bool(self.image_data) != bool(self.image_mime_type):
            raise ValueError("image data and MIME type must be supplied together")
        return self


class BatchRequest(BaseModel):
    questions: list[Question] = Field(min_length=1, max_length=20)
