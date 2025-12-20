# Legacy wrangling v3 — canonical pipeline from RAW → DB

## Goal
One deterministic pipeline that starts from:
- seed_kits/legacy_wrangling_v2/raw/
- seed_kits/2025-11-15-121231-autoload/

…and produces:
- seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_v9.csv
- seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations_for_db_v9.csv
- DB rows (clutches, memberships, genotypes, treatments, treated_clutches) with strict QC.

If anything is missing, we FAIL with a machine-readable report (no silent fallbacks).

## Canonical inputs
### RAW
- seed_kits/legacy_wrangling_v2/raw/Unique_parent_names__mom_dad_combined__preview_dqm.xlsx
- seed_kits/legacy_wrangling_v2/raw/Unique_injected_rna__preview_dqm.xlsx
- seed_kits/legacy_wrangling_v2/raw/Unique_injected_plasmid__preview_dqm.xlsx
- seed_kits/legacy_wrangling_v2/raw/experiment_hole_patch_v7.csv
- seed_kits/legacy_wrangling_v3/working/output_from_linking_v5.csv

### AUTOLOAD
- seed_kits/2025-11-15-121231-autoload/constructs_plasmid.csv
- seed_kits/2025-11-15-121231-autoload/treatments_v10.csv
- seed_kits/2025-11-15-121231-autoload/tags.xlsx
- seed_kits/2025-11-15-121231-autoload/alias.csv

## Canonical pipeline order
1) Enrich ROI annotations from raw maps (no derived CSVs as source-of-truth)
   - runner: seed_kits/legacy_wrangling_v3/scripts/02_enrich.py
   - output: legacy_imaging_annotations_v9.csv + legacy_imaging_annotations_for_db_v9.csv

2) Load clutches (strict) from v9 clutches CSV
   - runner: scripts/loader_legacy_clutches.py
   - output: public.clutches rows (legacy_imaging batch)

3) Load imaging_clutch_memberships from v9 memberships CSV
   - runner: scripts/v9_load_imaging_clutch_memberships_from_v9.py

4) Link legacy clutches to treatments (strict) using v9 annotations + treatments_v10.csv
   - runner: scripts/v11_link_legacy_clutches_to_treatments_from_v9.py
   - output: join_clutch_treatments rows

5) Seed treated_clutches_v11 + backfill imaging_clutch_memberships.treated_clutch_id
   - runner: scripts/v11_frontfill_imaging_clutch_memberships_treated.py
   - output: treated_clutches_v11 rows + treated_clutch_id backfilled

6) Seed/assign genotypes to clutches (STRICT; deterministic evidence only)
   - primary: parents-based (from clutches CSV parent fields via parent_map)
   - secondary: ROI genotype basecodes (from enriched csv) ONLY if present
   - NO fallbacks (no “casper”, no guessing)
   - output: clutches.genotype_v11_id

## Hard rules / invariants (must be enforced)
- The pipeline must be runnable end-to-end with a single command.
- Any “derived” mapping file must live under /working, never /raw.
- Base codes must be normalized consistently (e.g., pDQM082 → pdqm-82 if that’s the constructs table convention).
- If a clutch has imaging membership, it must either:
  - have genotype_v11_id assigned from deterministic evidence, OR
  - be reported as a strict failure with the exact reason and the ROI paths involved.
- pswin04/pswin05 must not appear unless present in RAW (and if present, must map deterministically to the intended canonical construct codes).
