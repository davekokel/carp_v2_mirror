#!/usr/bin/env bash
set -euo pipefail
export DB_URL="${DB_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}"
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; CREATE EXTENSION IF NOT EXISTS pgcrypto;"
( cd supabase/migrations && awk 'NF && $1 !~ /^#/' POST_FREEZE_APPLY_ORDER.txt | while read -r f; do
  echo ">> $f"; psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f";
done )
echo "OK: migrations applied."
