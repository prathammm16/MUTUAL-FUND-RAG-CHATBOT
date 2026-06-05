"""Phase 1.7 — chunk store persistence tests."""

from pathlib import Path

from ingestion.chunk_store import (
    build_chunks_from_corpus,
    chunk_from_dict,
    chunk_to_dict,
    load_all_chunks,
    write_all_chunks,
)
from ingestion.parse import parse_document

SAMPLE = Path(__file__).parent / "fixtures" / "sample_mid_cap.md"


def test_chunk_round_trip_dict() -> None:
    parsed = parse_document(SAMPLE.read_text(encoding="utf-8"), scheme_id="hdfc-mid-cap")
    chunks = build_chunks_from_corpus({"hdfc-mid-cap": parsed})
    data = chunk_to_dict(chunks[0])
    restored = chunk_from_dict(data)
    assert restored.chunk_id == chunks[0].chunk_id


def test_write_and_load_all_chunks(tmp_path: Path) -> None:
    parsed = parse_document(SAMPLE.read_text(encoding="utf-8"), scheme_id="hdfc-mid-cap")
    chunks = build_chunks_from_corpus({"hdfc-mid-cap": parsed})
    write_all_chunks(chunks, tmp_path)
    loaded = load_all_chunks(tmp_path)
    assert len(loaded) == len(chunks)
