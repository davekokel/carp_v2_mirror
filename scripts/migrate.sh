#!/usr/bin/env bash
set -euo pipefail

# Require standard PG env vars; PGPASSWORD is read by psql from the environment.
: "${PGHOST:?}"; : "${PGPORT:?}"; : "${PGDATABASE:?}"; : "${PGUSER:?}"; : "${PGPASSWORD:?}"

# IMPORTANT: no password= here; psql reads PGPASSWORD from env
PSQL_CONN="host=${PGHOST} port=${PGPORT} dbname=${PGDATABASE} user=${PGUSER} sslmode=${PGSSLMODE:-require}"

run_file() {
  local f="$1"
  echo "==> applying: $f"
  psql "$PSQL_CONN" -v ON_ERROR_STOP=1 -f "$f"
}

if [[ $# -gt 0 ]]; then
  run_file "$1"
else
  shopt -s nullglob
  files=(migrations/*.sql)
  IFS=$'\n' read -rd '' -a files_sorted < <(printf '%s\n' "${files[@]}" | sort && printf '\0')
  for f in "${files_sorted[@]}"; do
    run_file "$f"
  done
fi

echo "✅ Done."
