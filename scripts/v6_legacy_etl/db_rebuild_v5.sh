#!/usr/bin/env bash
set -euo pipefail

. "$(dirname "$0")/use_db.sh"
use_local
echo "DB_URL=$DB_URL"

psql "$DB_URL" -v ON_ERROR_STOP=1 -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"

while IFS= read -r -d '' f; do
  echo ">> $f"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f"
done < <(
  find "supabase/migrations" -maxdepth 1 -type f -name '*.sql' \
    ! -name '*.bak' ! -name '*.sql.bak' ! -name '*.sql.disabled' \
    ! -name '*~' ! -path '*/_archive/*' -print0 | sort -z
)

tables=$(psql "$DB_URL" -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")
views=$(psql "$DB_URL" -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='VIEW';")
echo "tables|$tables"
echo "views|$views"