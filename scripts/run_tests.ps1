# Phase 9 — local CI gate (build index if missing, then full pytest)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (Test-Path ".env") { Get-Content ".env" | ForEach-Object { } } # dotenv via pydantic at runtime

$python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

$store = if ($env:VECTOR_STORE_PATH) { $env:VECTOR_STORE_PATH } else { "vector_store" }
if (-not (Test-Path $store) -or -not (Get-ChildItem $store -ErrorAction SilentlyContinue)) {
    Write-Host "Building vector index at $store ..."
    & $python scripts/build_index.py --reset
}

& $python -m pytest -v @args
