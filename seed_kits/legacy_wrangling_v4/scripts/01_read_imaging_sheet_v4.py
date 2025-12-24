from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

import sys
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from seed_kits.legacy_wrangling_v4.scripts._lib_v4.util import (
    clean_str,
    nonempty,
    win_to_posix_path,
    to_cluster_path_from_any,
    foundation_guess_from_location,
    experiment_key_guess_from_location,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
V4_RAW = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "raw"
V4_WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "working"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=str(V4_RAW / "2025-12-22-161955-Cell Observatory - Zebrafish Development.xlsx"))
    ap.add_argument("--sheet", default="Master Imaging list")
    ap.add_argument("--out", default=str(V4_WORK / "imaging_sheet_normalized.tsv"))
    args = ap.parse_args()

    xlsx = Path(args.xlsx)
    out = Path(args.out)
    if not xlsx.exists():
        raise SystemExit(f"[STOP] missing xlsx: {xlsx}")

    df = pd.read_excel(xlsx, sheet_name=args.sheet)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.copy()
    df["sheet_row_id"] = df.index.astype(int)

    for c in df.columns:
        if df[c].dtype == object or str(df[c].dtype).startswith("string"):
            df[c] = df[c].map(clean_str)

    def to_iso_date(v) -> str | None:
        if not nonempty(v):
            return None
        dt = pd.to_datetime(v, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.date().isoformat()

    def to_int(v) -> int | None:
        if not nonempty(v):
            return None
        x = pd.to_numeric(v, errors="coerce")
        if pd.isna(x):
            return None
        try:
            return int(x)
        except Exception:
            return None

    data_raw = df.get("Data location", pd.NA).map(clean_str)
    data_posix = data_raw.map(win_to_posix_path)
    data_cluster = data_raw.map(to_cluster_path_from_any)

    data_best = data_cluster.where(data_cluster.astype(str).str.strip() != "", data_raw)

    out_df = pd.DataFrame(
        {
            "sheet_row_id": df["sheet_row_id"],
            "date_mount": df.get("date_mount", pd.NA).map(to_iso_date),
            "mount_id": df.get("mount_id", pd.NA).map(to_int),
            "data_location_raw": data_raw,
            "data_location_posix": data_posix,
            "data_location_cluster": data_cluster,
            "data_location": data_best,
            "foundation_guess": data_best.map(foundation_guess_from_location),
            "experiment_key_guess": data_best.map(experiment_key_guess_from_location),
            "additional_plasmids_injected": df.get("additional plasmids injected", pd.NA),
            "additional_mrnas_injected": df.get("additional mRNAs injected", pd.NA),
            "additional_proteins_injected": df.get("additonal proteins injected", pd.NA),
            "additional_dye_and_chemicals": df.get("additonal dye and chemicals", pd.NA),
            "zf_female_genotype": df.get("ZF female genotype", pd.NA),
            "zf_male_genotype": df.get("ZF male genotype", pd.NA),
            "imaged_locations": df.get("Imaged Locations", pd.NA),
            "comments": df.get("comments", pd.NA),
            "data_evaluation_comments": df.get("Data evaluation comments", pd.NA),
        }
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out, sep="\t", index=False)
    print(f"[OK] wrote {len(out_df)} imaging sheet rows → {out}")


if __name__ == "__main__":
    main()
