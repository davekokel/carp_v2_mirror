#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
. ./.env.staging.direct
set +a
exec .venv/bin/streamlit run carp_app/ui/streamlit_app.py
