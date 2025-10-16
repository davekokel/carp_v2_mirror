#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec env -i PATH="$PATH" HOME="$HOME" bash -lc '
  set -a
  . ./.env.staging.direct
  set +a
  exec .venv/bin/APP_COMMIT=103df8d streamlit run carp_app/ui/streamlit_app.py
'
