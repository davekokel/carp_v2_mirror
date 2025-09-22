#!/usr/bin/env bash
set -euo pipefail

CSV_DIR="${1:-}"
DB_URL="${2:-${LOCAL_DB_URL:-}}"

if [[ -z "$CSV_DIR" || -z "$DB_URL" ]]; then
  echo "Usage: $0 /path/to/csv/folder [DB_URL]"
  echo "  (or set LOCAL_DB_URL in your env)"
  exit 1
fi

if [[ ! -d "$CSV_DIR" ]]; then
  echo "❌ Folder not found: $CSV_DIR"
  exit 1
fi

echo "Loading from: $CSV_DIR"
echo "Database: ${DB_URL%%@*}@…"

# list CSVs
mapfile -t FILES < <(find "$CSV_DIR" -maxdepth 1 -type f -name '*.csv' | sort)
if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "No CSV files in $CSV_DIR"
  exit 0
fi

# Build one psql script
{
  echo "BEGIN;"
  echo "SET client_min_messages = WARNING;"

  for f in "${FILES[@]}"; do
    base="$(basename "$f")"
    core="$(echo "$base" | sed -E 's/^[0-9]+_//; s/\.csv$//')"   # e.g. fish, fish_links_has_transgenes
    raw_table="raw.${core}_csv"

    # sanity: ensure table exists
    echo "\\echo → $base → ${raw_table}"
    echo "create table if not exists ${raw_table} ();"

    f_sql="${f//\'/''}"
    echo "\\copy ${raw_table} from '$f_sql' with (format csv, header true)"
  done

  echo "COMMIT;"
} | psql "$DB_URL" -v ON_ERROR_STOP=1
