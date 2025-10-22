#!/usr/bin/env bash
set -euo pipefail
psql "$DB_URL" -v ON_ERROR_STOP=1 -Atc "
select 'tanks', data_type from information_schema.columns
 where table_schema='public' and table_name='tanks' and column_name='tank_id';
select 'fta', data_type from information_schema.columns
 where table_schema='public' and table_name='fish_tank_assignments' and column_name='tank_id';
select 'tsh', data_type from information_schema.columns
 where table_schema='public' and table_name='tank_status_history' and column_name='tank_id';
"
psql "$DB_URL" -v ON_ERROR_STOP=1 -Atc "
select coalesce(to_regclass('public.v_tanks')::text,'MISSING'),
       coalesce(to_regclass('public.v_tanks_current_status')::text,'MISSING'),
       coalesce(to_regclass('public.v_plasmids')::text,'MISSING');
"
