#!/usr/bin/env bash
set -euo pipefail
: "${DB_URL:?DB_URL not set}"

DB_NAME="$(printf '%s\n' "$DB_URL" | sed -E 's#^.*/([^/?]+).*#\1#')"

dropdb --if-exists "$DB_NAME"
createdb "$DB_NAME"

psql "$DB_URL" -Atc 'create extension if not exists pgcrypto; create extension if not exists "uuid-ossp";'

echo "────────────────────────────────────────────────────────────"
echo "🧱 Rebuilding local database: $DB_NAME"
echo "────────────────────────────────────────────────────────────"

ok=true
warn=false

for f in $(ls -1 supabase/migrations/*.sql | sort); do
  base="$(basename "$f")"
  if [[ "$base" == "00000000_baseline.sql" ]]; then
    continue
  fi

  echo ">> $base"
  out=$(psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f" 2>&1) || {
    echo -e "❌ Migration failed: $base"
    echo "$out"
    ok=false
    break
  }

  if echo "$out" | grep -Eq "NOTICE|WARNING"; then
    warn=true
  fi
done

echo
if [ "$ok" = true ] && [ "$warn" = false ]; then
  echo "✅ Rebuild completed successfully."
elif [ "$ok" = true ] && [ "$warn" = true ]; then
  echo "⚠️  Rebuild completed with warnings (check NOTICE/WARNING lines)."
else
  echo "❌ Rebuild encountered errors."
  exit 1
fi

echo
echo "🧩 Table counts:"
psql "$DB_URL" -Atc "
  SELECT 'tanks',count(*) FROM public.tanks UNION ALL
  SELECT 'tank_pairs',count(*) FROM public.tank_pairs UNION ALL
  SELECT 'fish_pairs',count(*) FROM public.fish_pairs UNION ALL
  SELECT 'cross_instances',count(*) FROM public.cross_instances UNION ALL
  SELECT 'clutch_instances',count(*) FROM public.clutch_instances;" |
  awk -F'|' '{printf "   %-18s %s\n",$1,$2}'

echo
echo "🧩 View counts:"
psql "$DB_URL" -Atc "
SELECT 'v_tank_pairs',             CASE WHEN to_regclass('public.v_tank_pairs') IS NULL THEN 'MISSING' ELSE (SELECT count(*)::text FROM public.v_tank_pairs) END
UNION ALL
SELECT 'v_cross_clutch_instances', CASE WHEN to_regclass('public.v_cross_clutch_instances') IS NULL THEN 'MISSING' ELSE (SELECT count(*)::text FROM public.v_cross_clutch_instances) END
UNION ALL
SELECT 'v_clutch_instances',       CASE WHEN to_regclass('public.v_clutch_instances') IS NULL THEN 'MISSING' ELSE (SELECT count(*)::text FROM public.v_clutch_instances) END
UNION ALL
SELECT 'v_rna_plasmids',           CASE WHEN to_regclass('public.v_rna_plasmids') IS NULL THEN 'MISSING' ELSE (SELECT count(*)::text FROM public.v_rna_plasmids) END;" \
| awk -F'|' '{printf "   %-28s %s\n",$1,$2}'

echo
if [ "$ok" = true ] && [ "$warn" = false ]; then
  echo "✅  Rebuild complete — clean and green."
elif [ "$ok" = true ]; then
  echo "⚠️   Rebuild completed with warnings."
else
  echo "❌  Rebuild failed — check above errors."
fi