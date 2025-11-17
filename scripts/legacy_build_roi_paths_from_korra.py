from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Dict, Optional

import os
import pandas as pd

# bootstrap repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.config.seed_kits import ROI_PATHS_XLSX, LEGACY_FINAL  # noqa: E402


OUT_CSV = LEGACY_FINAL / "legacy_roi_paths.csv"


def _pick_column(df: pd.DataFrame, candidates: List[str], label: str) -> Optional[str]:
    cols = list(df.columns)
    for c in candidates:
        if c in df.columns:
            return c
    print(f"[WARN] No column found for {label}. Tried: {candidates}. Available: {cols}")
    return None


def build_legacy_roi_paths() -> pd.DataFrame:
    """
    Build legacy_roi_paths.csv from the Korra/Aang ROI path index.

    Output columns:
      - plate_id_fk
      - full_path
      - plate_folder
      - fish_folder_name
      - roi_name
      - roi_anatomy_name
      - note
    """
    xlsx = ROI_PATHS_XLSX
    if not xlsx.exists():
        raise FileNotFoundError(f"Korra/Aang ROI paths XLSX not found: {xlsx}")

    print(f"[INFO] Reading ROI paths from: {xlsx}")
    df = pd.read_excel(xlsx)
    if df.empty:
        raise RuntimeError(f"{xlsx} is empty")

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    print(f"[DEBUG] ROI paths columns: {list(df.columns)}")

    # Try to detect the full-path column
    full_path_col = _pick_column(
        df,
        ["roi_dir", "full_path", "path", "roi_path", "filepath", "file_path"],
        "full_path",
    )
    if not full_path_col:
        raise ValueError("Cannot determine full_path column in ROI paths sheet.")

    # Heuristics for other columns
    plate_col = _pick_column(
        df,
        ["dataset", "plate", "plate_id", "experiment", "experiment_name"],
        "plate_folder",
    )
    fish_col = _pick_column(
        df,
        ["fish", "fish_folder", "fish_folder_name", "fish_id", "mount_id"],
        "fish_folder_name",
    )
    roi_name_col = _pick_column(
        df,
        ["roi_name", "roi", "roi_rel", "roi_id"],
        "roi_name",
    )
    roi_annot_col = _pick_column(
        df,
        ["roi_anatomy_name", "imaged_locations", "location", "tissue", "structure"],
        "roi_anatomy_name",
    )
    note_col = _pick_column(
        df,
        ["notes", "note", "comment", "comments"],
        "note",
    )

    records: List[Dict[str, str]] = []

    for _, row in df.iterrows():
        raw_path = str(row.get(full_path_col, "") or "").strip()
        if not raw_path:
            continue

        full_path = os.path.normpath(raw_path)

        # Derive plate_folder and fish_folder_name from either explicit columns or path
        plate_folder = ""
        fish_folder_name = ""

        if plate_col and pd.notna(row.get(plate_col)):
            plate_folder = str(row.get(plate_col, "") or "").strip()

        if fish_col and pd.notna(row.get(fish_col)):
            fish_folder_name = str(row.get(fish_col, "") or "").strip()

        # Fallbacks: derive from path segments if needed
        parts = Path(full_path).parts
        if not plate_folder and len(parts) >= 2:
            plate_folder = parts[-2]  # parent directory
        if not fish_folder_name and len(parts) >= 1:
            fish_folder_name = Path(full_path).stem  # file or last segment

        roi_name = ""
        if roi_name_col and pd.notna(row.get(roi_name_col)):
            roi_name = str(row.get(roi_name_col, "") or "").strip()
        if not roi_name:
            roi_name = fish_folder_name

        roi_anatomy_name = ""
        if roi_annot_col and pd.notna(row.get(roi_annot_col)):
            roi_anatomy_name = str(row.get(roi_annot_col, "") or "").strip()

        note = ""
        if note_col and pd.notna(row.get(note_col)):
            note = str(row.get(note_col, "") or "").strip()

        records.append(
            {
                "plate_id_fk": plate_folder,
                "full_path": full_path,
                "plate_folder": plate_folder,
                "fish_folder_name": fish_folder_name,
                "roi_name": roi_name,
                "roi_anatomy_name": roi_anatomy_name,
                "note": note,
            }
        )

    out_df = pd.DataFrame(records)
    if out_df.empty:
        print("[WARN] No ROI path records produced.")
    else:
        out_df = out_df.sort_values(["plate_id_fk", "fish_folder_name", "roi_name"]).reset_index(drop=True)

    LEGACY_FINAL.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Writing legacy ROI paths to: {OUT_CSV}")
    out_df.to_csv(OUT_CSV, index=False)
    print(f"[INFO] legacy ROI paths rows={len(out_df)}")

    return out_df


def main() -> None:
    build_legacy_roi_paths()
    print("[DONE] legacy_roi_paths build complete.")


if __name__ == "__main__":
    main()
