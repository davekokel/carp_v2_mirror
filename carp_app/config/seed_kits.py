from __future__ import annotations

import os
from pathlib import Path

# Repo root = two levels up from this file
ROOT = Path(__file__).resolve().parents[2]

# Top-level seed_kits/ directory
SEEDKITS_ROOT = ROOT / "seed_kits"

# Standard seed kit (v7 autoload). Allow override via env if needed.
STANDARD_SEEDKIT = Path(
    os.environ.get("CARP_STANDARD_SEEDKIT", SEEDKITS_ROOT / "2025-11-15-121231-autoload")
)

# Legacy import tree
LEGACY_ROOT   = SEEDKITS_ROOT / "legacy_import"
LEGACY_RAW    = LEGACY_ROOT / "raw"
LEGACY_WORKING = LEGACY_ROOT / "working"
LEGACY_FINAL   = LEGACY_ROOT / "final"

# Canonical raw legacy files
IMAGING_SHEET_XLSX = LEGACY_RAW / "2025-11-13-124226-imaging_sheet.xlsx"
ROI_PATHS_XLSX     = LEGACY_RAW / "2025-11-13-092338-korra_aang_roi_root_tiffs_good-3.xlsx"
PLASMID_PREVIEW_XLSX = LEGACY_RAW / "Unique_injected_plasmid__preview_dqm.xlsx"
RNA_PREVIEW_XLSX     = LEGACY_RAW / "Unique_injected_rna__preview_dqm.xlsx"
PARENT_PREVIEW_XLSX  = LEGACY_RAW / "Unique_parent_names__mom_dad_combined__preview_dqm.xlsx"
