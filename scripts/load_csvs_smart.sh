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

get_table_cols() {
  local tbl="$1"
  psql "$DB_URL" -Atqc "
    select column_name
    from information_schema.columns
    where table_schema='public' and table_name='${tbl}'
    order by ordinal_position
  "
}

esc_ident() {
  printf '%s' "$1" | sed 's/\"/\"\"/g'
}

mapfile -t FILES < <(find "$CSV_DIR" -maxdepth 1 -type f -name '*.csv' | sort)
if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "No CSV files in $CSV_DIR"
  exit 0
fi

{
  echo "BEGIN;"
  echo "SET client_min_messages = WARNING;"

  for f in "${FILES[@]}"; do
    base="$(basename "$f")"
    table="$(echo "$base" | sed -E 's/^[0-9]+_//; s/\.csv$//')"

    IFS=, read -r -a hdr < <(head -n 1 "$f")
    for i in "${!hdr[@]}"; do
      hdr[$i]="$(echo "${hdr[$i]}" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"
    done

    mapfile -t tblcols < <(get_table_cols "$table" || true)
    if [[ ${#tblcols[@]} -eq 0 ]]; then
      echo "\\echo ⚠️  public.$table does not exist in DB — skipping $base"
      continue
    fi

    intersect=()
    for col in "${tblcols[@]}"; do
      for h in "${hdr[@]}"; do
        if [[ "$col" == "$h" ]]; then intersect+=("$col"); break; fi
      done
    done
    if [[ ${#intersect[@]} -eq 0 ]]; then
      echo "\\echo ⚠️  No matching columns between $base and public.$table — skipping"
      continue
    fi

    missing_req=$(psql "$DB_URL" -Atqc "
      with req as (
        select column_name
        from information_schema.columns
        where table_schema='public' and table_name='${table}'
          and is_nullable='NO' and column_default is null
      )
      select string_agg(column_name, ',')
      from req
      where column_name not in ($(printf "'%s'," "${hdr[@]}" | sed 's/,$//'))
    " || true)
    if [[ -n "${missing_req:-}" ]]; then
      echo "\\echo ⚠️  $base → public.$table is missing NOT NULL columns w/o defaults: ${missing_req}"
    fi

    cols_joined=$(printf '"%s",' "${intersect[@]}" | sed 's/,$//')
    echo "\\echo → $base → public.$table (${#intersect[@]} cols)"
    f_sql="${f//\'/''}"
    echo "\\copy public.\"$(esc_ident "$table")\"($cols_joined) from '$f_sql' with (format csv, header true)"
  done

  echo "COMMIT;"
} | psql "$DB_URL" -v ON_ERROR_STOP=1
