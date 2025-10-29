#!/usr/bin/env bash
set -euo pipefail
: "${DB_URL:?DB_URL is required}"

psql "$DB_URL" -v ON_ERROR_STOP=1 -Atc "select current_database(), current_user"
psql "$DB_URL" -v ON_ERROR_STOP=1 -Atc "select pg_advisory_lock(77770001)"
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "drop schema if exists public cascade;"
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "create schema public;"
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "alter schema public owner to postgres;"
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "grant usage on schema public to anon, authenticated, service_role;"
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "create extension if not exists \"uuid-ossp\";"
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "create extension if not exists pgcrypto;"

psql "$DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/00000000_baseline.sql

EXCLUDE=$(printf "%s\n" \
  supabase/migrations/00000000_baseline.sql \
  supabase/migrations/20251026_standardize_uuid_entities.sql)

comm -23 <(ls supabase/migrations/*.sql | sort) <(printf "%s\n" $EXCLUDE | sort) | xargs -I{} psql "$DB_URL" -v ON_ERROR_STOP=1 -f {}

psql "$DB_URL" -v ON_ERROR_STOP=1 -Atc "select to_regclass('public.fish'), to_regclass('public.tanks'), to_regclass('public.fish_tank_memberships'), to_regclass('public.cross_instances'), to_regclass('public.clutch_instance_treatments')"
psql "$DB_URL" -v ON_ERROR_STOP=1 -Atc "select 'tables', count(*) from information_schema.tables where table_schema='public'"
psql "$DB_URL" -v ON_ERROR_STOP=1 -Atc "select pg_advisory_unlock(77770001)"
