from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# bootstrap repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.config.seed_kits import LEGACY_FINAL  # noqa: E402

ROI_PATHS_CSV = LEGACY_FINAL / "legacy_roi_paths.csv"
SLOTS_OUT     = LEGACY_FINAL / "legacy_imaging_slots.csv"
ROIS_OUT      = LEGACY_FINAL / "legacy_imaging_rois.csv"


def build_slots_and_rois() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build legacy_imaging_slots.csv and legacy_imaging_rois.csv from legacy_roi_paths.csv.

    Slots CSV will have columns:
      - plate_code
      - slot_code
      - legacy_fish_label
      - fish_code
      - imaging_nickname
      - timepoint
      - notes

    ROIs CSV will have columns:
      - plate_code
      - slot_code
      - roi_code
      - roi_index
      - roi_name
      - roi_dir
      - date_imaged
      - notes
    """
    if not ROI_PATHS_CSV.exists():
        raise FileNotFoundError(f"ROI paths CSV not found: {ROI_PATHS_CSV}")

    print(f"[INFO] Reading legacy_roi_paths: {ROI_PATHS_CSV}")
    df = pd.read_csv(ROI_PATHS_CSV)
    if df.empty:
        raise RuntimeError(f"{ROI_PATHS_CSV} is empty")

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["plate_id_fk", "fish_folder_name", "roi_name", "full_path", "roi_anatomy_name", "note"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{ROI_PATHS_CSV} is missing required columns: {missing}")

    # Standardize plate_code and slot_code
    df["plate_code"] = df["plate_id_fk"].astype(str).str.strip()
    df["slot_code"] = df["fish_folder_name"].astype(str).str.strip()

    # ---- Slots -----------------------------------------------------------------
    slots = (
        df[["plate_code", "slot_code"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    # Fill required columns
    slots["legacy_fish_label"] = slots["slot_code"]          # best-effort label
    slots["fish_code"] = ""                                  # no standard fish yet
    slots["imaging_nickname"] = ""                           # can fill later if desired
    slots["timepoint"] = ""                                  # can fill later
    slots["notes"] = ""                                      # keep empty for now

    # Order columns exactly as loader expects
    slots = slots[
        ["plate_code", "slot_code", "legacy_fish_label", "fish_code", "imaging_nickname", "timepoint", "notes"]
    ]

    # ---- ROIs ------------------------------------------------------------------
    rois = df[
        ["plate_code", "slot_code", "roi_name", "full_path", "note"]
    ].copy()

    # Assign roi_index per (plate_code, slot_code)
    rois["roi_index"] = (
        rois.groupby(["plate_code", "slot_code"]).cumcount() + 1
    )

    # roi_code: make it a simple code, e.g. "<slot_code>_<roi_index>"
    rois["roi_code"] = rois["slot_code"].astype(str).str.strip() + "_" + rois["roi_index"].astype(str)

    # Fill required fields
    rois["roi_dir"] = rois["full_path"].astype(str).str.strip()
    rois["date_imaged"] = ""    # can be filled from mounts later if needed
    # notes: reuse note column; loader expects "notes"
    rois["notes"] = rois["note"].astype(str).str.strip()

    # Order columns as loader expects
    rois = rois[
        ["plate_code", "slot_code", "roi_code", "roi_index", "roi_name", "roi_dir", "date_imaged", "notes"]
    ].sort_values(["plate_code", "slot_code", "roi_index"]).reset_index(drop=True)

    LEGACY_FINAL.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Writing legacy imaging slots to: {SLOTS_OUT}")
    slots.to_csv(SLOTS_OUT, index=False)
    print(f"[INFO] legacy imaging slots rows={len(slots)}")

    print(f"[INFO] Writing legacy imaging rois to: {ROIS_OUT}")
    rois.to_csv(ROIS_OUT, index=False)
    print(f"[INFO] legacy imaging rois rows={len(rois)}")

    return slots, rois


def main() -> None:
    build_slots_and_rois()
    print("[DONE] legacy_imaging_slots & legacy_imaging_rois build complete.")


if __name__ == "__main__":
    main()
