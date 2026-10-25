"""Vercel's FastAPI entrypoint; deploy the backend directory as project root."""

import os

# Vercel's code bundle is read-only; /tmp is writable but the cache is ephemeral.
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/quiz_cache.db")

from app.main import app  # noqa: E402

__all__ = ["app"]
