#!/usr/bin/env bash
set -euo pipefail
MSG="${1:-fix}"
FILE="${2:-}"

cd "$(git rev-parse --show-toplevel)"

psql "$DB_URL" -v ON_ERROR_STOP=1 -c "
create table if not exists public._applied_sql_files(
  name text primary key,
  applied_at timestamptz default now()
);"

apply_one() {
  f="$1"
  n="$(basename "$f")"
  hit=$(psql "$DB_URL" -Atqc "select 1 from public._applied_sql_files where name='$n' limit 1" || true)
  [ "$hit" = "1" ] && return 0
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -c "insert into public._applied_sql_files(name) values ('$n') on conflict do nothing;"
}

if [ -n "$FILE" ]; then
  apply_one "$FILE"
fi

mkdir -p supabase/snapshots/staging
ts=$(date -u +%Y%m%d_%H%M%S)
snap="supabase/snapshots/staging/${ts}_staging_schema_after_fix.sql"
pg_dump --schema-only --no-owner --no-privileges "$DB_URL" > "$snap"

git add -A
git commit -m "$MSG"
git push
echo "$snap"
