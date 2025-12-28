legacy_wrangling_v5 — v5 ROI channel & session metadata
=======================================================

This directory contains v5 legacy wrangling artifacts.
The workflow is CSV-first and pre-database.
The database only consumes these outputs.

There are exactly TWO canonical v5 artifacts.

-------------------------------------------------------
1) Deterministic ROI → channel counts
-------------------------------------------------------

Snapshot files:
  working/snapshots/roi_channel_counts_v5_YYYYMMDD_HHMMSS.csv

Schema:
  roi_path,channel_name,n_tiffs

This file is generated ONLY from raw TIFF paths.
It is fully reproducible and never edited by hand.

Input:
  raw/foundation_tiff_files_YYYYMMDD_HHMMSS.txt

Script:
  scripts/v5_build_roi_channel_counts_from_txt.py

Command:
  python scripts/v5_build_roi_channel_counts_from_txt.py \
    raw/foundation_tiff_files_YYYYMMDD_HHMMSS.txt

Then snapshot:
  cp working/roi_channel_counts_v5.csv \
     working/snapshots/roi_channel_counts_v5_YYYYMMDD_HHMMSS.csv

channel_name is derived ONLY from filenames and has the form:
  camX-chY-camZ-WL

Derived images (MIPs, FFTs, recon slices) are excluded.

-------------------------------------------------------
2) Manual ROI → session / genotype / treatment map
-------------------------------------------------------

Snapshot files:
  working/snapshots/roi_path_to_session_markers_v5_manual_YYYYMMDD_HHMMSS.csv

Schema:
  roi_path,
  date_mount_id,
  genotype_base_codes,
  genotype_allele_codes,
  treatment_rna_base_codes,
  treatment_plasmid_base_codes

This file is NOT derivable.
It is edited by humans and versioned via snapshots.

-------------------------------------------------------
Design intent
-------------------------------------------------------

• CSVs are the source of truth
• Scripts are simple and auditable
• Database tables are downstream mirrors
• UI reads from DB, but semantics live here
