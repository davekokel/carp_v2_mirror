#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
set -a
[ -f .env.staging.pooler ] && source .env.staging.pooler
set +a
exec streamlit run "$(rg --files -n -g 'carp_app/ui/**/streamlit_app.py' | head -n1)" --server.headless=true --server.port=8501
