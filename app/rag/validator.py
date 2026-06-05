"""
Post-generation validation and safe fixes (Phase 5).

Enforces ≤3 sentences, one allowlisted citation URL, footer, and no advisory leakage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from app.config import (
    ALLOWLISTED_SOURCE_URLS,
    get_settings,
    is_allowlisted_source_url,
)
from app.rag.generator import format_footer

_MAX_SENTENCES: Final[int] = 3
_FOOTER_PREFIX: Final[str] = "Last updated from sources:"

_URL_RE = re.compile(r"https?://[^\s\)\]>]+", re.IGNORECASE)
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)]+)\)", re.IGNORECASE)

_ADVISORY_LEAK_RE = re.compile(
    r"\b(?:you should (?:buy|invest)|recommend(?:ation)?|better fund|best fund|"
    r"should i invest|worth buying|good investment)\b",
    re.IGNORECASE,
)

_RETURN_COMPUTE_RE = re.compile(
    r"\b(?:\d+(\.\d+)?\s*%|cagr|xirr|outperform|beat the market)\b",
    re.IGNORECASE,
)


class ValidationError(ValueError):
    """Answer failed validation and could not be repaired."""


@dataclass(frozen=True)
class ValidationResult:
    """Validated (and possibly repaired) assistant payload."""

    answer: str
    citation_url: str
    footer: str
    valid: bool
    repairs: tuple[str, ...]


def _allowed_citation_urls() -> frozenset[str]:
    settings = get_settings()
    return ALLOWLISTED_SOURCE_URLS | frozenset(
        {settings.amfi_education_url, settings.sebi_investor_url}
    )


def count_sentences(text: str) -> int:
    """Count sentences in prose (ignores markdown link targets)."""
    without_links = _MARKDOWN_LINK_RE.sub(r"\1", text)
    without_links = _URL_RE.sub("", without_links)
    chunks = re.split(r"(?<=[.!?])\s+", without_links.strip())
    return len([c for c in chunks if c.strip()])


def extract_urls(text: str) -> list[str]:
    urls = _URL_RE.findall(text)
    for _label, url in _MARKDOWN_LINK_RE.findall(text):
        urls.append(url)
    return urls


def _trim_to_max_sentences(text: str, max_sentences: int = _MAX_SENTENCES) -> str:
    without_links = _MARKDOWN_LINK_RE.sub(r"\1", text)
    parts = re.split(r"(?<=[.!?])\s+", without_links.strip())
    kept: list[str] = []
    for part in parts:
        if not part.strip():
            continue
        kept.append(part.strip())
        if len(kept) >= max_sentences:
            break
    if not kept:
        return text.strip()
    result = ". ".join(kept)
    if not result.endswith((".", "!", "?")):
        result += "."
    # Restore a single markdown link if present in original
    md = _MARKDOWN_LINK_RE.search(text)
    if md and md.group(2) not in result:
        result = result.rstrip(".") + f" [{md.group(1) or 'source'}]({md.group(2)})."
    return result


def _normalize_answer_body(answer: str, citation_url: str) -> tuple[str, tuple[str, ...]]:
    """Inject citation, trim sentences, strip extra URLs."""
    repairs: list[str] = []
    body = answer.strip()
    urls = extract_urls(body)

    allowlisted = [u for u in urls if is_allowlisted_source_url(u)]
    edu = _allowed_citation_urls() - ALLOWLISTED_SOURCE_URLS
    edu_hits = [u for u in urls if u in edu]

    groww_url = citation_url if is_allowlisted_source_url(citation_url) else None
    if not groww_url and allowlisted:
        groww_url = allowlisted[0]

    if not groww_url:
        if is_allowlisted_source_url(citation_url):
            groww_url = citation_url
        else:
            raise ValidationError("citation_url is not allowlisted")

    # Remove non-allowlisted URLs (GN-04)
    for url in urls:
        if url not in _allowed_citation_urls():
            body = body.replace(url, "")
            repairs.append("removed_non_allowlisted_url")

    # Ensure exactly one markdown link to groww (GN-02, GN-03)
    if groww_url not in body:
        body = body.rstrip() + f" See the [scheme page]({groww_url})."
        repairs.append("injected_citation")
    else:
        # Keep only scheme citation in markdown; plain duplicate URLs removed
        md_links = _MARKDOWN_LINK_RE.findall(body)
        if len(md_links) > 1:
            first = True
            new_body = body
            for label, url in md_links:
                if url != groww_url and first:
                    new_body = new_body.replace(f"[{label}]({url})", label or "")
                    repairs.append("deduped_links")
                first = False
            body = new_body

    if count_sentences(body) > _MAX_SENTENCES:
        body = _trim_to_max_sentences(body, _MAX_SENTENCES)
        repairs.append("trimmed_sentences")

    return body.strip(), tuple(repairs)


def _split_footer(answer: str) -> tuple[str, str | None]:
    lines = answer.splitlines()
    body_lines: list[str] = []
    footer_line: str | None = None
    for line in lines:
        if line.strip().startswith(_FOOTER_PREFIX):
            footer_line = line.strip()
        else:
            body_lines.append(line)
    return "\n".join(body_lines).strip(), footer_line


def validate_and_fix(
    answer: str,
    *,
    citation_url: str,
    footer: str,
    is_refusal: bool = False,
) -> ValidationResult:
    """
    Validate assistant text; apply safe repairs (footer, citation, sentence cap).
    """
    repairs: list[str] = []
    body, existing_footer = _split_footer(answer)

    if _ADVISORY_LEAK_RE.search(body):
        raise ValidationError("advisory language in answer")

    if not is_refusal and _RETURN_COMPUTE_RE.search(body):
        # Allow percentages that appear in factual expense lines — soft check only
        if re.search(r"\bcompare\b|\boutperform\b|\bcagr\b", body, re.IGNORECASE):
            raise ValidationError("performance comparison in answer")

    if is_refusal:
        allowed = _allowed_citation_urls()
        urls = extract_urls(body)
        cite = citation_url if citation_url in allowed else get_settings().amfi_education_url
        final_footer = footer or format_footer(None)
        return ValidationResult(
            answer=body,
            citation_url=cite,
            footer=final_footer,
            valid=True,
            repairs=tuple(repairs),
        )

    try:
        body, body_repairs = _normalize_answer_body(body, citation_url)
        repairs.extend(body_repairs)
    except ValidationError:
        raise

    final_footer = (existing_footer or footer or "").strip()
    if not final_footer.startswith(_FOOTER_PREFIX):
        final_footer = footer.strip() if footer.strip().startswith(_FOOTER_PREFIX) else format_footer(None)
        repairs.append("appended_footer")

    if count_sentences(body) > _MAX_SENTENCES:
        body = _trim_to_max_sentences(body)
        repairs.append("trimmed_sentences_final")

    final_cite = citation_url
    for url in extract_urls(body):
        if is_allowlisted_source_url(url):
            final_cite = url
            break

    return ValidationResult(
        answer=body,
        citation_url=final_cite,
        footer=final_footer,
        valid=True,
        repairs=tuple(repairs),
    )


def compose_response_text(answer: str, footer: str) -> str:
    """Single display string: answer body (footer returned separately by API)."""
    return answer.strip()
