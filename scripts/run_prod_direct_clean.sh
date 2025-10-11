#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec env -i PATH="$PATH" HOME="$HOME" bash -lc '
  set -a
  . ./.env.prod.direct
  set +a
  exec .venv/bin/streamlit run supabase/ui/streamlit_app.py
'
