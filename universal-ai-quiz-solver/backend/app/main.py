import hmac
import logging
import time
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings
from app.schemas.answer import Answer, BatchResponse
from app.schemas.question import BatchRequest, Question
from app.services.cache_service import AnswerCache
from app.services.gemini_service import GeminiFailure, GeminiService
from app.services.quiz_solver import QuizSolver

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, solver: QuizSolver | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Universal AI Quiz Solver", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_methods=["GET", "POST"],
                       allow_headers=["Authorization", "Content-Type"])
    app.state.settings = settings
    app.state.solver = solver or QuizSolver(
        GeminiService(settings.gemini_api_key, settings.gemini_model),
        AnswerCache(settings.database_url, settings.cache_ttl_seconds),
    )
    visits: dict[str, deque] = defaultdict(deque)

    @app.middleware("http")
    async def size_limit(request: Request, call_next):
        if request.method == "POST":
            length = request.headers.get("content-length")
            if length and int(length) > 4_000_000:
                return JSONResponse(status_code=413, content={"error": "request_too_large", "detail": "Request exceeds 4 MB"})
            body = await request.body()
            if len(body) > 4_000_000:
                return JSONResponse(status_code=413, content={"error": "request_too_large", "detail": "Request exceeds 4 MB"})
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": "invalid_request", "detail": "Request validation failed"})

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": "http_error", "detail": exc.detail})

    @app.exception_handler(GeminiFailure)
    async def gemini_error(_request: Request, exc: GeminiFailure):
        return JSONResponse(status_code=exc.status_code, content={"error": "solver_error", "detail": str(exc)})

    async def authorize(authorization: str | None = Header(default=None)):
        if not settings.api_auth_secret or settings.api_auth_secret == "replace-with-a-long-random-personal-token":
            raise HTTPException(status_code=503, detail="Backend authentication is not configured")
        expected = "Bearer " + settings.api_auth_secret
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Invalid API token")
        bucket = visits["service"]
        now = time.monotonic()
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_per_minute:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        bucket.append(now)

    @app.get("/")
    async def root():
        return {"name": "Universal AI Quiz Solver API", "status": "ok", "docs": "/docs"}

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/status", dependencies=[Depends(authorize)])
    async def status():
        return {"status": "ready" if settings.gemini_api_key else "unconfigured",
                "model": settings.gemini_model}

    @app.get("/api/v1/models", dependencies=[Depends(authorize)])
    async def models():
        return {"configured_model": settings.gemini_model}

    @app.post("/api/v1/solve", response_model=Answer, dependencies=[Depends(authorize)])
    async def solve(question: Question):
        return await app.state.solver.solve(question)

    @app.post("/api/v1/solve/batch", response_model=BatchResponse, dependencies=[Depends(authorize)])
    async def solve_batch(batch: BatchRequest):
        if len(batch.questions) > settings.max_batch_size:
            raise HTTPException(status_code=422, detail="Batch too large")
        return BatchResponse(answers=await app.state.solver.solve_batch(batch.questions))

    return app


app = create_app()
