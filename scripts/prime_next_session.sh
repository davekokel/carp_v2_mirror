#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
[ -f .venv/bin/activate ] && . .venv/bin/activate
echo "DB_URL=${DB_URL:-}"
psql "$DB_URL" -Atc "select inet_server_addr(), current_user"
psql "$DB_URL" -Atc "
select table_name, data_type
from information_schema.columns
where table_schema='public'
  and column_name='tank_id'
  and table_name in ('tanks','fish_tank_assignments','tank_status_history')
order by table_name"
psql "$DB_URL" -Atc "
select to_regclass('public.v_tanks'),
       to_regclass('public.v_tanks_current_status'),
       to_regclass('public.v_plasmids')"
