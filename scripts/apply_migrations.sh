#!/usr/bin/env bash
set -euo pipefail
: "${DB_URL:?set DB_URL first}"

# Run only top-level migration .sql files (ignore subfolders like _to_delete/)
# Sort by name so timestamped files run in order.
while IFS= read -r -d '' f; do
  case "$f" in
    supabase/migrations/_to_delete/*) continue ;;
    supabase/migrations/*/*)          continue ;;
  esac
  echo "  → $f"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f"
done < <(find supabase/migrations -maxdepth 1 -type f -name '*.sql' -print0 | sort -z)
