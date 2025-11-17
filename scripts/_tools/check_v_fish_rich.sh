#!/usr/bin/env bash
set -euo pipefail
: "${DB_URL:?set DB_URL first}"
cols_expected=("fish_uuid" "fish_code" "fish_name" "fish_nickname" "genetic_background" "line_building_stage" "date_birth" "n_active_tanks" "allele_number" "allele_code" "transgene_pretty" "genotype_rollup" "created_at")
mapfile -t cols_actual < <(psql "$DB_URL" -Atc "select column_name from information_schema.columns where table_schema='public' and table_name='v_fish_rich' order by ordinal_position")
missing=()
for c in "${cols_expected[@]}"; do
  found=0; for a in "${cols_actual[@]}"; do [[ "$a" == "$c" ]] && found=1 && break; done
  (( found==0 )) && missing+=("$c")
done
if (( ${#missing[@]} )); then
  echo "Missing columns in v_fish_rich: ${missing[*]}"; exit 1
fi
psql "$DB_URL" -Atc "select count(*) as fish_rows from public.v_fish_rich"
psql "$DB_URL" -Atc "select fish_code, fish_name, fish_nickname, allele_code, transgene_pretty, genotype_rollup, n_active_tanks from public.v_fish_rich order by fish_code limit 10"
echo "v_fish_rich OK"
