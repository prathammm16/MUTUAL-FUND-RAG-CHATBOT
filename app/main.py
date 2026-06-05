"""
FastAPI application entrypoint (Phase 5 RAG backend).

Run: ``uvicorn app.main:app --reload``
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.config import get_settings
from app.middleware.rate_limit import get_chat_rate_limiter
from ingestion.embed import warmup_embedding_model

_UI_DIR = Path(__file__).resolve().parents[1] / "ui"

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings()
    if not settings.groq_api_key:
        logging.warning(
            "GROQ_API_KEY not set — factual answers use template generation."
        )
    if settings.effective_chat_rate_limit_per_minute > 0:
        logging.info(
            "Chat rate limit: %s requests/minute per client",
            settings.effective_chat_rate_limit_per_minute,
        )
    if settings.preload_embedding_model:
        logging.info(
            "Preloading embedding model (backend=%s)",
            settings.resolved_embedding_backend(),
        )
        warmup_embedding_model()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Groww Chatbot",
        description="Facts-only RAG chatbot for five HDFC mutual fund scheme pages on Groww.",
        version="0.9.0",
        lifespan=_lifespan,
    )

    cors_regex = settings.resolved_cors_origin_regex()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[] if cors_regex else settings.resolved_cors_origins(),
        allow_origin_regex=cors_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    limit = settings.effective_chat_rate_limit_per_minute
    if limit > 0:
        limiter = get_chat_rate_limiter(limit)

        @app.middleware("http")
        async def chat_rate_limit_middleware(request: Request, call_next):
            if request.method == "POST" and request.url.path == "/api/chat":
                client = request.client.host if request.client else "unknown"
                forwarded = request.headers.get("X-Forwarded-For")
                client_key = forwarded.split(",")[0].strip() if forwarded else client
                if not limiter.is_allowed(client_key):
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Rate limit exceeded. Try again later."},
                    )
            return await call_next(request)

    app.include_router(api_router)
    if settings.serve_ui and _UI_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(_UI_DIR), html=True), name="ui")
    return app


app = create_app()
