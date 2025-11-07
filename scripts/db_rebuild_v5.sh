#!/usr/bin/env bash
set -euo pipefail

. scripts/use_db.sh
use_local
echo "DB_URL=$DB_URL"

psql "$DB_URL" -v ON_ERROR_STOP=1 -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"

for f in \
  supabase/migrations/00000001_compat_digest_text_wrapper.sql \
  supabase/migrations/20251106_000000_core_fish_baseline.sql \
  supabase/migrations/20251106_000020_upsert_fish_by_identity.sql \
  supabase/migrations/20251106_000010_v4_views.sql \
  supabase/migrations/20251106_000100_tanks_baseline.sql \
  supabase/migrations/20251106_000200_plasmids_fusions_baseline.sql
do
  echo ">> $f"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f"
done

tables=$(psql "$DB_URL" -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")
views=$(psql "$DB_URL" -Atc "SELECT count(*) FROM pg_views WHERE schemaname='public';")

echo "tables|$tables"
echo "views|$views"
