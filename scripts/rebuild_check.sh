#!/usr/bin/env bash
set -euo pipefail

PORT=${1:-5435}
DB=carp_rebuild
URL="postgresql://postgres:postgres@127.0.0.1:${PORT}/${DB}?sslmode=disable"
ADMIN_URL="postgresql://postgres:postgres@127.0.0.1:${PORT}/postgres?sslmode=disable"

docker rm -f carp_pg >/dev/null 2>&1 || true
docker run -d --name carp_pg -e POSTGRES_PASSWORD=postgres -p ${PORT}:5432 supabase/postgres:15.1.1.71 >/dev/null

until psql "$ADMIN_URL" -Atc "select 1" >/dev/null 2>&1; do sleep 1; done

psql "$ADMIN_URL" -c "drop database if exists ${DB} with (force)"
psql "$ADMIN_URL" -c "create database ${DB}"

psql "$URL" -v ON_ERROR_STOP=1 -c "create schema if not exists pgsodium"
psql "$URL" -v ON_ERROR_STOP=1 -c "create extension if not exists pgsodium with schema pgsodium"

psql "$URL" -v ON_ERROR_STOP=1 -c "DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN CREATE ROLE app_rw NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rr') THEN CREATE ROLE app_rr NOLOGIN; END IF;
END $$;"

cp supabase/migrations/00000000_baseline.sql /tmp/_baseline_supapg.sql
sed -i '' -E '/^SET (statement_timeout|lock_timeout|idle_in_transaction_session_timeout|transaction_timeout)/d' /tmp/_baseline_supapg.sql
psql "$URL" -v ON_ERROR_STOP=1 -f /tmp/_baseline_supapg.sql

for f in $(ls -1 supabase/migrations/*.sql | sort | sed '1d'); do
  psql "$URL" -v ON_ERROR_STOP=1 -f "$f"
done

psql "$URL" -Atc "select viewname from pg_views where schemaname='public' order by 1"
