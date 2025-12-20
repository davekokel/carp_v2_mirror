# Legacy wrangling v3 pipeline from raw (strict)

## Goal
A single reproducible pipeline that starts from **raw** inputs and generates **derived** outputs for:
- legacy imaging annotations (v9-style CSVs)
- clutch memberships
- clutch genotypes + treatments
- ROI overview rollups downstream

Key invariant:
- **pSWIN04 / pSWIN05 must not propagate** into any derived outputs unless they truly exist in raw.  
  If they appear, the pipeline is leaking non-raw mapping data and must be fixed.

---

## Source-of-truth folders

### Raw (inputs only; do not hand-edit)
`seed_kits/legacy_wrangling_v2/raw/`

Must contain (minimum):
- `Unique_parent_names__mom_dad_combined__preview_dqm.xlsx`
- `Unique_injected_rna__preview_dqm.xlsx`
- `Unique_injected_plasmid__preview_dqm.xlsx`
- `experiment_hole_patch_v7.csv`

### Derived working (generated artifacts; safe to overwrite)
- `seed_kits/legacy_wrangling_v2/working/`
- `seed_kits/legacy_wrangling_v3/working/`

---

## Why pSWIN04/pSWIN05 showed up before
They were introduced by a **derived parent-map CSV** (`...preview_dqm_v5.csv`) that was mistakenly treated like raw.
That file encoded mappings like:
- `"from Swinburne lab - tank ID 344 ..."` → `pSWIN04`
- `"ef1a:2xLynk:tdm:Halo"` → `pSWIN05`

But the raw XLSX mapping for those names should map to `pSWIN01` (or other canonical basecodes), not pSWIN04/05.

So: **do not use the v5 CSV** as an input to enrichment.  
Always derive the parent-map CSV directly from the raw XLSX each run.

---

## Canonical pipeline entrypoint
Run:
- `scripts/legacy_v3_run_from_raw.sh`

This script enforces:
1) raw preconditions exist
2) derive a parent map CSV from raw XLSX into:
   `seed_kits/legacy_wrangling_v2/working/Unique_parent_names__mom_dad_combined__preview_dqm_from_raw.csv`
3) run `seed_kits/legacy_wrangling_v3/scripts/02_enrich.py`
4) hard check: derived outputs contain **no pSWIN04/05**
5) load memberships + genotypes + treatments + treated_clutches_v11
6) print a DB QC summary

---

## Derived outputs (expected)

### v3 working
- `seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_v9.csv`
- `seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_for_db_v9.csv`

### v2 working (derived helper)
- `seed_kits/legacy_wrangling_v2/working/Unique_parent_names__mom_dad_combined__preview_dqm_from_raw.csv`

---

## Minimal verification commands
After a successful run:

Check that forbidden codes did not propagate:
- `rg -n -i 'pswin[\- ]?0?4|pswin[\- ]?0?5' seed_kits/legacy_wrangling_v3/working/*.csv`

Check DB treatment linkage state:
- `psql "$DB_URL" -x -c "SELECT count(*) FROM public.join_clutch_treatments;"`
- `psql "$DB_URL" -x -c "SELECT count(*) FROM public.treated_clutches_v11;"`

---

## If the invariant fails (pSWIN04/05 reappears)
Do NOT patch downstream tables/views.

Instead, debug the earliest step where the code enters:
1) confirm raw XLSX does not contain pSWIN04/05 for the affected parent names
2) confirm the generated `...preview_dqm_from_raw.csv` does not contain pSWIN04/05
3) confirm `02_enrich.py` is reading `PARENT_MAP_XLSX` (raw) and writing the derived CSV, not reading any `*_v5.csv`
4) re-run the pipeline
