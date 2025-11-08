#!/usr/bin/env bash
set -euo pipefail

. scripts/use_db.sh
use_local

echo "🔁 Dropping and recreating local database..."
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"

echo "🚀 Applying v6 baseline migration..."
psql "$DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/20251108_144757_baseline_v6.sql

echo "✅ Rebuild complete — schema ready (no seeds)."
