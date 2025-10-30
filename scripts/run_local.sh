#!/usr/bin/env bash
set -euo pipefail
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
if [ -f .env.local ]; then
  set -a; . .env.local; set +a
else
  . scripts/use_db.sh && use_local
fi
exec "$PY" -m streamlit run carp_app/ui/streamlit_app.py
