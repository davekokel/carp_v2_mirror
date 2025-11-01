#!/usr/bin/env bash
set -euo pipefail
: "${DB_URL:?DB_URL is required}"

echo "────────────────────────────────────────────"
echo "🧱 Rebuilding database from migrations: postgres"
echo "────────────────────────────────────────────"

# 1) Drop public, then let the BASELINE create it (it contains CREATE SCHEMA public)
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "drop schema if exists public cascade;"

# 2) Baseline first (creates schema/tables/views/functions/triggers)
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "CREATE SCHEMA IF NOT EXISTS public;"
psql "$DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/00000000_baseline.sql

# 3) Idempotent extensions / grants (OK if baseline already did them)
psql "$DB_URL" -v ON_ERROR_STOP=1 -c 'create extension if not exists "uuid-ossp";'
psql "$DB_URL" -v ON_ERROR_STOP=1 -c 'create extension if not exists pgcrypto;'
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "grant usage on schema public to anon, authenticated, service_role;"

# 4) Everything else in timestamp order (excluding the baseline)
find supabase/migrations -maxdepth 1 -type f -name '*.sql' ! -name '00000000_baseline.sql' \
  | sort | while read f; do
    psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f"
  done

# 5) Summary
psql "$DB_URL" -Atc "select 'tables', count(*) from information_schema.tables where table_schema='public'"
psql "$DB_URL" -Atc "select 'views', count(*) from information_schema.views where table_schema='public'"
