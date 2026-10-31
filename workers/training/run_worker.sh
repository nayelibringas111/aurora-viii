#!/usr/bin/env bash
# Ejecuta el worker de entrenamiento en tu computadora contra la base de Supabase (alternativa gratuita
# al Background Worker de Render). Requiere Python 3.12 y un archivo .env con DATABASE_URL, SUPABASE_URL,
# SUPABASE_SECRET_KEY y STORAGE_BACKEND=supabase.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r services/api/requirements.txt -r workers/training/requirements.txt
set -a; [ -f workers/training/.env ] && . workers/training/.env; set +a
export PYTHONPATH="$ROOT/services/api:$ROOT/workers/training"
exec python -m aurora_worker
