#!/usr/bin/env bash
set -euo pipefail
: "${DB_URL:?DB_URL not set}"
DB_NAME="$(printf '%s\n' "$DB_URL" | sed -E 's/^.*\/([^/?]+).*$/\1/')"

dropdb --if-exists "$DB_NAME"
createdb "$DB_NAME"
psql "$DB_URL" -Atc 'create extension if not exists pgcrypto; create extension if not exists "uuid-ossp";'

for f in 20 20 12 61 79 80 81 701 33 98 100 204 250 395 398 399 400printf "%s
" supabase/migrations/*.sql | rg -v "00000000_baseline\.sql" | sort); do
  psql "" -v ON_ERROR_STOP=1 -f ""
done

psql "$DB_URL" -v ON_ERROR_STOP=1 <<'SQL'
drop function if exists public.raise_exception(text);
create function public.raise_exception(msg text)
returns int
language plpgsql
as $fn$
begin
  raise exception '%', msg;
  return 0;
end;
$fn$;
SQL

psql "$DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/20251027_094500_v_tank_pairs_and_trigger.sql
psql "$DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/20251027_094824_v_tank_pairs_and_trigger_fix.sql
psql "$DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/20251026_083110_view_v_cross_clutch_instances.sql
psql "$DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/20251027_105316_view_v_clutch_instances_min_contract.sql
psql "$DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/20251027_110818_view_v_rna_plasmids_filter.sql

psql "$DB_URL" -Atc "select to_regclass('public.v_tank_pairs'), to_regclass('public.v_cross_clutch_instances'), to_regclass('public.v_clutch_instances'), to_regclass('public.v_rna_plasmids')"