#!/usr/bin/env bash
set -euo pipefail
: "${DB_URL:?DB_URL is required}"

echo "────────────────────────────────────────────"
echo "🧱 Rebuilding database from migrations: STAGING"
echo "────────────────────────────────────────────"

HAS_BASE=$(psql "$DB_URL" -Atc "select case when to_regclass('public.fish') is not null then 1 else 0 end;")

if [ "${SKIP_BASELINE:-0}" = "1" ]; then
  :
elif [ "$HAS_BASE" = "0" ]; then
  psql "$DB_URL" -v ON_ERROR_STOP=1 -c "create schema if not exists public;"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/00000000_baseline.sql
fi

psql "$DB_URL" -v ON_ERROR_STOP=1 -c 'create extension if not exists "uuid-ossp";'
psql "$DB_URL" -v ON_ERROR_STOP=1 -c 'create extension if not exists pgcrypto;'
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "grant usage on schema public to anon, authenticated, service_role;"

if [ -n "${START_FROM:-}" ]; then
  files=$(printf "%s\n" supabase/migrations/*.sql | LC_ALL=C sort | awk -v s="$START_FROM" 'f||$0~s{f=1; if ($0!~"00000000_baseline.sql") print}')
else
  files=$(printf "%s\n" supabase/migrations/*.sql | LC_ALL=C sort | awk '$0!~"00000000_baseline.sql"{print}')
fi

last=""
set +e
while IFS= read -r f; do
  [ -z "$f" ] && continue
  echo "$f"
  last="$f"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f" || { echo "FAILED: $last"; exit 1; }
done <<< "$files"
set -e

psql "$DB_URL" -Atc "select 'tables', count(*) from information_schema.tables where table_schema='public'"
psql "$DB_URL" -Atc "select 'views', count(*) from information_schema.views where table_schema='public'"