#!/usr/bin/env bash
set -euo pipefail

: "${DB_URL:?DB_URL not set}"

DB_NAME="$(printf '%s\n' "$DB_URL" | sed -E 's#^.*/([^/?]+).*#\1#')"

dropdb --if-exists "$DB_NAME"
createdb "$DB_NAME"

psql "$DB_URL" -Atc 'create extension if not exists pgcrypto; create extension if not exists "uuid-ossp";'

# Apply all migrations strictly by filename (excluding the cloud baseline)
for f in $(ls -1 supabase/migrations/*.sql | sort); do
  base="$(basename "$f")"
  if [ "$base" = "00000000_baseline.sql" ]; then
    continue
  fi
  echo ">> $base"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f"
done

# Quick sanity
psql "$DB_URL" -Atc "select to_regclass('public.v_tank_pairs'), to_regclass('public.v_cross_clutch_instances'), to_regclass('public.v_clutch_instances'), to_regclass('public.v_rna_plasmids')"
