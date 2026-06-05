# Raw corpus (`data/raw/`)

Per scheme (`{scheme_id}`), three files:

| File | Contents |
|------|----------|
| `{scheme_id}.html` | Full Groww page HTML (as fetched) |
| `{scheme_id}.json` | Extracted Groww `mfServerSideData` + fetch metadata |
| `{scheme_id}.md` | Markdown used by the parse/import pipeline |

`uploads/` overrides `data/raw/` for the same `scheme_id` when both exist.

## Populate

```powershell
python scripts/fetch_raw.py
```

Then build parsed corpus:

```powershell
python scripts/build_corpus.py
python scripts/validate_parse.py
```

You can also add hand-exported `.md` files only; re-run `fetch_raw.py` to refresh HTML and JSON.
