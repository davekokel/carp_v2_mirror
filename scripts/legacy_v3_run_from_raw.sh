#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[STEP 0] Preconditions"
test -f seed_kits/legacy_wrangling_v2/raw/Unique_parent_names__mom_dad_combined__preview_dqm.xlsx
test -f seed_kits/legacy_wrangling_v2/raw/Unique_injected_rna__preview_dqm.xlsx
test -f seed_kits/legacy_wrangling_v2/raw/Unique_injected_plasmid__preview_dqm.xlsx
test -f seed_kits/legacy_wrangling_v2/raw/experiment_hole_patch_v7.csv
test -f seed_kits/legacy_wrangling_v3/working/output_from_linking_v5.csv

echo "[STEP 1] Derive parent map CSV from raw XLSX"
python - <<'PY'
import pandas as pd, pathlib
xlsx = pathlib.Path("seed_kits/legacy_wrangling_v2/raw/Unique_parent_names__mom_dad_combined__preview_dqm.xlsx")
out  = pathlib.Path("seed_kits/legacy_wrangling_v2/working/Unique_parent_names__mom_dad_combined__preview_dqm_from_raw.csv")
out.parent.mkdir(parents=True, exist_ok=True)
df = pd.read_excel(xlsx, dtype=str)
df.to_csv(out, index=False)
print("WROTE", out)
PY

echo "[STEP 2] Run legacy v3 enrich (raw → v9 CSVs)"
python -u seed_kits/legacy_wrangling_v3/scripts/02_enrich.py

echo "[STEP 3] Invariant check: pSWIN04 / pSWIN05 must not appear"
if rg -n -i 'pswin[\- ]?0?4|pswin[\- ]?0?5' \
  seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_for_db_v9.csv \
  seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_v9.csv
then
  echo "ERROR: pSWIN04/05 detected in derived outputs"
  exit 1
else
  echo "OK: no pSWIN04/05 detected"
fi

echo "[STEP 4] Load imaging clutch memberships (v9)"
python -u scripts/v9_load_imaging_clutch_memberships_from_v9.py \
  --csv seed_kits/legacy_wrangling_v3/working/legacy_clutch_memberships_v9.csv || true

echo "[STEP 5] Seed legacy genotypes from enriched ROI CSV"
python -u scripts/v11_seed_legacy_genotypes_from_enriched_roi.py \
  --csv seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_for_db_v9.csv

echo "[STEP 6] Link legacy clutches to treatments (v9→v10 inference)"
python -u scripts/v11_link_legacy_clutches_to_treatments_from_v9.py \
  --annotations-csv seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_for_db_v9.csv \
  --clutches-csv seed_kits/legacy_wrangling_v3/working/legacy_clutches_v9.csv \
  --treatments-csv seed_kits/2025-11-15-121231-autoload/treatments_v10.csv

echo "[STEP 7] Frontfill treated_clutches_v11 + memberships"
python -u scripts/v11_frontfill_imaging_clutch_memberships_treated.py

echo "[STEP 8] DB QC summary"
psql "$DB_URL" -x -c "
SELECT
  (SELECT count(*) FROM public.clutches) AS n_clutches,
  (SELECT count(*) FROM public.clutches WHERE genotype_v11_id IS NOT NULL) AS n_with_genotype,
  (SELECT count(*) FROM public.join_clutch_treatments) AS n_join_clutch_treatments,
  (SELECT count(*) FROM public.treated_clutches_v11) AS n_treated_clutches_v11,
  (SELECT count(*) FROM public.v_roi_overview) AS n_rois,
  (SELECT count(*) FROM public.v_roi_overview WHERE treated_clutch_code IS NOT NULL) AS n_treated_rois;
"

echo "[DONE] legacy v3 pipeline completed successfully"
