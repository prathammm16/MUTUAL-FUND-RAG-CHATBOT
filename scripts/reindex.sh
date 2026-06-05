#!/usr/bin/env bash
# Cron-safe wrapper for Phase 7 daily ingestion (Phase 8).
# Invokes: python -m ingestion.run_daily
#
# Usage (manual smoke):
#   bash scripts/reindex.sh
#   bash scripts/reindex.sh --skip-fetch
#
# Exit codes: 0 success, 1 pipeline failure, 2 skipped (flock / overlap)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi

LOG_DIR="${INGEST_LOG_DIR:-$PROJECT_ROOT/logs}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/reindex-$(date -u +%Y%m%d).log"

if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  PYTHON="$(command -v python)"
fi

LOCK_FILE="${INGEST_FLOCK_FILE:-$PROJECT_ROOT/data/ingest/.cron.flock}"
mkdir -p "$(dirname "$LOCK_FILE")"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "$(date -Is) SKIPPED: another reindex holds flock (PH7-05)" >>"$LOG_FILE"
  exit 2
fi

echo "=== $(date -Is) reindex start cwd=$PROJECT_ROOT python=$PYTHON ===" >>"$LOG_FILE"

set +e
"$PYTHON" -m ingestion.run_daily "$@" >>"$LOG_FILE" 2>&1
status=$?
set -e

echo "=== $(date -Is) reindex finished exit=$status ===" >>"$LOG_FILE"
if [ "$status" -ne 0 ]; then
  echo "--- reindex log ($LOG_FILE) ---" >&2
  cat "$LOG_FILE" >&2 || true
fi
exit "$status"
