"""RAG pipeline: classifier, retriever, generator (Phases 3–5)."""

from app.rag.classifier import (
    ClassifierResult,
    QueryClass,
    build_refusal,
    classify_query,
    contains_pii,
    redact_pii,
)
from app.rag.backend import RagBackendResponse, ResponseType, run_rag
from app.rag.generator import generate_answer
from app.rag.retriever import (
    NOT_FOUND_MESSAGE,
    RetrievalResult,
    build_context,
    retrieve,
)
from app.rag.validator import validate_and_fix

__all__ = [
    "ClassifierResult",
    "NOT_FOUND_MESSAGE",
    "QueryClass",
    "RagBackendResponse",
    "ResponseType",
    "RetrievalResult",
    "build_context",
    "build_refusal",
    "classify_query",
    "contains_pii",
    "generate_answer",
    "redact_pii",
    "retrieve",
    "run_rag",
    "validate_and_fix",
]
