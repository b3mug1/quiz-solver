import asyncio
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.main import create_app
from app.schemas.answer import Answer
from app.schemas.question import Question
from app.services.answer_validator import validate_answer
from app.services.cache_service import AnswerCache
from app.services.gemini_service import GeminiFailure, ModelAnswer
from app.services.html_parser import parse_questions
from app.services.quiz_solver import QuizSolver

QUESTION = {"id": "q1", "text": "What is two plus two?", "question_type": "single_choice",
            "options": [{"id": "A", "text": "3"}, {"id": "B", "text": "4"}]}


class Client:
    def __init__(self, app):
        self.app = app

    def request(self, method, path, **kwargs):
        async def send():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test") as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(send())

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)


class FakeGemini:
    model = "fake-model"

    def __init__(self):
        self.calls = 0
        self.fail = False

    async def solve(self, question):
        self.calls += 1
        if self.fail:
            raise GeminiFailure("Mock network failure", 503)
        return Answer(question_id=question.id, question_type=question.question_type,
                      selected_option_ids=["B"], explanation="2 + 2 = 4", confidence=0.9, status="solved")


@pytest.fixture
def setup(tmp_path):
    fake = FakeGemini()
    db = tmp_path / "cache.db"
    cache = AnswerCache(f"sqlite:///{db.as_posix()}", 3600)
    settings = Settings(api_auth_secret="test-token", database_url=f"sqlite:///{db.as_posix()}",
                        rate_limit_per_minute=20, allowed_origins="chrome-extension://abc")
    app = create_app(settings, QuizSolver(fake, cache))
    return Client(app), fake, cache


def headers():
    return {"Authorization": "Bearer test-token"}


def test_health_and_auth(setup):
    client, _, _ = setup
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/status").status_code == 401
    assert client.get("/api/v1/models", headers=headers()).json()["configured_model"]


def test_single_and_cache(setup):
    client, fake, _ = setup
    first = client.post("/api/v1/solve", headers=headers(), json=QUESTION)
    second = client.post("/api/v1/solve", headers=headers(), json={**QUESTION, "id": "q2"})
    assert first.status_code == 200
    assert first.json()["selected_option_ids"] == ["B"]
    assert second.json()["cached"] is True
    assert second.json()["question_id"] == "q2"
    assert fake.calls == 1


def test_batch_and_network_error(setup):
    client, fake, _ = setup
    fake.fail = True
    result = client.post("/api/v1/solve/batch", headers=headers(), json={"questions": [QUESTION]})
    assert result.status_code == 200
    assert result.json()["answers"][0]["status"] == "error"
    single = client.post("/api/v1/solve", headers=headers(), json=QUESTION)
    assert single.status_code == 503


def test_validation_and_answer_checks(setup):
    client, _, _ = setup
    bad = {**QUESTION, "options": [{"id": "A", "text": "same"}, {"id": "A", "text": "duplicate"}]}
    assert client.post("/api/v1/solve", headers=headers(), json=bad).status_code == 422
    question = Question.model_validate(QUESTION)
    answer = Answer(question_id="q1", question_type="single_choice", selected_option_ids=["Z"],
                    explanation="bad", confidence=0.9, status="solved")
    with pytest.raises(ValueError):
        validate_answer(question, answer)
    with pytest.raises(ValueError):
        ModelAnswer.model_validate({"question_id": "q1", "question_type": "single_choice",
                                    "selected_option_ids": ["B"], "text_answer": None,
                                    "explanation": "", "confidence": 0.9, "status": "certain"})


def test_rate_limit(tmp_path):
    settings = Settings(api_auth_secret="test-token", database_url=f"sqlite:///{(tmp_path / 'rate.db').as_posix()}", rate_limit_per_minute=1)
    client = Client(create_app(settings, QuizSolver(FakeGemini(), AnswerCache(settings.database_url, 10))))
    assert client.get("/api/v1/models", headers=headers()).status_code == 200
    assert client.get("/api/v1/models", headers=headers()).status_code == 429


def test_example_token_is_rejected(tmp_path):
    settings = Settings(api_auth_secret="replace-with-a-long-random-personal-token",
                        database_url=f"sqlite:///{(tmp_path / 'placeholder.db').as_posix()}")
    client = Client(create_app(settings, QuizSolver(FakeGemini(), AnswerCache(settings.database_url, 10))))
    response = client.get("/api/v1/status", headers={"Authorization": f"Bearer {settings.api_auth_secret}"})
    assert response.status_code == 503


def test_html_fixture():
    html = (Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "standard.html").read_text(encoding="utf-8")
    parsed = parse_questions(html)
    assert len(parsed) == 2
    assert parsed[0]["options"][1]["text"] == "4"
