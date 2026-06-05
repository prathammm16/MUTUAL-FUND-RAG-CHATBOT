"""
RAG backend orchestrator (Phase 5).

Single entry point: classify → retrieve → generate → validate.
Used by FastAPI routes and tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from app.rag.classifier import ClassifierResult, classify_query, redact_pii
from app.rag.generator import GenerationError, generate_answer, template_generate
from app.rag.retriever import NOT_FOUND_MESSAGE, retrieve
from app.rag.validator import ValidationError, validate_and_fix

logger = logging.getLogger(__name__)

_MAX_USER_MESSAGE_LEN = 4096


class ResponseType(str, Enum):
    ANSWER = "answer"
    REFUSAL = "refusal"
    NOT_FOUND = "not_found"
    ERROR = "error"


@dataclass(frozen=True)
class RagBackendResponse:
    """Unified chat payload for API and tests."""

    answer: str
    citation_url: str
    footer: str
    type: ResponseType
    query_class: str | None = None


class RagBackendError(Exception):
    """User-facing backend failure (index missing, LLM down)."""


def _refusal_response(classification: ClassifierResult) -> RagBackendResponse:
    return RagBackendResponse(
        answer=classification.refusal_message or "",
        citation_url=classification.citation_url or "",
        footer="",
        type=ResponseType.REFUSAL,
        query_class=classification.query_class.value,
    )


def _not_found_response() -> RagBackendResponse:
    return RagBackendResponse(
        answer=NOT_FOUND_MESSAGE,
        citation_url="",
        footer="",
        type=ResponseType.NOT_FOUND,
        query_class="FACTUAL",
    )


def _error_response(message: str) -> RagBackendResponse:
    return RagBackendResponse(
        answer=message,
        citation_url="",
        footer="",
        type=ResponseType.ERROR,
    )


def run_rag(
    message: str,
    *,
    force_template: bool = False,
    persist_directory: str | None = None,
) -> RagBackendResponse:
    """
    Execute the full RAG pipeline for one user message.

    Parameters
    ----------
    message:
        Raw user text.
    force_template:
        Skip Groq even if API key is set (tests).
    persist_directory:
        Optional Chroma path override.
    """
    text = (message or "").strip()
    if not text:
        raise ValueError("message is required")
    if len(text) > _MAX_USER_MESSAGE_LEN:
        raise ValueError(f"message exceeds {_MAX_USER_MESSAGE_LEN} characters")

    safe_log = redact_pii(text)
    logger.info("RAG query: %s", safe_log[:200])

    classification = classify_query(text)
    if not classification.should_retrieve:
        return _refusal_response(classification)

    try:
        retrieval = retrieve(text, persist_directory=persist_directory)
    except FileNotFoundError:
        logger.error("Vector index missing")
        raise RagBackendError(
            "Assistant is temporarily unavailable. Please try again later."
        ) from None

    if not retrieval.found:
        return _not_found_response()

    try:
        generated = generate_answer(
            text,
            retrieval,
            force_template=force_template,
        )
    except GenerationError as exc:
        logger.warning("Generation failed: %s", exc)
        try:
            generated = template_generate(text, retrieval)
        except GenerationError:
            return _error_response(
                "I could not generate an answer right now. Please try again later."
            )

    try:
        validated = validate_and_fix(
            generated.answer,
            citation_url=generated.citation_url,
            footer=generated.footer,
            is_refusal=False,
        )
    except ValidationError as exc:
        logger.warning("Validation failed, template retry: %s", exc)
        try:
            generated = template_generate(text, retrieval)
            validated = validate_and_fix(
                generated.answer,
                citation_url=generated.citation_url,
                footer=generated.footer,
                is_refusal=False,
            )
        except (GenerationError, ValidationError):
            return _error_response(
                "I could not produce a compliant answer. Please rephrase your question."
            )

    return RagBackendResponse(
        answer=validated.answer,
        citation_url=validated.citation_url,
        footer=validated.footer,
        type=ResponseType.ANSWER,
        query_class=classification.query_class.value,
    )
