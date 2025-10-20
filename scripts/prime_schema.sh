#!/usr/bin/env bash
set -euo pipefail
ENV_LABEL=staging
URL="${STAGING_DB_URL:-${DB_URL:-}}"
if [ -z "${URL}" ]; then echo "Set STAGING_DB_URL or DB_URL to your staging DSN"; exit 1; fi
TS="$(date +%Y%m%d_%H%M%S)"
OUTDIR="priming/${ENV_LABEL}_schema_${TS}"
mkdir -p "$OUTDIR"

pg_dump -s -d "$URL" -f "$OUTDIR/schema.sql"

psql "$URL" -c "\\copy (select schemaname, tablename from pg_tables where schemaname='public' order by 1,2) to stdout with csv header" > "$OUTDIR/tables.csv"

psql "$URL" -c "\\copy (
  select table_schema, table_name, ordinal_position, column_name, data_type, is_nullable, column_default
  from information_schema.columns
  where table_schema='public'
  order by table_name, ordinal_position
) to stdout with csv header" > "$OUTDIR/columns.csv"

psql "$URL" -c "\\copy (
  select schemaname as view_schema, viewname as view_name
  from pg_views
  where schemaname='public'
  order by viewname
) to stdout with csv header" > "$OUTDIR/views.csv"

psql "$URL" -A -t -c "
  select 'create or replace view '||quote_ident(schemaname)||'.'||quote_ident(viewname)||' as '||pg_get_viewdef((quote_ident(schemaname)||'.'||quote_ident(viewname))::regclass, true)||';'
  from pg_views
  where schemaname='public'
  order by viewname
" > "$OUTDIR/views.sql"

psql "$URL" -c "\\copy (
  select trigger_schema, event_object_table as table_name, trigger_name, action_timing, string_agg(event_manipulation, '+') as events
  from information_schema.triggers
  where trigger_schema='public'
  group by trigger_schema, event_object_table, trigger_name, action_timing
  order by event_object_table, trigger_name
) to stdout with csv header" > "$OUTDIR/triggers.csv"

psql "$URL" -A -t -c "
  select pg_get_functiondef(p.oid)
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public'
  order by n.nspname, p.proname
" > "$OUTDIR/functions.sql"

printf "Environment: %s\nTimestamp: %s\nURL: %s\nFiles:\n- schema.sql\n- tables.csv\n- columns.csv\n- views.csv\n- views.sql\n- triggers.csv\n- functions.sql\n" "$ENV_LABEL" "$TS" "$URL" > "$OUTDIR/README.txt"

cd "priming"
zip -r "priming_${ENV_LABEL}_schema_${TS}.zip" "$(basename "$OUTDIR")"
echo "Created: priming/priming_${ENV_LABEL}_schema_${TS}.zip"