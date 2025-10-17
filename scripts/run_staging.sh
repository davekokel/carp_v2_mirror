#!/usr/bin/env bash
set -euo pipefail
unset PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE
export POOLER_AUTOREWRITE=0
export DB_URL="postgresql://postgres@db.zebzrvjbalhazztvhhcm.supabase.co:5432/postgres?sslmode=require"
exec streamlit run carp_app/ui/streamlit_app.py
