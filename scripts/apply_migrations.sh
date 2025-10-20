#!/usr/bin/env bash
set -euo pipefail

DB_URL="${DB_URL:-}"
if [ -z "$DB_URL" ]; then
  echo "DB_URL not set"; exit 1
fi

psql "$DB_URL" -v ON_ERROR_STOP=1 -c "
create table if not exists public.migrations_applied (
  filename text primary key,
  applied_at timestamptz default now()
);
"

echo "Applying migrations to: $DB_URL"

# Sorted, space-safe iteration
find supabase/migrations -type f -name '*.sql' -print0 | sort -z | while IFS= read -r -d '' f; do
  b="$(basename "$f")"
  already="$(psql "$DB_URL" -Atqc "select 1 from public.migrations_applied where filename='$b'" || true)"
  if [ "$already" = "1" ]; then
    echo "  • skip $b"
    continue
  fi
  echo "  → $b"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -c "insert into public.migrations_applied(filename) values ('$b')"
done
