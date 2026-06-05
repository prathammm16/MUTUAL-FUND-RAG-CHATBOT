"""Phase 2.1 — index metadata tests (chunks built in Phase 1)."""

import pytest

from ingestion.chunk import (
    Chunk,
    ChunkValidationError,
    chunk_scheme,
    dedupe_chunks,
    validate_chunk,
    validate_chunks,
)
from ingestion.index import COLLECTION_NAME, chunk_to_metadata
from ingestion.parse import parse_document

MID_CAP_URL = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
SAMPLE = __import__("pathlib").Path(__file__).parent / "fixtures" / "sample_mid_cap.md"


@pytest.fixture
def sample_chunks():
    raw = SAMPLE.read_text(encoding="utf-8")
    parsed = parse_document(raw, scheme_id="hdfc-mid-cap")
    return chunk_scheme(parsed)


class TestChunkMetadata:
    def test_chunk_to_metadata_has_required_keys(self, sample_chunks) -> None:
        chunk = sample_chunks[0]
        meta = chunk_to_metadata(chunk, ingested_at="2025-06-05")
        for key in (
            "chunk_id",
            "scheme_id",
            "scheme_name",
            "source_url",
            "section",
            "last_updated",
        ):
            assert key in meta
        assert meta["scheme_id"] == "hdfc-mid-cap"
        assert meta["ingested_at"] == "2025-06-05"

    def test_collection_name(self) -> None:
        assert COLLECTION_NAME == "hdfc_groww_corpus"


class TestChunkValidation:
    def test_validate_allowlisted_url(self, sample_chunks) -> None:
        validate_chunks(sample_chunks)

    def test_reject_missing_source_url(self, sample_chunks) -> None:
        bad = Chunk(
            chunk_id="x:costs:0",
            scheme_id="hdfc-mid-cap",
            scheme_name="HDFC Mid Cap Fund Direct Growth",
            source_url="",
            section="costs",
            content="x",
            text="Scheme: x | Section: costs | x",
        )
        with pytest.raises(ChunkValidationError, match="source_url"):
            validate_chunk(bad)

    def test_reject_non_allowlisted_url(self, sample_chunks) -> None:
        c = sample_chunks[0]
        bad = Chunk(
            chunk_id=c.chunk_id,
            scheme_id=c.scheme_id,
            scheme_name=c.scheme_name,
            source_url="https://example.com/fund",
            section=c.section,
            content=c.content,
            text=c.text,
        )
        with pytest.raises(ChunkValidationError, match="allowlisted"):
            validate_chunk(bad)


class TestDedupe:
    def test_dedupe_identical_text(self, sample_chunks) -> None:
        dup = Chunk(
            chunk_id="hdfc-mid-cap:costs:99",
            scheme_id="hdfc-mid-cap",
            scheme_name=sample_chunks[0].scheme_name,
            source_url=MID_CAP_URL,
            section="costs",
            content=sample_chunks[0].content,
            text=sample_chunks[0].text,
        )
        merged = dedupe_chunks(sample_chunks + [dup])
        assert len(merged) == len(sample_chunks)
