"""Phase 1.6 — chunking tests."""

from pathlib import Path

import pytest

from ingestion.chunk import (
    PREFIX_TEMPLATE,
    Chunk,
    chunk_scheme,
    format_prefix,
)
from ingestion.parse import parse_document

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_MID_CAP = FIXTURES / "sample_mid_cap.md"


@pytest.fixture
def mid_cap_parsed():
    raw = SAMPLE_MID_CAP.read_text(encoding="utf-8")
    return parse_document(raw, scheme_id="hdfc-mid-cap")


class TestPrefixTemplate:
    def test_format_prefix(self) -> None:
        text = format_prefix("HDFC Mid Cap Fund", "costs", "Expense ratio: 0.78%")
        assert text == PREFIX_TEMPLATE.format(
            scheme_name="HDFC Mid Cap Fund",
            section="costs",
            content="Expense ratio: 0.78%",
        )
        assert text.startswith("Scheme: HDFC Mid Cap Fund | Section: costs |")


class TestChunkScheme:
    def test_chunk_ids_and_metadata(self, mid_cap_parsed) -> None:
        chunks = chunk_scheme(mid_cap_parsed)
        assert len(chunks) >= 8
        for c in chunks:
            assert isinstance(c, Chunk)
            assert c.chunk_id.startswith(f"{c.scheme_id}:{c.section}:")
            assert c.scheme_id == "hdfc-mid-cap"
            assert c.source_url.startswith("https://groww.in/mutual-funds/")
            assert c.text.startswith(f"Scheme: {c.scheme_name} | Section: {c.section} |")

    def test_single_chunk_metric_sections(self, mid_cap_parsed) -> None:
        chunks = chunk_scheme(mid_cap_parsed)
        costs = [c for c in chunks if c.section == "costs"]
        assert len(costs) == 1
        assert "0.78%" in costs[0].content

    def test_fund_management_block_intact(self, mid_cap_parsed) -> None:
        fm = [c for c in chunk_scheme(mid_cap_parsed) if c.section == "fund_management"]
        assert len(fm) == 1
        assert "Fund manager" in fm[0].content
        assert "Also manages" in fm[0].content
        assert "John Doe" in fm[0].text

    def test_fund_management_splits_multiple_managers(self, mid_cap_parsed) -> None:
        mid_cap_parsed.sections["fund_management"] = (
            "Fund manager: Alice\nExperience: 10 years\n\n"
            "Fund manager: Bob\nExperience: 8 years\nAlso manages: Other Fund"
        )
        fm = [c for c in chunk_scheme(mid_cap_parsed) if c.section == "fund_management"]
        assert len(fm) == 2
        assert "Alice" in fm[0].content
        assert "Bob" in fm[1].content

    def test_exit_load_one_chunk(self, mid_cap_parsed) -> None:
        el = [c for c in chunk_scheme(mid_cap_parsed) if c.section == "exit_load"]
        assert len(el) == 1
