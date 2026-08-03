#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"
source .venv/bin/activate
export PYTHONPATH="$ROOT/backend"
exec uvicorn app.main:app --host 127.0.0.1 --port 1690 --reload
