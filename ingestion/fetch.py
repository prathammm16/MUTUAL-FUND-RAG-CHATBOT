"""
Fetch Groww scheme pages into ``data/raw/`` (Phase 7.1 daily pipeline; usable from Phase 1 import path).

Per scheme writes three artifacts under ``data/raw/``:
  - ``{scheme_id}.html`` — raw Groww page HTML
  - ``{scheme_id}.json`` — extracted ``mfServerSideData`` (+ metadata)
  - ``{scheme_id}.md`` — markdown for ``ingestion/parse.py``
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.config import Scheme, get_all_schemes

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = _PROJECT_ROOT / "data" / "raw"

_USER_AGENT = (
    "Mozilla/5.0 (compatible; HDFC-MF-FAQ-Bot/1.0; +https://groww.in/mutual-funds/)"
)
_FETCH_DELAY_SEC = 1.5
_FETCH_MAX_RETRIES = 3
_FETCH_BACKOFF_BASE_SEC = 2.0
_RETRYABLE_STATUS = frozenset({403, 429, 500, 502, 503, 504})


class FetchError(Exception):
    """Groww fetch failed for one or more schemes (IG-01, IG-02)."""


@dataclass(frozen=True)
class RawArtifacts:
    """Paths to the three raw files for one scheme."""

    scheme_id: str
    html: Path
    json: Path
    markdown: Path


def raw_paths(scheme_id: str, raw_dir: Path | None = None) -> RawArtifacts:
    """Standard paths for raw HTML / JSON / markdown."""
    base = raw_dir or DEFAULT_RAW_DIR
    return RawArtifacts(
        scheme_id=scheme_id,
        html=base / f"{scheme_id}.html",
        json=base / f"{scheme_id}.json",
        markdown=base / f"{scheme_id}.md",
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip()


def _format_manager_block(manager: dict[str, Any]) -> str:
    lines = [f"Fund manager: {_safe_str(manager.get('person_name'))}"]
    if manager.get("date_from"):
        lines.append(f"Managing since: {_safe_str(manager.get('date_from'))}")
    if manager.get("education"):
        lines.append(f"Education: {_safe_str(manager.get('education'))}")
    if manager.get("experience"):
        lines.append(f"Experience: {_safe_str(manager.get('experience'))}")
    funds = manager.get("funds_managed") or []
    if funds:
        names = [_safe_str(f.get("scheme_name")) for f in funds if f.get("scheme_name")]
        if names:
            lines.append(f"Also manages: {', '.join(names)}")
    return "\n".join(lines)


def groww_data_to_markdown(
    mf: dict[str, Any],
    *,
    scheme: Scheme,
) -> str:
    """Convert Groww ``mfServerSideData`` JSON to importable markdown."""
    lines = [
        f"Source URL: {scheme.source_url}",
        "",
        f"# {scheme.scheme_name}",
        "",
    ]

    nav = mf.get("nav")
    nav_date = mf.get("nav_date")
    if nav is not None:
        lines.append(f"NAV as on {nav_date or 'latest'}: ₹{nav}")
        lines.append("")

    expense = mf.get("expense_ratio")
    if expense:
        lines.extend(
            [
                "## Expense ratio and costs",
                "",
                f"Expense ratio: {expense}%",
                "",
            ]
        )

    exit_load = mf.get("exit_load")
    if exit_load:
        lines.extend(["## Exit load", "", _safe_str(exit_load), ""])

    tax = (mf.get("category_info") or {}).get("tax_impact") or mf.get("tax_impact")
    if tax:
        lines.extend(["## Tax implications", "", _safe_str(tax), ""])

    min_lump = mf.get("min_investment_amount")
    min_sip = mf.get("min_sip_investment")
    if min_lump or min_sip:
        lines.extend(["## Minimum investment", ""])
        if min_sip:
            lines.append(f"Minimum SIP: ₹{min_sip}")
        if min_lump:
            lines.append(f"Minimum lumpsum: ₹{min_lump}")
        lines.append("")

    risk = None
    for stat in mf.get("stats") or []:
        if stat.get("risk"):
            risk = stat["risk"]
            break
    if not risk:
        risk = mf.get("nfo_risk")
    if risk:
        lines.extend(["## Risk", "", f"Riskometer: {_safe_str(risk)}", ""])

    benchmark = mf.get("benchmark") or mf.get("benchmark_name")
    if benchmark:
        lines.extend(["## Benchmark", "", f"Benchmark: {_safe_str(benchmark)}", ""])

    managers = mf.get("fund_manager_details") or []
    if managers:
        lines.extend(["## Fund management", ""])
        for mgr in managers:
            block = _format_manager_block(mgr)
            if block.strip():
                lines.append(block)
                lines.append("")
    elif mf.get("fund_manager"):
        lines.extend(
            [
                "## Fund management",
                "",
                f"Fund manager: {_safe_str(mf.get('fund_manager'))}",
                "",
            ]
        )

    objective = mf.get("description")
    if objective:
        lines.extend(["## Investment objective", "", _safe_str(objective), ""])

    return "\n".join(lines).strip() + "\n"


def build_raw_json_payload(
    mf: dict[str, Any],
    *,
    scheme: Scheme,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    """Wrap Groww server data with fetch metadata for ``data/raw/*.json``."""
    return {
        "scheme_id": scheme.scheme_id,
        "scheme_name": scheme.scheme_name,
        "source_url": scheme.source_url,
        "fetched_at": fetched_at or _utc_now_iso(),
        "groww": mf,
    }


def extract_groww_json(html: str) -> dict[str, Any]:
    """Parse ``__NEXT_DATA__`` from a Groww mutual-fund HTML page."""
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        raise ValueError("Groww page missing __NEXT_DATA__ (layout may have changed)")
    data = json.loads(match.group(1))
    mf = data.get("props", {}).get("pageProps", {}).get("mfServerSideData")
    if not mf:
        raise ValueError("Groww page missing mfServerSideData")
    return mf


def fetch_scheme_html(
    scheme: Scheme,
    *,
    client: httpx.Client | None = None,
    max_retries: int = _FETCH_MAX_RETRIES,
    backoff_base_sec: float = _FETCH_BACKOFF_BASE_SEC,
) -> str:
    """HTTP GET scheme page HTML with backoff on transient errors (IG-01)."""
    owns_client = client is None
    if owns_client:
        client = httpx.Client(
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
            timeout=30.0,
        )
    try:
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = client.get(scheme.source_url)
                response.raise_for_status()
                body = response.text
                if not body.strip():
                    raise ValueError("IG-04: empty fetch body")
                return body
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                code = exc.response.status_code
                if code in _RETRYABLE_STATUS and attempt < max_retries - 1:
                    delay = backoff_base_sec ** attempt
                    logger.warning(
                        "Fetch %s HTTP %s; retry %d/%d in %.1fs",
                        scheme.scheme_id,
                        code,
                        attempt + 1,
                        max_retries,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise
            except (httpx.TransportError, ValueError) as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    delay = backoff_base_sec ** attempt
                    logger.warning(
                        "Fetch %s error %s; retry %d/%d in %.1fs",
                        scheme.scheme_id,
                        exc,
                        attempt + 1,
                        max_retries,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise
        if last_exc:
            raise last_exc
        raise FetchError(f"fetch failed for {scheme.scheme_id}")
    finally:
        if owns_client:
            client.close()


def write_raw_artifacts(
    scheme: Scheme,
    *,
    html: str,
    mf: dict[str, Any],
    markdown: str,
    raw_dir: Path | None = None,
    fetched_at: str | None = None,
) -> RawArtifacts:
    """Write ``{scheme_id}.html``, ``.json``, and ``.md`` under ``data/raw/``."""
    paths = raw_paths(scheme.scheme_id, raw_dir)
    paths.html.parent.mkdir(parents=True, exist_ok=True)

    paths.html.write_text(html, encoding="utf-8")
    payload = build_raw_json_payload(mf, scheme=scheme, fetched_at=fetched_at)
    paths.json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths.markdown.write_text(markdown, encoding="utf-8")

    logger.info(
        "Wrote raw artifacts for %s: html, json, md",
        scheme.scheme_id,
    )
    return paths


def fetch_scheme_to_raw(
    scheme: Scheme,
    *,
    raw_dir: Path | None = None,
    client: httpx.Client | None = None,
) -> RawArtifacts:
    """Fetch one scheme and save HTML, JSON, and markdown to ``data/raw/``."""
    html = fetch_scheme_html(scheme, client=client)
    mf = extract_groww_json(html)
    md = groww_data_to_markdown(mf, scheme=scheme)
    return write_raw_artifacts(scheme, html=html, mf=mf, markdown=md, raw_dir=raw_dir)


def fetch_all_schemes(
    *,
    raw_dir: Path | None = None,
    delay_sec: float = _FETCH_DELAY_SEC,
) -> dict[str, RawArtifacts]:
    """
    Fetch all five registry schemes into ``data/raw/{scheme_id}.{html,json,md}``.

    IG-13: waits ``delay_sec`` between requests.
    """
    out_dir = raw_dir or DEFAULT_RAW_DIR
    written: dict[str, RawArtifacts] = {}

    with httpx.Client(
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
        timeout=30.0,
    ) as client:
        schemes = get_all_schemes()
        for i, scheme in enumerate(schemes):
            if i > 0 and delay_sec > 0:
                time.sleep(delay_sec)
            try:
                written[scheme.scheme_id] = fetch_scheme_to_raw(
                    scheme, raw_dir=out_dir, client=client
                )
            except Exception as exc:
                logger.error("Failed to fetch %s: %s", scheme.scheme_id, exc)
                raise FetchError(
                    f"IG-02: fetch failed for {scheme.scheme_id} "
                    f"({len(written)}/{len(schemes)} succeeded): {exc}"
                ) from exc

    if len(written) != len(schemes):
        raise FetchError(
            f"IG-02: partial fetch {len(written)}/{len(schemes)}; keeping previous index"
        )

    return written
