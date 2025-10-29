#!/usr/bin/env bash
set -euo pipefail
: "${DB_URL:?DB_URL is required}"

echo "────────────────────────────────────────────"
echo "🧱 Rebuilding database from migrations: postgres"
echo "────────────────────────────────────────────"

# Fresh public schema
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "drop schema if exists public cascade;"
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "create schema public;"
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "alter schema public owner to postgres;"
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "grant usage on schema public to anon, authenticated, service_role;"
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "create extension if not exists \"uuid-ossp\";"
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "create extension if not exists pgcrypto;"

# Apply all migrations in order
ls supabase/migrations/*.sql | sort | xargs -I{} psql "$DB_URL" -v ON_ERROR_STOP=1 -f {}

psql "$DB_URL" -Atc "select 'tables', count(*) from information_schema.tables where table_schema='public'"
psql "$DB_URL" -Atc "select 'views', count(*) from information_schema.views where table_schema='public'"
