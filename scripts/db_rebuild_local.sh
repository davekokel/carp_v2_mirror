#!/usr/bin/env bash
set -euo pipefail
: "${DB_URL:?DB_URL is required}"

DB_NAME="$(printf '%s\n' "$DB_URL" | sed -E 's#\?.*$##; s#.*/##')"
ADMIN_URL="$(printf '%s\n' "$DB_URL" | sed -E "s#/${DB_NAME}(\\?|$|$)#/postgres\\1#")"

echo "────────────────────────────────────────────────────────────"
echo "🧱 Rebuilding local database from migrations: $DB_NAME"
echo "────────────────────────────────────────────────────────────"

# Drop and recreate the database every time
psql "$ADMIN_URL" -Atc "select pg_terminate_backend(pid)
  from pg_stat_activity where datname='${DB_NAME}' and pid<>pg_backend_pid();" || true
psql "$ADMIN_URL" -v ON_ERROR_STOP=1 -c "drop database if exists \"${DB_NAME}\";"
psql "$ADMIN_URL" -v ON_ERROR_STOP=1 -c "create database \"${DB_NAME}\";"

# Run every migration file in lexical order
for f in $(ls -1 supabase/migrations/*.sql | LC_ALL=C sort); do
  printf '>> %s\n' "$(basename "$f")"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f"
done

echo "✅ Database now exactly reflects supabase/migrations"