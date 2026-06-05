"""
Query classifier and compliance refusals (Phase 3).

Runs **before** retrieval: advisory, performance, PII, and out-of-corpus checks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Final

from app.config import (
    AMC_NAME,
    get_all_schemes,
    get_settings,
    normalize_text,
    resolve_scheme_id_from_text,
)

# --- PII patterns (CL-09, CL-10, CL-11) ---

_PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
_AADHAAR_PATTERN = re.compile(r"\b(?:\d{4}[\s-]?){2}\d{4}\b")
_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
)
_PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)",
)
_ACCOUNT_PATTERN = re.compile(
    r"\b(?:account|a/c|acct)\s*(?:no\.?|number|#)?\s*:?\s*\d{6,18}\b",
    re.IGNORECASE,
)
_OTP_PATTERN = re.compile(
    r"\b(?:otp|one[\s-]?time[\s-]?password)\s*(?:is|:)?\s*\d{4,8}\b",
    re.IGNORECASE,
)

_PII_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    _PAN_PATTERN,
    _AADHAAR_PATTERN,
    _EMAIL_PATTERN,
    _PHONE_PATTERN,
    _ACCOUNT_PATTERN,
    _OTP_PATTERN,
)

# Non-HDFC AMC / scheme mentions (CL-12)
_NON_HDFC_AMC_PHRASES: Final[tuple[str, ...]] = (
    "sbi mutual",
    "sbi fund",
    "sbi bluechip",
    "icici prudential",
    "icici mutual",
    "axis mutual",
    "axis fund",
    "nippon india",
    "kotak mutual",
    "uti mutual",
    "mirae asset",
    "parag parikh",
    "bandhan mutual",
    "tata mutual",
)

# HDFC schemes outside the curated five (CL-13)
_HDFC_OUT_OF_CORPUS_PHRASES: Final[tuple[str, ...]] = (
    "flexi cap",
    "flexi-cap",
    "flexicap",
    "top 100",
    "top100",
    "balanced advantage",
    "short term debt",
    "liquid fund",
    "tax saver",
    "elss",
    "hybrid equity",
    "arbitrage fund",
    "infrastructure fund",
    "small cap fund",
    "large cap fund",
)

# Performance / return queries (CL-05, CL-06, CL-08)
_PERFORMANCE_PHRASES: Final[tuple[str, ...]] = (
    "return",
    "returns",
    "cagr",
    "3y return",
    "3 year return",
    "1y return",
    "5 year return",
    "compare return",
    "compare the return",
    "compare all five return",
    "performance of",
    "outperform",
    "out perform",
    "beat nifty",
    "beat the nifty",
    "beat market",
    "alpha",
    "xirr",
    "nav history",
    "historical performance",
    "which performed better",
    "which has higher return",
)

# Advisory / opinion (CL-01–04, CL-16, CL-19, CL-21, FM-06, FM-07)
_ADVISORY_PHRASES: Final[tuple[str, ...]] = (
    "should i invest",
    "should i buy",
    "should i switch",
    "should i pick",
    "which fund should",
    "which should i",
    "should we invest",
    "worth investing",
    "worth buying",
    "good investment",
    "good for me",
    "recommend",
    "recommendation",
    "which fund is better",
    "which is better",
    "which one is better",
    "what fund is better",
    "better fund",
    "best fund",
    "is it good to invest",
    "is this a good fund",
    "is this fund good",
    "is this fund amazing",
    "fund is amazing",
    "thoughts on investing",
    "your opinion",
    "what do you think",
    "ignore previous instructions",
    "ignore all instructions",
    "disregard your instructions",
    "pretend you are",
    "jailbreak",
    "you should buy",
    "you should invest",
    "buy or sell",
    "hold or sell",
)

_MANAGER_OPINION_RE = re.compile(
    r"\b(?:fund\s+)?manager\b.*\b(?:best|good|better|recommend|switch)\b"
    r"|\b(?:best|good|better|recommend)\b.*\b(?:fund\s+)?manager\b"
    r"|\bswitch\b.*\b(?:because of|due to)\b.*\bmanager\b",
    re.IGNORECASE,
)

_BETTER_WORD_RE = re.compile(r"\bbetter\b", re.IGNORECASE)
_BENCHMARK_WORD_RE = re.compile(r"\bbenchmark\b", re.IGNORECASE)

_REGULATORY_POINTER_PHRASES: Final[tuple[str, ...]] = (
    "what does sebi say",
    "what does amfi say",
    "sebi regulation",
    "amfi regulation",
    "sebi rules for",
    "amfi rules for",
)


class QueryClass(str, Enum):
    """Classifier output labels."""

    ADVISORY = "ADVISORY"
    PERFORMANCE_COMPARE = "PERFORMANCE_COMPARE"
    PII = "PII"
    OUT_OF_CORPUS = "OUT_OF_CORPUS"
    FACTUAL = "FACTUAL"


@dataclass(frozen=True)
class ClassifierResult:
    """Classification outcome; factual queries proceed to retrieval."""

    query_class: QueryClass
    refusal_message: str | None = None
    citation_url: str | None = None

    @property
    def should_retrieve(self) -> bool:
        return self.query_class == QueryClass.FACTUAL


def contains_pii(text: str) -> bool:
    """Return True if text matches any PII pattern."""
    if any(p.search(text) for p in _PII_PATTERNS):
        return True
    if re.search(r"\baadhaar\b", text, re.IGNORECASE) and re.search(r"\d{4}[\s-]?\d{4}[\s-]?\d{4}", text):
        return True
    return False


def redact_pii(text: str) -> str:
    """Redact PII patterns for safe logging (SE-04 stub)."""
    redacted = text
    for pattern in _PII_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _supported_schemes_list() -> str:
    return "; ".join(s.scheme_name for s in get_all_schemes())


def _has_phrase(normalized: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in normalized for phrase in phrases)


def _has_better_advisory_signal(text: str, normalized: str) -> bool:
    """Detect advisory 'better' without false-positive on 'benchmark' (CL-20)."""
    if "benchmark" in normalized:
        return False
    if not _BETTER_WORD_RE.search(text):
        return False
    # Factual comparisons of metrics are still advisory when choosing funds.
    advisory_better = (
        "which" in normalized and "better" in normalized,
        "what" in normalized and "better" in normalized and "fund" in normalized,
        "better fund" in normalized,
        "is better" in normalized and "fund" in normalized,
    )
    return any(advisory_better)


def _mentions_out_of_corpus_scheme(text: str, normalized: str) -> bool:
    if _has_phrase(normalized, _NON_HDFC_AMC_PHRASES):
        return True

    if _has_phrase(normalized, _HDFC_OUT_OF_CORPUS_PHRASES):
        return True

    # Competitor AMC token without "hdfc" in our five
    if re.search(r"\bsbi\b", normalized) and "hdfc" not in normalized.split("sbi")[0][-10:]:
        if not resolve_scheme_id_from_text(text):
            return True

    # HDFC mentioned but does not resolve to one of the five
    if "hdfc" in normalized and not resolve_scheme_id_from_text(text):
        if _has_phrase(normalized, _HDFC_OUT_OF_CORPUS_PHRASES):
            return True
        # Generic unknown HDFC product names
        if re.search(r"\bhdfc\s+(?:flexi|top\s*100|liquid|elss|tax\s*saver)\b", normalized):
            return True

    return False


def _is_performance_query(normalized: str) -> bool:
    return _has_phrase(normalized, _PERFORMANCE_PHRASES)


def _is_advisory_query(text: str, normalized: str) -> bool:
    if _has_phrase(normalized, _ADVISORY_PHRASES):
        return True
    if _MANAGER_OPINION_RE.search(text):
        return True
    if _has_better_advisory_signal(text, normalized):
        return True
    if re.search(r"\b(?:is|are)\s+.+\s+(?:best|good)\s+(?:for\s+me|manager)\b", normalized):
        return True
    if re.search(r"\b(?:is|are)\s+the\s+manager\s+(?:best|good)\b", normalized):
        return True
    return False


def _is_regulatory_pointer(normalized: str) -> bool:
    return _has_phrase(normalized, _REGULATORY_POINTER_PHRASES)


def build_refusal(query_class: QueryClass) -> tuple[str, str]:
    """
    Return (refusal_message, citation_url) for a non-factual class.

    Educational links come from config (AMFI primary, SEBI referenced in copy).
    """
    settings = get_settings()
    amfi = settings.amfi_education_url
    sebi = settings.sebi_investor_url
    schemes = _supported_schemes_list()

    if query_class == QueryClass.PII:
        message = (
            "For your privacy, this assistant cannot process messages that contain "
            "personal identifiers (such as PAN, phone, email, Aadhaar, account numbers, or OTP). "
            "Please remove sensitive information and ask a factual question about the supported schemes."
        )
        return message, amfi

    if query_class == QueryClass.OUT_OF_CORPUS:
        message = (
            f"I can only answer factual questions about these five {AMC_NAME} schemes: "
            f"{schemes}. "
            "Please ask about one of these funds or rephrase your question."
        )
        return message, amfi

    if query_class == QueryClass.PERFORMANCE_COMPARE:
        message = (
            "I provide facts from scheme pages only and cannot compare returns, rank funds, "
            "or predict performance. "
            f"For investor education, see [AMFI]({amfi}) or [SEBI]({sebi})."
        )
        return message, amfi

    # ADVISORY and regulatory pointer (CL-22)
    message = (
        "I can share objective facts from the five supported HDFC scheme pages only — "
        "not investment advice, opinions, or recommendations. "
        f"For investor education, see [AMFI]({amfi}) or [SEBI]({sebi})."
    )
    return message, amfi


def classify_query(message: str) -> ClassifierResult:
    """
    Classify a user message before retrieval.

    Priority: PII → out-of-corpus → performance → advisory → factual.
    """
    text = (message or "").strip()
    if not text:
        return ClassifierResult(query_class=QueryClass.FACTUAL)

    normalized = normalize_text(text)

    if contains_pii(text):
        refusal, url = build_refusal(QueryClass.PII)
        return ClassifierResult(
            query_class=QueryClass.PII,
            refusal_message=refusal,
            citation_url=url,
        )

    if _mentions_out_of_corpus_scheme(text, normalized):
        refusal, url = build_refusal(QueryClass.OUT_OF_CORPUS)
        return ClassifierResult(
            query_class=QueryClass.OUT_OF_CORPUS,
            refusal_message=refusal,
            citation_url=url,
        )

    if _is_performance_query(normalized):
        refusal, url = build_refusal(QueryClass.PERFORMANCE_COMPARE)
        return ClassifierResult(
            query_class=QueryClass.PERFORMANCE_COMPARE,
            refusal_message=refusal,
            citation_url=url,
        )

    if _is_advisory_query(text, normalized) or _is_regulatory_pointer(normalized):
        refusal, url = build_refusal(QueryClass.ADVISORY)
        return ClassifierResult(
            query_class=QueryClass.ADVISORY,
            refusal_message=refusal,
            citation_url=url,
        )

    return ClassifierResult(query_class=QueryClass.FACTUAL)
