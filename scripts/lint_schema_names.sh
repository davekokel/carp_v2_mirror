#!/usr/bin/env bash
set -euo pipefail
bad=$(psql "$DB_URL" -Atc "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' AND table_name ~ '^link_'")
if [ -n "$bad" ]; then
  echo "Disallowed table names (use join_*):"
  echo "$bad"
  exit 1
fi
echo "OK"
