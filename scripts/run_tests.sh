#!/usr/bin/env bash
# Phase 9 — local CI gate (build index if missing, then full pytest)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
elif [[ -f "$PROJECT_ROOT/.env.example" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env.example"
  set +a
fi

if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  PYTHON="$(command -v python)"
fi

STORE="${VECTOR_STORE_PATH:-vector_store}"
if [[ ! -d "$PROJECT_ROOT/$STORE" ]] || [[ -z "$(ls -A "$PROJECT_ROOT/$STORE" 2>/dev/null || true)" ]]; then
  echo "Building vector index at $STORE ..."
  "$PYTHON" scripts/build_index.py --reset
fi

exec "$PYTHON" -m pytest -v "$@"
