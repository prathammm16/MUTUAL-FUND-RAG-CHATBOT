"""
Application configuration: scheme registry, aliases, and environment settings.

Phase 0 — single source of truth for the five Groww corpus URLs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Final
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AMC_NAME: Final[str] = "HDFC Mutual Fund"
GROWW_MUTUAL_FUNDS_PREFIX: Final[str] = "https://groww.in/mutual-funds/"

# Local embeddings (free, sentence-transformers)
BGE_SMALL_MODEL: Final[str] = "BAAI/bge-small-en-v1.5"
BGE_LARGE_MODEL: Final[str] = "BAAI/bge-large-en-v1.5"
EMBEDDING_PROVIDER_LOCAL: Final[str] = "local"
EMBEDDING_PROVIDER_OPENAI: Final[str] = "openai"
EMBEDDING_BACKEND_FASTEMBED: Final[str] = "fastembed"
EMBEDDING_BACKEND_SENTENCE_TRANSFORMERS: Final[str] = "sentence_transformers"


@dataclass(frozen=True)
class Scheme:
    """One scheme in the curated corpus."""

    scheme_id: str
    scheme_name: str
    source_url: str

    def __post_init__(self) -> None:
        if not self.source_url.startswith(GROWW_MUTUAL_FUNDS_PREFIX):
            raise ValueError(
                f"source_url must be under {GROWW_MUTUAL_FUNDS_PREFIX}: {self.source_url}"
            )


# --- Curated corpus (5 Groww scheme pages) ---
SCHEMES: Final[tuple[Scheme, ...]] = (
    Scheme(
        scheme_id="hdfc-silver-etf-fof",
        scheme_name="HDFC Silver ETF FoF Direct Growth",
        source_url="https://groww.in/mutual-funds/hdfc-silver-etf-fof-direct-growth",
    ),
    Scheme(
        scheme_id="hdfc-mid-cap",
        scheme_name="HDFC Mid Cap Fund Direct Growth",
        source_url="https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    ),
    Scheme(
        scheme_id="hdfc-equity",
        scheme_name="HDFC Equity Fund Direct Growth",
        source_url="https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
    ),
    Scheme(
        scheme_id="hdfc-gold-etf-fof",
        scheme_name="HDFC Gold ETF Fund of Fund Direct Plan Growth",
        source_url="https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth",
    ),
    Scheme(
        scheme_id="hdfc-nifty-50-index",
        scheme_name="HDFC NIFTY 50 Index Fund Direct Growth",
        source_url="https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth",
    ),
)

SCHEME_BY_ID: Final[dict[str, Scheme]] = {s.scheme_id: s for s in SCHEMES}
ALLOWLISTED_SOURCE_URLS: Final[frozenset[str]] = frozenset(s.source_url for s in SCHEMES)

# Alias phrase (normalized) -> scheme_id. Longer phrases matched first at runtime.
SCHEME_ALIASES: Final[dict[str, str]] = {
    # Silver FoF (not underlying ETF stock page — SC-11)
    "hdfc silver etf fof": "hdfc-silver-etf-fof",
    "silver etf fof": "hdfc-silver-etf-fof",
    "silver fof": "hdfc-silver-etf-fof",
    "silver fund": "hdfc-silver-etf-fof",
    "silver": "hdfc-silver-etf-fof",
    # Gold FoF
    "hdfc gold etf fund of fund": "hdfc-gold-etf-fof",
    "gold etf fund of fund": "hdfc-gold-etf-fof",
    "gold fund of fund": "hdfc-gold-etf-fof",
    "gold fof": "hdfc-gold-etf-fof",
    "gold fund": "hdfc-gold-etf-fof",
    # Mid cap (PH0-04)
    "hdfc mid cap fund": "hdfc-mid-cap",
    "hdfc mid cap": "hdfc-mid-cap",
    "mid cap fund": "hdfc-mid-cap",
    "mid-cap fund": "hdfc-mid-cap",
    "midcap fund": "hdfc-mid-cap",
    "mid cap": "hdfc-mid-cap",
    "midcap": "hdfc-mid-cap",
    "mid-cap": "hdfc-mid-cap",
    # Equity
    "hdfc equity fund": "hdfc-equity",
    "hdfc equity": "hdfc-equity",
    "equity fund": "hdfc-equity",
    # NIFTY 50 index
    "hdfc nifty 50 index fund": "hdfc-nifty-50-index",
    "nifty 50 index fund": "hdfc-nifty-50-index",
    "nifty 50 index": "hdfc-nifty-50-index",
    "nifty 50": "hdfc-nifty-50-index",
    "nifty50": "hdfc-nifty-50-index",
    "nifty index": "hdfc-nifty-50-index",
}

def _slug_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.split("/")[-1] if path else ""


# Groww URL path slug -> scheme_id (for SC-12)
_URL_SLUG_TO_SCHEME_ID: Final[dict[str, str]] = {
    _slug_from_url(s.source_url): s.scheme_id for s in SCHEMES
}

_ALIAS_PATTERNS: Final[list[tuple[str, str]]] = sorted(
    SCHEME_ALIASES.items(), key=lambda item: len(item[0]), reverse=True
)


def normalize_text(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation edges for matching."""
    lowered = text.lower().strip()
    cleaned = re.sub(r"[^\w\s-]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def get_scheme(scheme_id: str) -> Scheme | None:
    return SCHEME_BY_ID.get(scheme_id)


def get_all_schemes() -> list[Scheme]:
    return list(SCHEMES)


def is_allowlisted_source_url(url: str) -> bool:
    return url in ALLOWLISTED_SOURCE_URLS


def resolve_scheme_id_from_import_stem(stem: str) -> str | None:
    """Map import filename stem (no extension) to scheme_id."""
    normalized = stem.lower().replace("_", "-")
    if normalized in SCHEME_BY_ID:
        return normalized
    return _URL_SLUG_TO_SCHEME_ID.get(normalized)


def resolve_scheme_id_from_url(text: str) -> str | None:
    """Extract scheme_id if text contains an allowlisted Groww mutual-fund URL."""
    for scheme in SCHEMES:
        if scheme.source_url in text:
            return scheme.scheme_id
    match = re.search(r"groww\.in/mutual-funds/([a-z0-9-]+)", text, re.IGNORECASE)
    if match:
        slug = match.group(1).lower()
        return _URL_SLUG_TO_SCHEME_ID.get(slug)
    return None


def resolve_scheme_id_from_text(text: str) -> str | None:
    """
    Resolve scheme from URL, full scheme name, or alias (longest match wins).
    """
    from_url = resolve_scheme_id_from_url(text)
    if from_url:
        return from_url

    normalized = normalize_text(text)
    for scheme in SCHEMES:
        if normalize_text(scheme.scheme_name) in normalized:
            return scheme.scheme_id

    for alias, scheme_id in _ALIAS_PATTERNS:
        if alias in normalized:
            return scheme_id

    return None


def validate_registry() -> None:
    """Raise if registry violates Phase 0 invariants (PH0-01, PH0-02)."""
    if len(SCHEMES) != 5:
        raise ValueError(f"Expected exactly 5 schemes, got {len(SCHEMES)}")

    ids = [s.scheme_id for s in SCHEMES]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate scheme_id in SCHEMES")

    urls = [s.source_url for s in SCHEMES]
    if len(urls) != len(set(urls)):
        raise ValueError("Duplicate source_url in SCHEMES")

    alias_targets = set(SCHEME_ALIASES.values())
    unknown = alias_targets - set(ids)
    if unknown:
        raise ValueError(f"Aliases reference unknown scheme_ids: {unknown}")


class Settings(BaseSettings):
    """Environment-driven settings (optional in Phase 0; required in later phases)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    groq_api_key: str = ""
    # local = free BGE via sentence-transformers; openai = paid API
    embedding_provider: str = "local"
    embedding_model: str = BGE_SMALL_MODEL
    # When true and model is bge-small/bge-large, pick small vs large from chunk stats
    embedding_auto_bge: bool = True
    chat_model: str = "llama-3.3-70b-versatile"
    top_k: int = 5
    similarity_threshold: float = 0.7
    amfi_education_url: str = Field(
        default="https://www.amfiindia.com/investor/knowledge-center-info"
    )
    sebi_investor_url: str = Field(default="https://investor.sebi.gov.in/")
    corpus_version: int = 1
    ingested_at: str = ""
    ingest_cron_schedule: str = "0 10 * * *"
    ingest_timezone: str = "Asia/Kolkata"
    vector_store_path: str = "vector_store"
    ingest_lock_ttl_seconds: int = 7200
    admin_reindex_token: str = ""
    admin_reindex_enabled: bool = True
    max_ingest_chunk_drop_ratio: float = 0.5
    # Local embedding runtime: fastembed (ONNX, ~80MB RAM) or sentence_transformers (PyTorch, ~1GB+)
    # auto → fastembed in production, sentence_transformers in development
    embedding_backend: str = "auto"
    index_batch_size: int = 16
    preload_embedding_model: bool = False
    serve_ui: bool = True
    # Phase 9 — production API hardening
    app_env: str = "development"
    cors_origins: str = ""
    chat_rate_limit_per_minute: int = 0

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    def resolved_embedding_backend(self) -> str:
        """Pick ONNX fastembed (Railway-friendly) vs full sentence-transformers."""
        raw = (self.embedding_backend or "auto").strip().lower()
        if raw == "auto":
            return (
                EMBEDDING_BACKEND_FASTEMBED
                if self.is_production
                else EMBEDDING_BACKEND_SENTENCE_TRANSFORMERS
            )
        if raw in (
            EMBEDDING_BACKEND_FASTEMBED,
            "fast",
            "onnx",
        ):
            return EMBEDDING_BACKEND_FASTEMBED
        if raw in (
            EMBEDDING_BACKEND_SENTENCE_TRANSFORMERS,
            "st",
            "torch",
        ):
            return EMBEDDING_BACKEND_SENTENCE_TRANSFORMERS
        return raw

    @property
    def effective_chat_rate_limit_per_minute(self) -> int:
        if self.chat_rate_limit_per_minute > 0:
            return self.chat_rate_limit_per_minute
        if self.is_production:
            return 30
        return 0

    @property
    def admin_reindex_allowed(self) -> bool:
        if not self.admin_reindex_enabled:
            return False
        if self.is_production and not (self.admin_reindex_token or "").strip():
            return False
        return bool((self.admin_reindex_token or "").strip())

    def resolved_cors_origins(self) -> list[str]:
        raw = (self.cors_origins or "").strip()
        if raw and raw != "*":
            return [o.strip() for o in raw.split(",") if o.strip()]
        if self.is_production:
            return [
                "http://127.0.0.1:8000",
                "http://localhost:8000",
            ]
        return [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ]

    def resolved_cors_origin_regex(self) -> str | None:
        """
        Regex for split deploy (Railway API + Vercel UI).

        In production always allow ``*.vercel.app`` so preview + production
        Vercel URLs pass OPTIONS preflight (avoids 400 from browser).
        """
        raw = (self.cors_origins or "").strip()
        if raw == "*":
            return r"https?://.*"
        if self.is_production:
            return r"https://([a-z0-9-]+\.)*vercel\.app"
        return None

    def cors_allow_credentials(self) -> bool:
        """No cookie/session auth — keep false so cross-origin fetch works."""
        return False

    @field_validator("amfi_education_url", "sebi_investor_url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError(f"URL must be http(s): {value}")
        return value


@lru_cache
def get_settings() -> Settings:
    validate_registry()
    return Settings()


# Run invariant check on import so misconfiguration fails fast.
validate_registry()
