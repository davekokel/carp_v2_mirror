#!/usr/bin/env bash
set -euo pipefail

# Only fail for ACTUAL query usage (FROM/JOIN/INSERT/UPDATE … public.<table>)
# Ignore archives and anything that isn't .py or .sql.
rg -n -P \
  --glob '!carp_app/ui/_archive_pages/**' \
  --glob '!**/_archive/**' \
  --glob '!**/_archive_*/**' \
  --type-add 'py:*.py' --type-add 'sql:*.sql' -tpy -tsql \
  '(?i)\b(from|join|insert\s+into|update)\s+public\.(fish_tank_memberships|clutch_plan_treatments)\b' \
  carp_app supabase \
  && { echo "❌ legacy refs found"; exit 1; } \
  || echo "✅ no legacy refs in active code"