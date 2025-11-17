#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
bad=$(rg -n "v_fish_overview_all|v_fish_overview\b|v_fish_standard_clean|v_clutches_overview_final\b|v_clutches_overview\b|v_cross_concepts_overview\b|vw_" \
  -g '!**/.venv/**' \
  -g '!**/.git/**' \
  -g '!supabase/migrations/**' \
  -g '!priming/**' \
  -g '!_dbscan_*' \
  -g '!archive/**' \
  -g '!SCHEMA_INVENTORY.md' \
  -g '!scripts/guard_legacy_views.sh' || true)
[ -z "$bad" ] || { echo "$bad"; echo "❌ legacy view reference found"; exit 1; }
echo "✅ no legacy view references in active code"
