"""FastAPI routes for the RAG backend (Phase 5)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from app.api.schemas import (
    AdminReindexResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SchemeInfo,
    SchemesResponse,
)
from app.config import get_all_schemes, get_settings
from app.rag.backend import RagBackendError, ResponseType, run_rag
from app.rag.classifier import redact_pii
from ingestion.index import (
    collection_exists,
    get_indexed_chunk_count,
    resolve_index_dir,
    validate_indexed_store,
)
from ingestion.pipeline_state import IngestLockError, is_ingesting, read_ingest_status
from ingestion.run_daily import DailyIngestError, run_daily_ingest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness plus index metadata (AP-09)."""
    settings = get_settings()
    store = str(resolve_index_dir())
    ready = collection_exists(store)
    count = get_indexed_chunk_count(store) if ready else 0
    errors = validate_indexed_store(store) if ready else ["collection missing"]
    ingested_at = settings.ingested_at or ""

    if ready and not errors:
        from ingestion.index import get_collection

        coll = get_collection(store)
        sample = coll.get(limit=1, include=["metadatas"])
        metas = sample.get("metadatas") or []
        if metas and metas[0]:
            ingested_at = metas[0].get("ingested_at") or ingested_at

    ingest_status = read_ingest_status()
    ingesting = is_ingesting()
    if ingesting:
        status = "degraded"
    else:
        status = "ok" if ready and not errors else "degraded"

    return HealthResponse(
        status=status,
        corpus_version=settings.corpus_version,
        ingested_at=ingested_at,
        index_chunk_count=count,
        index_ready=ready and not errors and not ingesting,
        ingesting=ingesting,
        last_ingest_error=ingest_status.last_error,
    )


@router.get("/schemes", response_model=SchemesResponse)
def list_schemes() -> SchemesResponse:
    """Return the five curated schemes (AP-07)."""
    schemes = [
        SchemeInfo(
            scheme_id=s.scheme_id,
            scheme_name=s.scheme_name,
            source_url=s.source_url,
        )
        for s in get_all_schemes()
    ]
    return SchemesResponse(schemes=schemes)


@router.post("/admin/reindex", response_model=AdminReindexResponse)
def admin_reindex(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> AdminReindexResponse:
    """
    Dev-only manual reindex (Phase 7.6, AP-08).

    Requires ``ADMIN_REINDEX_TOKEN`` in env and matching ``X-Admin-Token`` header.
    """
    settings = get_settings()
    if not settings.admin_reindex_allowed:
        raise HTTPException(status_code=404, detail="Admin reindex disabled")
    token = (settings.admin_reindex_token or "").strip()
    if not x_admin_token or x_admin_token.strip() != token:
        raise HTTPException(status_code=401, detail="Invalid admin token")

    if is_ingesting():
        raise HTTPException(status_code=409, detail="Ingestion already in progress")

    try:
        result = run_daily_ingest(skip_fetch=True)
    except IngestLockError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DailyIngestError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return AdminReindexResponse(
        status="ok",
        ingested_at=result.ingested_at,
        chunk_count=result.chunk_count,
        message="Reindex completed (fetch skipped; used data/raw or uploads)",
    )


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    """Run classifier → retriever → generator → validator (RAG backend)."""
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message must not be empty")

    logger.info("POST /api/chat %s", redact_pii(message)[:120])

    try:
        result = run_rag(message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RagBackendError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ChatResponse(
        answer=result.answer,
        citation_url=result.citation_url,
        footer=result.footer,
        type=result.type.value,
    )
