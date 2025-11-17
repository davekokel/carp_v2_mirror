from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# bootstrap repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.config.seed_kits import ROI_PATHS_XLSX, LEGACY_FINAL  # noqa: E402

OUT_CSV = LEGACY_FINAL / "legacy_imaging_plates.csv"


def _pick_column(df: pd.DataFrame, candidates: List[str], label: str) -> Optional[str]:
    cols = list(df.columns)
    for c in candidates:
        if c in df.columns:
            return c
    print(f"[WARN] No column found for {label}. Tried: {candidates}. Available: {cols}")
    return None


def build_legacy_imaging_plates() -> pd.DataFrame:
    """
    Build legacy_imaging_plates.csv from the Korra/Aang ROI path index.

    Output columns:
      - plate_code       (typically the dataset name)
      - plate_date       (first date_experiment for that dataset, if present)
      - root_path        (common directory prefix of roi_dir for that dataset)
      - source_system    ("legacy")
      - notes
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

    date_col = _pick_column(df, ["date_experiment", "date", "experiment_date"], "date_experiment")
    dataset_col = _pick_column(df, ["dataset", "plate", "plate_id", "experiment", "experiment_name"], "dataset")
    roi_dir_col = _pick_column(df, ["roi_dir", "full_path", "path", "roi_path", "filepath", "file_path"], "roi_dir")

    if not dataset_col:
        raise ValueError("Cannot determine dataset/plate column in ROI paths sheet.")
    if not roi_dir_col:
        raise ValueError("Cannot determine ROI directory/full_path column in ROI paths sheet.")

    # Normalize date if present
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.date

    records: List[Dict[str, object]] = []

    for dataset, sub in df.groupby(dataset_col):
        plate_code = str(dataset).strip()
        if not plate_code:
            continue

        plate_date = None
        if date_col:
            dates = sub[date_col].dropna()
            if not dates.empty:
                plate_date = dates.iloc[0]

        paths = sub[roi_dir_col].dropna().astype(str).tolist()
        root_path = ""
        if paths:
            try:
                root_path = os.path.commonpath(paths)
            except Exception:
                # Fallback: use directory of first path
                root_path = os.path.dirname(paths[0])

        notes = ""
        records.append(
            {
                "plate_code": plate_code,
                "plate_date": plate_date,
                "root_path": root_path,
                "source_system": "legacy",
                "notes": notes,
            }
        )

    plates_df = pd.DataFrame(records)
    if plates_df.empty:
        print("[WARN] No imaging plates produced.")
    else:
        plates_df = plates_df.sort_values(["plate_date", "plate_code"]).reset_index(drop=True)

    LEGACY_FINAL.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Writing legacy imaging plates to: {OUT_CSV}")
    plates_df.to_csv(OUT_CSV, index=False)
    print(f"[INFO] legacy imaging plates rows={len(plates_df)}")

    return plates_df


def main() -> None:
    build_legacy_imaging_plates()
    print("[DONE] legacy_imaging_plates build complete.")


if __name__ == "__main__":
    main()
