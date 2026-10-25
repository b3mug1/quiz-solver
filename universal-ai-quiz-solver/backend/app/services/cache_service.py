import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager

from app.schemas.answer import Answer
from app.schemas.question import Question


class AnswerCache:
    def __init__(self, database_url: str, ttl: int):
        self.ttl = ttl
        if database_url.startswith("sqlite:///"):
            self.kind = "sqlite"
            self.path = database_url.removeprefix("sqlite:///")
        elif database_url.startswith(("postgresql://", "postgres://")):
            self.kind = "postgres"
            self.path = database_url
        else:
            raise ValueError("DATABASE_URL must be sqlite:/// or postgresql://")
        with self.connection() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS answer_cache (key TEXT PRIMARY KEY, payload TEXT NOT NULL, expires_at DOUBLE PRECISION NOT NULL)")

    @contextmanager
    def connection(self):
        if self.kind == "sqlite":
            connection = sqlite3.connect(self.path)
        else:
            import psycopg
            connection = psycopg.connect(self.path)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def key(question: Question, model: str) -> str:
        data = question.model_dump(exclude={"id", "source_url", "extraction_confidence"})
        raw = json.dumps([model, data], sort_keys=True).encode()
        return hashlib.sha256(raw).hexdigest()

    def get(self, key: str, question_id: str) -> Answer | None:
        with self.connection() as connection:
            connection.execute("DELETE FROM answer_cache WHERE expires_at <= %s" if self.kind == "postgres" else "DELETE FROM answer_cache WHERE expires_at <= ?", (time.time(),))
            query = "SELECT payload, expires_at FROM answer_cache WHERE key = %s" if self.kind == "postgres" else "SELECT payload, expires_at FROM answer_cache WHERE key = ?"
            row = connection.execute(query, (key,)).fetchone()
            if not row or row[1] <= time.time():
                return None
            answer = Answer.model_validate_json(row[0])
            return answer.model_copy(update={"question_id": question_id, "cached": True})

    def put(self, key: str, answer: Answer) -> None:
        with self.connection() as connection:
            if self.kind == "postgres":
                connection.execute("INSERT INTO answer_cache (key,payload,expires_at) VALUES (%s,%s,%s) ON CONFLICT (key) DO UPDATE SET payload=EXCLUDED.payload, expires_at=EXCLUDED.expires_at", (key, answer.model_dump_json(), time.time() + self.ttl))
            else:
                connection.execute("INSERT OR REPLACE INTO answer_cache (key,payload,expires_at) VALUES (?,?,?)", (key, answer.model_dump_json(), time.time() + self.ttl))
