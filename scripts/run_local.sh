#!/usr/bin/env bash
set -euo pipefail
env -u PGUSER -u PGPASSWORD -u PGHOST -u PGPORT -u PGDATABASE \
  DB_URL="${LOCAL_DB_URL}" PYTHONPATH="$(pwd)" \
  streamlit run carp_app/ui/streamlit_app.py
