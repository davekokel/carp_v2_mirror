from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Dict

import pandas as pd

# bootstrap repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.config.seed_kits import LEGACY_WORKING, LEGACY_FINAL  # noqa: E402

MOUNTS_CSV = LEGACY_WORKING / "legacy_mounts.csv"
CLUTCHES_OUT = LEGACY_FINAL / "legacy_clutches.csv"


def _make_clutch_code(date_mount, mount_id: str) -> str:
    """
    Build a deterministic clutch_code from date_mount + mount_id.

    Example:
      date_mount = 2025-10-29, mount_id = '1'
      -> 'LG_CLUTCH_20251029_1'
    """
    if pd.isna(date_mount):
        ds = "UNKNOWN"
    else:
        ds = date_mount.strftime("%Y%m%d")
    mid = str(mount_id).strip().replace(" ", "_")
    if not mid:
        mid = "NA"
    return f"LG_CLUTCH_{ds}_{mid}"


def build_legacy_clutches() -> pd.DataFrame:
    """
    Build legacy_clutches.csv from legacy_mounts.csv.

    Columns:
      - clutch_code
      - clutch_date
      - mount_id
      - mom_genotype_text
      - dad_genotype_text
      - mom_genotype_code  (empty for now)
      - dad_genotype_code  (empty for now)
      - additional_plasmids_raw
      - additional_rnas_raw
      - additional_proteins_raw
      - additional_dyes_raw
      - imaged_locations_raw
      - data_location
      - notes
    """
    if not MOUNTS_CSV.exists():
        raise FileNotFoundError(f"legacy_mounts.csv not found: {MOUNTS_CSV}")

    print(f"[INFO] Reading legacy_mounts: {MOUNTS_CSV}")
    df = pd.read_csv(MOUNTS_CSV, parse_dates=["date_mount"])
    if df.empty:
        raise RuntimeError(f"{MOUNTS_CSV} is empty")

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["mount_id", "date_mount"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{MOUNTS_CSV} is missing required columns: {missing}")

    df["mount_id"] = df["mount_id"].astype(str).str.strip()
    # date_mount is already parsed; ensure it's date, not datetime
    df["date_mount"] = pd.to_datetime(df["date_mount"], errors="coerce").dt.date

    # Drop rows with no mount_id
    mask = df["mount_id"].astype(str).str.len() > 0
    dropped = len(df) - int(mask.sum())
    if dropped:
        print(f"[INFO] Dropping {dropped} row(s) with empty mount_id.")
    df = df[mask].reset_index(drop=True)

    # Build clutch_code per row (1:1 with mount for now)
    df["clutch_code"] = [
        _make_clutch_code(d, mid) for d, mid in zip(df["date_mount"], df["mount_id"])
    ]

    out = pd.DataFrame()

    out["clutch_code"] = df["clutch_code"]
    out["clutch_date"] = df["date_mount"]
    out["mount_id"] = df["mount_id"]

    out["mom_genotype_text"] = df.get("zf_female_genotype_text", "").astype(str).str.strip()
    out["dad_genotype_text"] = df.get("zf_male_genotype_text", "").astype(str).str.strip()

    # placeholder genotype_code columns for future mapping
    out["mom_genotype_code"] = ""
    out["dad_genotype_code"] = ""

    out["additional_plasmids_raw"] = df.get("additional_plasmids_raw", "").astype(str).str.strip()
    out["additional_rnas_raw"] = df.get("additional_rnas_raw", "").astype(str).str.strip()
    out["additional_proteins_raw"] = df.get("additional_proteins_raw", "").astype(str).str.strip()
    out["additional_dyes_raw"] = df.get("additional_dyes_raw", "").astype(str).str.strip()

    out["imaged_locations_raw"] = df.get("imaged_locations_raw", "").astype(str).str.strip()
    out["data_location"] = df.get("data_location", "").astype(str).str.strip()
    out["notes"] = df.get("notes", "").astype(str).str.strip()

    out = out.sort_values(["clutch_date", "clutch_code"]).reset_index(drop=True)

    LEGACY_FINAL.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Writing legacy clutches to: {CLUTCHES_OUT}")
    out.to_csv(CLUTCHES_OUT, index=False)
    print(f"[INFO] legacy clutches rows={len(out)}")

    return out


def main() -> None:
    build_legacy_clutches()
    print("[DONE] legacy_clutches build complete.")


if __name__ == "__main__":
    main()
