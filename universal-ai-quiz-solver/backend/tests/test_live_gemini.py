"""Optional smoke test: run only when GEMINI_API_KEY is configured."""

import asyncio
import os

import pytest

from app.schemas.question import Question
from app.services.gemini_service import GeminiService


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not configured")
def test_live_gemini():
    question = Question(id="live-smoke", text="What is 2 + 2?", question_type="single_choice",
                        options=[{"id": "A", "text": "3"}, {"id": "B", "text": "4"}])
    service = GeminiService(os.environ["GEMINI_API_KEY"], os.getenv("GEMINI_MODEL", "gemini-3.6-flash"))
    answer = asyncio.run(service.solve(question))
    assert answer.selected_option_ids == ["B"]
