#!/usr/bin/env bash
set -euo pipefail
MSG="${1:-fix: sticky change}"
cd "$(git rev-parse --show-toplevel)"
find supabase/migrations -type f -name '*.sql' -print0 | sort -z | xargs -0 -n1 -I{} psql "$DB_URL" -v ON_ERROR_STOP=1 -f "{}"
scripts/guard_db.sh
mkdir -p supabase/snapshots/staging
ts=$(date -u +%Y%m%d_%H%M%S)
snap="supabase/snapshots/staging/${ts}_staging_schema_after_fix.sql"
pg_dump --schema-only --no-owner --no-privileges "$DB_URL" > "$snap"
git add -A
git commit -m "$MSG"
git push
echo "$snap"
