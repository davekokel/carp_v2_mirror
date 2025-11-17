#!/usr/bin/env bash
set -euo pipefail
ts=$(date -u +%Y%m%d_%H%M%S)
slug="${1:-migration}"
file="supabase/migrations/${ts}_${slug}.sql"
touch "$file"
echo "$file"
