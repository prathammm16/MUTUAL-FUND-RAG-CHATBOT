# Chunk store (`data/chunks/`)

Phase 1 output: embeddable units derived from `data/corpus/*.json`.

| File | Contents |
|------|----------|
| `{scheme_id}.json` | Chunk list + metadata for one scheme |
| `{scheme_id}.md` | Human-readable chunk listing |
| `all_chunks.json` | All schemes combined (used by Phase 2 index) |

## Build

```powershell
python scripts/build_corpus.py   # also writes chunks by default
# or
python scripts/build_chunks.py
python scripts/validate_parse.py
```

Chunking rules: see [implementation-plan.md § Phase 1](../docs/implementation-plan.md#phase-1--corpus-parsing-sectioning--chunking).
