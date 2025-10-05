#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DB_URL:-}" ]]; then
  echo "Usage: DB_URL=postgresql://user:pass@host:port/db?sslmode=... scripts/apply_migrations.sh"
  exit 1
fi

echo "Applying migrations to: $DB_URL"
for f in supabase/migrations/*.sql; do
  echo "  → $f"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f"
done
echo "✅ Done"
