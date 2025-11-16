#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
DIR="${1:-$ROOT/seed_kits}"
DBURL="${LOCAL_DB_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres?sslmode=disable}"

if [ ! -d "$DIR" ]; then
  echo "❌ Folder not found: $DIR"
  echo "   Usage: $0 /path/to/csv/folder"
  exit 2
fi

shopt -s nullglob
mapfile -t FILES < <(find "$DIR" -type f -name '*.csv' | sort)
if ((${#FILES[@]} == 0)); then
  echo "🤷 No CSVs found under: $DIR"
  exit 0
fi

echo "→ Loading $((${#FILES[@]})) CSV file(s) from: $DIR"
echo "→ Target DB: $DBURL"
echo ""

loaded=0
skipped=0
failed=0

for f in "${FILES[@]}"; do
  base="$(basename "$f")"
  # Derive table name:
  #   - strip leading numeric chunk(s) like 01_ 10_ etc
  #   - normalize non-alphanumerics to _
  name="$(echo "${base%.*}" | sed -E 's/^([0-9]{2}_)+|^[0-9]+_?//; s/[^A-Za-z0-9_]+/_/g')"
  table="public.${name}"

  # Skip empty files
  if [ ! -s "$f" ]; then
    echo "⏭  $base (empty) — skipped"
    ((skipped++)) || true
    continue
  fi

  # Check table exists
  exists="$(psql "$DBURL" -Atqc "select to_regclass('$table') is not null" 2>/dev/null || echo f)"
  if [ "$exists" != "t" ]; then
    echo "⏭  $base → $table (table not found) — skipped"
    ((skipped++)) || true
    continue
  fi

  echo "→ \copy $table FROM '$f' CSV HEADER"
  if psql "$DBURL" -v ON_ERROR_STOP=1 -c "\copy $table from '$(pwd)/$f' csv header"; then
    ((loaded++)) || true
  else
    echo "❌  failed: $base → $table"
    ((failed++)) || true
  fi
done

echo ""
echo "== Summary =="
echo "  loaded : $loaded"
echo "  skipped: $skipped"
echo "  failed : $failed"

exit 0
