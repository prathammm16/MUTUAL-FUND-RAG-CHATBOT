"""Pydantic models for the RAG API (Phase 5)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)


class ChatResponse(BaseModel):
    answer: str
    citation_url: str
    footer: str
    type: str


class SchemeInfo(BaseModel):
    scheme_id: str
    scheme_name: str
    source_url: str


class SchemesResponse(BaseModel):
    schemes: list[SchemeInfo]


class HealthResponse(BaseModel):
    status: str
    corpus_version: int
    ingested_at: str
    index_chunk_count: int
    index_ready: bool
    ingesting: bool = False
    last_ingest_error: str = ""


class AdminReindexResponse(BaseModel):
    status: str
    ingested_at: str
    chunk_count: int
    message: str = ""
