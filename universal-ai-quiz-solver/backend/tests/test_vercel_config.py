from app.config import Settings


def test_vercel_uses_writable_tmp_by_default(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url == "sqlite:////tmp/quiz_cache.db"
