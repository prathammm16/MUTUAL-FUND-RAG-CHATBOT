# Daily scheduler (Phase 8)

External scheduler invokes the Phase 7 pipeline via [`scripts/reindex.sh`](../scripts/reindex.sh).

## Schedule

| Setting | Value | Meaning |
|---------|-------|---------|
| `INGEST_CRON_SCHEDULE` | `0 10 * * *` | 10:00 AM daily |
| `INGEST_TIMEZONE` | `Asia/Kolkata` | Indian Standard Time (IST) |

Configure these in `.env` (see [`.env.example`](../.env.example)).

## Entrypoint

```bash
bash scripts/reindex.sh              # full fetch + parse + chunk + index
bash scripts/reindex.sh --skip-fetch   # offline / CI (existing data/raw/)
```

The wrapper:

- `cd`s to the repository root (PH10-04)
- Loads `.env` when present
- Uses `.venv/bin/python` when available
- Appends logs to `logs/reindex-YYYYMMDD.log` (override with `INGEST_LOG_DIR`)
- Uses `flock` on `data/ingest/.cron.flock` before calling `run_daily.py` (PH7-05)
- Relies on Phase 7 ingest lock inside `ingestion/run_daily.py` (SK-07)

Exit codes: `0` success, `1` pipeline error, `2` skipped (overlap).

## OS cron (Linux / macOS)

See [`cron.example`](./cron.example). Set `CRON_TZ=Asia/Kolkata` so the job runs at **10:00 AM IST** even when the host uses UTC (SK-06).

```bash
chmod +x scripts/reindex.sh
crontab -e   # paste lines from cron.example with your project path
```

## Kubernetes

See [`k8s-cronjob.example.yaml`](./k8s-cronjob.example.yaml). Use `concurrencyPolicy: Forbid` so overlapping pods do not run (SK-07).

## GitHub Actions

[`.github/workflows/daily-ingest.yml`](../.github/workflows/daily-ingest.yml) runs on `30 4 * * *` UTC (= 10:00 AM IST). Forks need repository secrets for optional keys (SK-08); use `workflow_dispatch` for manual runs without cron.

## Manual smoke (exit gate)

```powershell
bash scripts/reindex.sh --skip-fetch
# or: python -m ingestion.run_daily --skip-fetch
```

Full README cron section is completed in Phase 10.
