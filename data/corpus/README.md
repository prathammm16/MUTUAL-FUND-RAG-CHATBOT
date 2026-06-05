# Parsed corpus (`data/corpus/`)

Per scheme (`{scheme_id}`), three files:

| File | Contents |
|------|----------|
| `{scheme_id}.json` | Structured sections (input for Phase 1 chunking) |
| `{scheme_id}.md` | Human-readable cleaned corpus |
| `{scheme_id}.html` | Simple HTML view of the same sections |

## Build from raw

```powershell
python scripts/build_corpus.py
python scripts/validate_parse.py
```

Or fetch + build in one step:

```powershell
python scripts/validate_parse.py --build
```
