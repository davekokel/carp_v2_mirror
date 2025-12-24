# Legacy Imaging Wrangling v4 (MOSAIC) — Contract

This pipeline is intentionally modular. Each stage consumes explicit inputs and emits explicit artifacts.
Downstream stages must not reach “backwards” to read earlier-stage raw inputs directly.

## Inputs (raw, immutable)
- raw/foundation_dirs_depthN.txt
- raw/Cell Observatory - Zebrafish Development.xlsx (sheet: "Master Imaging list")
- working/experiment_roots.tsv
- working/roi_channels_by_roi_root.tsv (filesystem-derived)

## Stage A — Filesystem discovery (no workbook)
Inputs:
- raw/foundation_dirs_depthN.txt
- working/experiment_roots.tsv
- working/roi_channels_by_roi_root.tsv

Output:
- working/roi_observations.tsv

Required columns in roi_observations.tsv:
- roi_root_rel              (e.g. Aang_Foundation/20251204.../fish1_24hpf_roi1)
- roi_dir                   (absolute, clusterfs-prefixed)
- foundation_long           (Aang_Foundation|Korra_Foundation)
- foundation                (aang|korra)
- experiment_key            (e.g. 20251204_cdk_sensor_red_mem_red_nuc)
- date_key                  (YYYYMMDD)
- experiment_date           (YYYY-MM-DD)
- roi_name                  (basename)
- fish_label                (best-effort fish label)
- cams, channels, wavelengths_nm, file_exts, n_paths  (from roi_channels_by_roi_root.tsv; nullable)

## Stage B — Workbook normalization (no filesystem)
Input:
- raw/Cell Observatory - Zebrafish Development.xlsx

Output:
- working/imaging_sheet_normalized.tsv

Required columns in imaging_sheet_normalized.tsv:
- sheet_row_id (int; 0-based)
- date_mount (YYYY-MM-DD; nullable)
- mount_id (int; nullable)
- data_location (string; nullable)
- foundation_guess (aang|korra|nullable)
- experiment_key_guess (string; nullable)
- additional_plasmids_injected (raw)
- additional_mrnas_injected (raw)
- additional_proteins_injected (raw)
- additional_dye_and_chemicals (raw)
- zf_female_genotype (raw)
- zf_male_genotype (raw)
- imaged_locations (raw)
- comments (raw)
- data_evaluation_comments (raw)

## Stage C — Linking (filesystem ↔ workbook)
Inputs:
- working/roi_observations.tsv
- working/imaging_sheet_normalized.tsv

Output:
- working/roi_sheet_links.tsv

Required columns in roi_sheet_links.tsv:
- roi_root_rel
- sheet_row_id (nullable)
- link_method (string)
- link_score (float)
- n_candidates (int)
- is_ambiguous (bool)
- link_notes (string)

## Stage D — Enrichment for DB
Inputs:
- working/roi_observations.tsv
- working/roi_sheet_links.tsv
- working/imaging_sheet_normalized.tsv
- (existing crosswalks + constructs metadata as needed)

Outputs:
- working/legacy_imaging_annotations_for_db_v9.csv
- working/legacy_imaging_annotations_for_db_v9_compat.csv
- qc/*

Notes:
- This is the MOSAIC pipeline. ISOAR will be a sibling pipeline (v4_isoar / v5_isoar) with its own contract.
