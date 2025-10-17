#!/usr/bin/env bash
set -euo pipefail
unset PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE
export DB_URL="postgresql://postgres.zebzrvjbalhazztvhhcm@aws-1-us-west-1.pooler.supabase.com:6543/postgres?sslmode=require"
export POOLER_AUTOREWRITE=1
exec streamlit run "carp_app/ui/pages/000_👋_welcome.py"
