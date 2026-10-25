import asyncio

from app.schemas.answer import Answer
from app.schemas.question import Question
from app.services.cache_service import AnswerCache
from app.services.gemini_service import GeminiFailure, GeminiService


class QuizSolver:
    def __init__(self, gemini: GeminiService, cache: AnswerCache):
        self.gemini = gemini
        self.cache = cache
        self.semaphore = asyncio.Semaphore(3)
        self.inflight: dict[str, asyncio.Task] = {}
        self.lock = asyncio.Lock()

    async def solve(self, question: Question) -> Answer:
        key = self.cache.key(question, self.gemini.model)
        cached = await asyncio.to_thread(self.cache.get, key, question.id)
        if cached:
            return cached
        async with self.lock:
            task = self.inflight.get(key)
            if task is None:
                task = asyncio.create_task(self._solve_new(key, question))
                self.inflight[key] = task
        try:
            answer = await asyncio.shield(task)
            return answer.model_copy(update={"question_id": question.id})
        finally:
            if task.done():
                async with self.lock:
                    if self.inflight.get(key) is task:
                        self.inflight.pop(key, None)

    async def _solve_new(self, key: str, question: Question) -> Answer:
        async with self.semaphore:
            answer = await self.gemini.solve(question)
            if answer.status == "solved":
                await asyncio.to_thread(self.cache.put, key, answer)
            return answer

    async def solve_batch(self, questions: list[Question]) -> list[Answer]:
        async def one(question: Question) -> Answer:
            try:
                return await self.solve(question)
            except GeminiFailure as exc:
                return Answer(question_id=question.id, question_type=question.question_type,
                              explanation="", confidence=0, status="error", error=str(exc))
        return await asyncio.gather(*(one(question) for question in questions))
