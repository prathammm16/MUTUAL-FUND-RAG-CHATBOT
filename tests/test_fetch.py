"""Tests for Groww fetch → raw markdown."""

import json
from pathlib import Path

from app.config import get_scheme
from ingestion.fetch import (
    RawArtifacts,
    build_raw_json_payload,
    extract_groww_json,
    groww_data_to_markdown,
    raw_paths,
    write_raw_artifacts,
)

FIXTURE_HTML = Path(__file__).parent / "fixtures" / "groww_next_data.html"


def test_groww_data_to_markdown_from_fixture() -> None:
    scheme = get_scheme("hdfc-mid-cap")
    assert scheme is not None
    mf = {
        "nav": 219.942,
        "nav_date": "04-Jun-2026",
        "expense_ratio": "0.73",
        "exit_load": "Exit load of 1% if redeemed within 1 year.",
        "min_investment_amount": 100,
        "min_sip_investment": 100,
        "benchmark": "NIFTY Midcap 150 TRI",
        "description": "Mid-cap objective text.",
        "category_info": {"tax_impact": "Tax rules apply."},
        "stats": [{"risk": "Very High"}],
        "fund_manager_details": [
            {
                "person_name": "Test Manager",
                "education": "MBA",
                "experience": "10 years",
                "funds_managed": [{"scheme_name": "Other Fund"}],
            }
        ],
    }
    md = groww_data_to_markdown(mf, scheme=scheme)
    assert scheme.source_url in md
    assert "Expense ratio: 0.73%" in md
    assert "Fund manager: Test Manager" in md
    assert "Also manages: Other Fund" in md


def test_extract_groww_json_from_html() -> None:
    payload = {"props": {"pageProps": {"mfServerSideData": {"scheme_name": "x"}}}}
    html = (
        '<html><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload)
        + "</script></html>"
    )
    mf = extract_groww_json(html)
    assert mf.get("scheme_name") == "x"


def test_write_raw_artifacts_three_files(tmp_path: Path) -> None:
    scheme = get_scheme("hdfc-mid-cap")
    assert scheme is not None
    mf = {"expense_ratio": "0.5", "description": "Test"}
    md = groww_data_to_markdown(mf, scheme=scheme)
    artifacts = write_raw_artifacts(
        scheme,
        html="<html>groww</html>",
        mf=mf,
        markdown=md,
        raw_dir=tmp_path,
        fetched_at="2025-06-05T00:00:00+00:00",
    )
    assert isinstance(artifacts, RawArtifacts)
    assert artifacts.html.is_file()
    assert artifacts.json.is_file()
    assert artifacts.markdown.is_file()
    data = json.loads(artifacts.json.read_text(encoding="utf-8"))
    assert data["scheme_id"] == scheme.scheme_id
    assert data["groww"]["expense_ratio"] == "0.5"
    assert raw_paths(scheme.scheme_id, tmp_path) == artifacts
