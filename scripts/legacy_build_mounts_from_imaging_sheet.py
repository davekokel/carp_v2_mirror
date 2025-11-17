from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

# bootstrap repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.config.seed_kits import (  # noqa: E402
    IMAGING_SHEET_XLSX,
    LEGACY_WORKING,
)

OUT_CSV = LEGACY_WORKING / "legacy_mounts.csv"


def build_legacy_mounts() -> pd.DataFrame:
    """
    Normalize the imaging_sheet.xlsx into a working mounts table:

    Columns:
      - mount_id
      - date_mount
      - zf_female_genotype_text
      - zf_male_genotype_text
      - additional_plasmids_raw
      - additional_rnas_raw
      - additional_proteins_raw
      - additional_dyes_raw
      - imaged_locations_raw
      - data_location
      - notes
    """
    xlsx = IMAGING_SHEET_XLSX
    if not xlsx.exists():
        raise FileNotFoundError(f"Imaging sheet XLSX not found: {xlsx}")

    print(f"[INFO] Reading imaging sheet: {xlsx}")
    df = pd.read_excel(xlsx)
    if df.empty:
        return pd.DataFrame(columns=[
            "mount_id",
            "date_mount",
            "zf_female_genotype_text",
            "zf_male_genotype_text",
            "additional_plasmids_raw",
            "additional_rnas_raw",
            "additional_proteins_raw",
            "additional_dyes_raw",
            "imaged_locations_raw",
            "data_location",
            "notes",
        ])

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    print(f"[DEBUG] imaging sheet columns: {list(df.columns)}")

    out = pd.DataFrame()
    out["mount_id"] = df.get("mount_id", "").astype(str).str.strip()
    out["date_mount"] = pd.to_datetime(df.get("date_mount", ""), errors="coerce").dt.date

    out["zf_female_genotype_text"] = df.get("zf female genotype", "").astype(str).str.strip()
    out["zf_male_genotype_text"] = df.get("zf male genotype", "").astype(str).str.strip()

    out["additional_plasmids_raw"] = df.get("additional plasmids injected", "").astype(str).str.strip()
    out["additional_rnas_raw"] = df.get("additional mrnas injected", "").astype(str).str.strip()
    out["additional_proteins_raw"] = df.get("additonal proteins injected", "").astype(str).str.strip()
    out["additional_dyes_raw"] = df.get("additonal dye and chemicals", "").astype(str).str.strip()

    out["imaged_locations_raw"] = df.get("imaged locations", "").astype(str).str.strip()
    out["data_location"] = df.get("data location", "").astype(str).str.strip()

    # Notes: keep a compact summary of key free-text columns
    notes_pieces = []
    # currently we don't combine them; just leave blank for now
    out["notes"] = ""

    # Drop rows with no mount_id
    mask = out["mount_id"].astype(str).str.len() > 0
    dropped = len(out) - int(mask.sum())
    if dropped:
        print(f"[INFO] Dropping {dropped} row(s) with empty mount_id.")
    out = out[mask].reset_index(drop=True)

    LEGACY_WORKING.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Writing legacy mounts to: {OUT_CSV}")
    out.to_csv(OUT_CSV, index=False)
    print(f"[INFO] legacy mounts rows={len(out)}")

    return out


def main() -> None:
    build_legacy_mounts()
    print("[DONE] legacy_mounts build complete.")


if __name__ == "__main__":
    main()
