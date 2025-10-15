#!/usr/bin/env bash
set -euo pipefail
CID=carp_pg_norm
docker rm -f "$CID" >/dev/null 2>&1 || true
docker run -d --name "$CID" -p 55432:5432 -e POSTGRES_PASSWORD=postgres postgres:16 >/dev/null
echo -n "waiting for postgres"
for i in {1..60}; do
  if PGPASSWORD=postgres psql -h localhost -p 55432 -U postgres -d postgres -Atc "select 1" >/dev/null 2>&1; then
    echo " ✓"
    break
  fi
  echo -n "."
  sleep 1
done
export PGPASSWORD=postgres
URL="postgresql://postgres@localhost:55432/postgres"
psql "$URL" -v ON_ERROR_STOP=1 -f supabase/migrations/00000001_util_mig_helpers.sql
psql "$URL" -v ON_ERROR_STOP=1 -f supabase/migrations/00000002_audit_primitives.sql
psql "$URL" -v ON_ERROR_STOP=1 -f supabase/migrations/00000003_roles_min.sql
psql "$URL" -v ON_ERROR_STOP=1 -f supabase/migrations/00000004_app_roles.sql
psql "$URL" -v ON_ERROR_STOP=1 -f supabase/migrations/00000000_baseline_v2.sql
for f in $(ls -1 supabase/migrations/2025*.sql 2>/dev/null || true); do
  echo "Applying $f"
  psql "$URL" -v ON_ERROR_STOP=1 -f "$f"
done
echo "local migration PASS"
