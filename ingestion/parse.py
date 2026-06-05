"""
Parse Groww scheme pages: strip boilerplate and map semantic sections.

Phase 1 tasks 1.1 (noise removal) and 1.2 (section mapper).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from app.config import (
    Scheme,
    get_scheme,
    is_allowlisted_source_url,
    resolve_scheme_id_from_url,
)

# Canonical section ids used downstream (chunking / retrieval).
SECTION_IDS: tuple[str, ...] = (
    "costs",
    "exit_load",
    "tax",
    "minimum_investment",
    "risk",
    "benchmark",
    "fund_management",
    "objective",
)

_SOURCE_URL_RE = re.compile(
    r"(?:^|\n)\s*(?:\*\*)?Source\s+URL(?:\*\*)?\s*:?\s*(https?://\S+)",
    re.IGNORECASE | re.MULTILINE,
)
_NAV_DATE_RE = re.compile(
    r"(?:NAV|Net Asset Value)\s*(?:as\s+on|on|:)\s*"
    r"(\d{1,2}[-/]\w{3,9}[-/]\d{2,4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

# Lines or inline blocks to drop (IG-05: nav, footer, calculators).
_NOISE_LINE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^\s*\[?Home\]?\s*$",
        r"^\s*Mutual\s+Funds\s*$",
        r"^\s*Stocks\s*$",
        r"^\s*FD\s*$",
        r"^\s*Gold\s*$",
        r"^\s*US\s+Stocks\s*$",
        r"^\s*More\s*$",
        r"^\s*Search\s*$",
        r"^\s*Login\s*$",
        r"^\s*Sign\s+Up\s*$",
        r"SIP\s+Calculator",
        r"Lumpsum\s+Calculator",
        r"Returns?\s+Calculator",
        r"Calculate\s+(?:your\s+)?returns",
        r"Investment\s+Calculator",
        r"^\s*If\s+you\s+invest(?:ed)?\s+",
        r"^\s*Monthly\s+SIP\s+of\s+₹",
        r"^\s*Total\s+investment\s+value",
        r"^\s*Download\s+Groww",
        r"^\s*Get\s+the\s+app",
        r"©\s*\d{4}",
        r"Privacy\s+Policy",
        r"Terms\s+(?:&|and)\s+Conditions",
        r"Grievance\s+Redressal",
        r"Similar\s+funds",
        r"You\s+may\s+also\s+like",
        r"Popular\s+on\s+Groww",
        r"^\s*Explore\s+all\s+mutual\s+funds",
        r"^\s*Trending\s+on\s+Groww",
        r"^\s*Footer\s*$",
        r"^\s*---\s*$",
    )
)

# Entire heading-led blocks to skip when the heading matches.
_NOISE_SECTION_HEADING_RE = re.compile(
    r"^(?:SIP|Lumpsum|Return[s]?)\s+Calculator|"
    r"Similar\s+funds|You\s+may\s+also\s+like|"
    r"Popular\s+on\s+Groww|Explore\s+more|"
    r"Download\s+Groww|Related\s+funds",
    re.IGNORECASE,
)

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)

# (section_id, heading/content keyword patterns) — first match wins per block.
_SECTION_RULES: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "fund_management",
        (
            re.compile(r"fund\s+manag", re.I),
            re.compile(r"fund\s+manager", re.I),
            re.compile(r"managed\s+by", re.I),
        ),
    ),
    (
        "exit_load",
        (
            re.compile(r"exit\s+load", re.I),
            re.compile(r"redemption\s+charg", re.I),
        ),
    ),
    (
        "tax",
        (
            re.compile(r"\btax(?:ation)?\b", re.I),
            re.compile(r"capital\s+gains", re.I),
            re.compile(r"stcg|ltcg", re.I),
        ),
    ),
    (
        "minimum_investment",
        (
            re.compile(r"minimum\s+invest", re.I),
            re.compile(r"min\.?\s*(?:sip|lumpsum)", re.I),
            re.compile(r"minimum\s+sip", re.I),
            re.compile(r"minimum\s+amount", re.I),
        ),
    ),
    (
        "costs",
        (
            re.compile(r"expense\s+ratio", re.I),
            re.compile(r"\bter\b", re.I),
            re.compile(r"transaction\s+charg", re.I),
            re.compile(r"stamp\s+duty", re.I),
            re.compile(r"other\s+charg", re.I),
            re.compile(r"\bcosts?\b", re.I),
            re.compile(r"fund\s+expenses", re.I),
        ),
    ),
    (
        "risk",
        (
            re.compile(r"riskometer", re.I),
            re.compile(r"\brisk\s+level\b", re.I),
            re.compile(r"very\s+high\s+risk", re.I),
        ),
    ),
    ("benchmark", (re.compile(r"benchmark", re.I),)),
    (
        "objective",
        (
            re.compile(r"\bobjective\b", re.I),
            re.compile(r"investment\s+objective", re.I),
            re.compile(r"about\s+(?:the\s+)?scheme", re.I),
        ),
    ),
)

_EXIT_LOAD_HISTORY_RE = re.compile(
    r"historical|previous(?:ly)?|earlier|was\s+applicable|old\s+exit\s+load",
    re.IGNORECASE,
)


@dataclass
class ParsedScheme:
    """Cleaned, sectioned corpus for one scheme (Phase 1 output shape)."""

    scheme_id: str
    scheme_name: str
    source_url: str
    sections: dict[str, str] = field(default_factory=dict)
    last_updated: str | None = None


def extract_source_url(text: str) -> str | None:
    """Read ``Source URL:`` from document header (Groww export convention)."""
    match = _SOURCE_URL_RE.search(text)
    if not match:
        return None
    url = match.group(1).rstrip(").,]")
    return url if resolve_scheme_id_from_url(url) else None


def extract_nav_date(text: str) -> str | None:
    """Best-effort NAV / as-on date for ``last_updated`` (CI-06)."""
    match = _NAV_DATE_RE.search(text)
    if not match:
        return None
    raw = match.group(1).strip()
    for fmt in ("%d-%b-%Y", "%d %b %Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw.replace("/", "-"), fmt)
            return parsed.date().isoformat()
        except ValueError:
            continue
    return raw


def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return any(p.search(stripped) for p in _NOISE_LINE_PATTERNS)


def strip_noise(text: str) -> str:
    """
    Remove navigation, footer, calculator, and cross-promotional boilerplate.

    IG-05: nav/calculator noise must not appear in parsed output.
    """
    if not text:
        return ""

    # Drop calculator / promo sections bounded by headings.
    blocks = _split_by_headings(text)
    kept: list[str] = []
    for heading, body in blocks:
        if heading and _NOISE_SECTION_HEADING_RE.search(heading):
            continue
        if heading:
            kept.append(f"## {heading}")
        for line in body.splitlines():
            if not _is_noise_line(line):
                kept.append(line)
    cleaned = "\n".join(kept)

    # Line-level pass for inline noise without headings.
    lines = [ln for ln in cleaned.splitlines() if not _is_noise_line(ln)]
    cleaned = "\n".join(lines)

    # Collapse excessive blank lines.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _split_by_headings(text: str) -> list[tuple[str | None, str]]:
    """Split markdown into (heading, body) segments in document order."""
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [(None, text)]

    segments: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        segments.append((None, text[: matches[0].start()]))

    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segments.append((heading, text[start:end]))
    return segments


def classify_section(heading: str, body: str) -> str | None:
    """Map a heading+body block to a canonical section id, or None if unmatched."""
    probe = f"{heading}\n{body[:500]}"
    for section_id, patterns in _SECTION_RULES:
        if any(p.search(probe) for p in patterns):
            return section_id
    return None


def _canonicalize_exit_load(existing: str, candidate: str) -> str:
    """
    Keep one exit-load block per scheme (IG-06, RT-04).

    Prefer the block without historical wording; otherwise keep the longer block.
    """
    if not existing:
        return candidate
    existing_hist = bool(_EXIT_LOAD_HISTORY_RE.search(existing))
    candidate_hist = bool(_EXIT_LOAD_HISTORY_RE.search(candidate))
    if existing_hist and not candidate_hist:
        return candidate
    if candidate_hist and not existing_hist:
        return existing
    return candidate if len(candidate) > len(existing) else existing


def map_sections(cleaned_text: str) -> dict[str, str]:
    """
    Map cleaned markdown into canonical sections (task 1.2).

    Unmapped blocks are omitted; duplicate section keys are merged with
    section-specific rules (e.g. single canonical exit_load).
    """
    sections: dict[str, str] = {}
    for heading, body in _split_by_headings(cleaned_text):
        body = body.strip()
        if not body and not heading:
            continue
        section_id = classify_section(heading or "", body)
        if not section_id:
            continue
        content = body
        if heading:
            content = f"{heading}\n{body}".strip()
        if section_id == "exit_load":
            sections[section_id] = _canonicalize_exit_load(
                sections.get(section_id, ""), content
            )
        elif section_id in sections:
            sections[section_id] = f"{sections[section_id]}\n\n{content}".strip()
        else:
            sections[section_id] = content
    return sections


def parse_document(
    raw_text: str,
    *,
    scheme: Scheme | None = None,
    scheme_id: str | None = None,
    source_url: str | None = None,
) -> ParsedScheme:
    """
    Full parse pipeline: extract metadata, strip noise, map sections.

    ``scheme`` or ``scheme_id`` must be resolvable via config when not inferable
    from ``Source URL`` in the document.
    """
    header_url = extract_source_url(raw_text)
    resolved_id = resolve_scheme_id_from_url(header_url or "") if header_url else None
    if scheme:
        resolved_id = scheme.scheme_id
        resolved_scheme = scheme
    elif scheme_id:
        resolved_id = scheme_id
        resolved_scheme = get_scheme(scheme_id)
        if resolved_scheme is None:
            raise ValueError(f"Unknown scheme_id: {scheme_id}")
    elif resolved_id:
        resolved_scheme = get_scheme(resolved_id)
        if resolved_scheme is None:
            raise ValueError(f"Unknown scheme_id from URL: {resolved_id}")
    else:
        raise ValueError(
            "Cannot resolve scheme: provide scheme/scheme_id or Source URL header"
        )

    final_url = header_url or source_url or resolved_scheme.source_url
    if not is_allowlisted_source_url(final_url):
        raise ValueError(f"source_url not allowlisted: {final_url}")

    if source_url and header_url and source_url != header_url:
        # PH1-03: prefer explicit header over filename hint
        final_url = header_url

    cleaned = strip_noise(raw_text)
    sections = map_sections(cleaned)

    return ParsedScheme(
        scheme_id=resolved_scheme.scheme_id,
        scheme_name=resolved_scheme.scheme_name,
        source_url=final_url,
        sections=sections,
        last_updated=extract_nav_date(raw_text),
    )
