# HDFC Mutual Fund FAQ Assistant (Facts-Only RAG)



Facts-only FAQ assistant for five HDFC schemes on Groww. See [docs/problemStatement.md](docs/problemStatement.md) and [docs/implementation-plan.md](docs/implementation-plan.md).



## Phase 0 — Setup (complete)



```powershell

cd MUTUAL-FUND-RAG-CHATBOT

python -m venv .venv

.venv\Scripts\pip install -r requirements-phase0.txt

.venv\Scripts\python -m pytest tests/test_config.py -v

```



## Phase 1 — Parsing, sectioning & chunking (complete)



Sectioning + chunking strategy: [docs/implementation-plan.md § Phase 1](docs/implementation-plan.md#phase-1--corpus-parsing-sectioning--chunking).



```powershell

.venv\Scripts\pip install httpx

python scripts/fetch_raw.py

python scripts/build_corpus.py       # writes data/corpus/ and data/chunks/

python scripts/validate_parse.py

python -m pytest tests/test_parse.py tests/test_corpus.py tests/test_fetch.py tests/test_chunk.py tests/test_phase1_gate.py -v

```



## Phase 2 — Embedding & Chroma index (complete)

Uses **BGE-small** (local) + **ChromaDB**. See [implementation-plan.md § Phase 2](docs/implementation-plan.md#phase-2--embedding--vector-index).

```powershell
pip install -r requirements.txt
copy .env.example .env
python scripts/build_index.py --reset
python scripts/smoke_retrieve.py
python -m pytest tests/test_embed.py tests/test_ingestion.py tests/test_phase2_gate.py -v
```

Copy `.env.example` to `.env` before Phase 2. **Embeddings default to free local BGE** (`sentence-transformers`); Phase 5 chat uses **Groq** (`GROQ_API_KEY`). `OPENAI_API_KEY` is only for optional paid OpenAI embeddings.



**Full stack** (Phase 2+): `pip install -r requirements.txt` (Chroma 1.x ships prebuilt Windows wheels; no C++ build tools needed).



## Phase 3 — Query classifier & compliance (complete)

Rule-based classifier runs **before** retrieval. See [implementation-plan.md § Phase 3](docs/implementation-plan.md#phase-3--query-classifier--compliance).

```powershell
python -m pytest tests/test_classifier.py -v
```

Classes: `ADVISORY`, `PERFORMANCE_COMPARE`, `PII`, `OUT_OF_CORPUS`, `FACTUAL`. Refusals include AMFI/SEBI educational links from config.

## Phase 4 — Retriever (complete)

Scheme filter, section boost, BGE thresholds, `[CONTEXT]` assembly. See [implementation-plan.md § Phase 4](docs/implementation-plan.md#phase-4--retriever--context-assembly).

```powershell
python -m pytest tests/test_retriever.py -v
```

## Phase 5 — RAG backend & API (complete)

`app/rag/backend.py` runs classify → retrieve → generate → validate. FastAPI: `POST /api/chat`, `GET /api/health`, `GET /api/schemes`. Template answers work without `GROQ_API_KEY`; set the key for Groq LLM generation.

```powershell
python -m pytest tests/test_golden.py -v
python scripts/smoke_chat.py --template
uvicorn app.main:app --reload --port 8000
# or: python scripts/run_api.py --reload
```

## Phase 6 — Chat UI (complete)

Fintech-style UI in `ui/` (from `stitch Design/`). Served at `http://localhost:8000/` when the API runs.

```powershell
python scripts/build_index.py --reset   # if needed
uvicorn app.main:app --reload --port 8000
# Open http://127.0.0.1:8000/ — welcome, 3 example chips, sticky disclaimer, chat
python -m pytest tests/test_ui_static.py tests/test_golden.py -v
```

Features: `POST /api/chat`, loading state, refusal (amber) vs answer (green) cards, escaped HTML, Groww citations in a new tab, empty send disabled.

## Phase 7 — Daily ingestion pipeline (complete)

`run_daily.py`: fetch → parse → chunk → index; lock under `data/ingest/`; first build uses staging + atomic swap; re-runs rebuild in-place when a live index exists; keeps previous index on failure. See [implementation-plan.md § Phase 7](docs/implementation-plan.md#phase-7--daily-ingestion-pipeline).

```powershell
# Offline (uses existing data/raw/ or uploads/)
python -m ingestion.run_daily --skip-fetch

# Full daily job (network fetch all 5 Groww pages)
python -m ingestion.run_daily

python -m pytest tests/test_phase7_daily.py -v
```

Optional dev reindex: set `ADMIN_REINDEX_TOKEN` in `.env`, then `POST /api/admin/reindex` with header `X-Admin-Token`.

## Phase 8 — Daily scheduler (complete)

Daily refresh at **10:00 AM IST** (`INGEST_CRON_SCHEDULE=0 10 * * *`, `INGEST_TIMEZONE=Asia/Kolkata`). External scheduler calls `scripts/reindex.sh` → `python -m ingestion.run_daily`. See [scheduler/README.md](scheduler/README.md) and [implementation-plan.md § Phase 8](docs/implementation-plan.md#phase-8--daily-scheduler).

```powershell
# Manual smoke (scheduler path)
bash scripts/reindex.sh --skip-fetch

# OS cron: copy scheduler/cron.example into crontab (set CRON_TZ=Asia/Kolkata)
# K8s: scheduler/k8s-cronjob.example.yaml
# GitHub Actions: .github/workflows/daily-ingest.yml (04:30 UTC = 10:00 IST)

python -m pytest tests/test_phase8_scheduler.py -v
```

## Phase 9 — Tests (complete)

Full golden / edge-case coverage, production hardening (rate limits, CORS, admin lockdown), and CI. See [implementation-plan.md § Phase 9](docs/implementation-plan.md#phase-9--tests).

```powershell
# Full suite (build index first if vector_store/ is empty)
python scripts/build_index.py --reset   # if needed
python -m pytest -v
# or gate script:
powershell -File scripts/run_tests.ps1
```

Production settings in `.env`: `APP_ENV=production`, `CHAT_RATE_LIMIT_PER_MINUTE=30` (or rely on prod default), `CORS_ORIGINS=https://your-ui.example`, `ADMIN_REINDEX_ENABLED=false`.

## Phase 10 — Documentation & deployment (planned)

README, deployment guide, optional Docker, fellowship demo checklist. See [implementation-plan.md § Phase 10](docs/implementation-plan.md#phase-10--documentation--deployment).

## Project layout



```text

app/config.py       # Scheme registry, aliases, settings
app/main.py         # FastAPI entry (Phase 5)
app/api/routes.py   # /api/chat, /api/health, /api/schemes
app/rag/            # classifier, retriever, generator, validator, backend

ingestion/          # fetch, parse, corpus, chunk, embed, index

data/raw/           # Per scheme: .html, .json, .md (fetched)
data/corpus/        # Per scheme: .json, .md, .html (parsed sections)
data/chunks/        # Per scheme: .json, .md + all_chunks.json (Phase 1 chunks)
vector_store/       # ChromaDB persistence (Phase 2, gitignored)

scripts/            # build_index, reindex.sh, run_tests (Phase 8–9)
scheduler/          # cron.example, K8s CronJob, scheduler README

tests/              # pytest suites

docs/               # Problem statement, architecture, plan

```



## Disclaimer



Facts-only. No investment advice.

