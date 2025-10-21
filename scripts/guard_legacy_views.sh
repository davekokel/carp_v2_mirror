#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
bad=$(rg -n "v_fish_overview_all|v_fish_overview\b|v_fish_standard_clean|v_clutches_overview_final\b|v_clutches_overview\b|v_cross_concepts_overview\b|vw_" \
  -g '!supabase/migrations/_archive**' \
  -g '!supabase/migrations/_archive_legacy**' \
  -g '!supabase/migrations/_archive_all**' \
  -g '!carp_app/ui/_archive_pages/**' \
  -g '!**/.venv/**' -g '!**/.git/**' || true)
[ -z "$bad" ] || { echo "$bad"; echo "❌ legacy view reference found"; exit 1; }
echo "✅ no legacy view references in active code"
