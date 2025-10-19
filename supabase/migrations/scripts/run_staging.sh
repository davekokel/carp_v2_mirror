#!/usr/bin/env bash
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
[ -f "$ROOT/.env.staging" ] && set -a && . "$ROOT/.env.staging" && set +a
[ -z "${DB_URL:-}" ] && [ -f "$ROOT/.env.staging.direct" ] && set -a && . "$ROOT/.env.staging.direct" && set +a
export PYTHONUNBUFFERED=1
cd "$ROOT"
python3 -m streamlit run supabase/ui/streamlit_app.py
