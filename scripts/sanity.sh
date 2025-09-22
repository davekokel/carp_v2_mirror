#!/usr/bin/env bash
set -euo pipefail
export PGHOST=${PGHOST:-127.0.0.1} PGPORT=${PGPORT:-54322} PGUSER=${PGUSER:-postgres} PGDATABASE=${PGDATABASE:-postgres} PGSSLMODE=${PGSSLMODE:-disable}

echo "== object counts =="
psql -Atc "select 'tables',count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE'
union all select 'views',count(*) from information_schema.views where table_schema='public' order by 1"

echo "== known views exist? =="
psql -Atc "select
  to_regclass('public.v_fish_overview_v1') is not null as v_fish_overview_v1,
  to_regclass('public.v_plasmid_treatments') is not null as v_plasmid_treatments,
  to_regclass('public.v_rna_treatments') is not null as v_rna_treatments,
  to_regclass('public.v_dye_treatments') is not null as v_dye_treatments"
