from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd


def _plate_code_from_cols(plate_date: object, plate_id_filled: object) -> str | None:
    if plate_date is None or plate_id_filled is None:
        return None

    s = str(plate_date).strip()
    if not s or s.lower() in ("nan", "none", "<na>"):
        return None

    if s.endswith(".0"):
        s = s[:-2]

    m = re.search(r"(20\d{6})", s.replace("-", ""))
    if not m:
        return None

    d_int = int(m.group(1))

    pid = plate_id_filled
    if isinstance(pid, str) and pid.strip().endswith(".0"):
        pid = pid.strip()[:-2]
    try:
        plate_num = int(pid)
    except Exception:
        try:
            plate_num = int(float(pid))
        except Exception:
            return None

    return f"{d_int}-plate{plate_num}"


def first_nonnull(grp: pd.DataFrame, col: str) -> str:
    if col not in grp.columns:
        return ""
    s = grp[col].dropna().astype(str)
    return s.iloc[0] if len(s) else ""


def build_clutches_and_memberships(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    required_cols: List[str] = [
        "plate_date",
        "plate_id_filled",
        "slot_id_filled",
        "roi_index_within_slot",
        "bruker_roi_id",
        "roi_dir",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise SystemExit(f"v9_build_legacy_clutches_from_v9: CSV is missing required columns: {missing}")

    df2 = df.copy()

    df2["plate_code"] = df2.apply(lambda r: _plate_code_from_cols(r.get("plate_date"), r.get("plate_id_filled")), axis=1)
    df2["slot_index"] = pd.to_numeric(df2["slot_id_filled"], errors="coerce").astype("Int64")

    df2 = df2[df2["plate_code"].notna() & df2["slot_index"].notna()].copy()

    df2["legacy_clutch_key"] = df2["plate_code"].astype(str) + "|slot" + df2["slot_index"].astype(int).astype(str)

    if "date_born" not in df2.columns:
        if "Date born" in df2.columns:
            df2["date_born"] = df2["Date born"]
        else:
            df2["date_born"] = ""

    if "parent_female_genotype_text" not in df2.columns:
        df2["parent_female_genotype_text"] = df2.get("ZF female genotype", "")
    if "parent_male_genotype_text" not in df2.columns:
        df2["parent_male_genotype_text"] = df2.get("ZF male genotype", "")

    if "treatment_rna_rna_base_code" not in df2.columns:
        df2["treatment_rna_rna_base_code"] = ""
    if "treatment_plasmid_plasmid_base_code" not in df2.columns:
        df2["treatment_plasmid_plasmid_base_code"] = ""

    clutch_rows = []
    for key, grp in df2.groupby("legacy_clutch_key", dropna=False):
        clutch_rows.append(
            {
                "legacy_clutch_key": str(key),
                "date_born": first_nonnull(grp, "date_born"),
                "parent_female_genotype_text": first_nonnull(grp, "parent_female_genotype_text"),
                "parent_male_genotype_text": first_nonnull(grp, "parent_male_genotype_text"),
                "treatment_rna_rna_base_code": first_nonnull(grp, "treatment_rna_rna_base_code"),
                "treatment_plasmid_plasmid_base_code": first_nonnull(grp, "treatment_plasmid_plasmid_base_code"),
                "roi_count": int(len(grp)),
                "datasets": "",
            }
        )

    clutches_df = pd.DataFrame(clutch_rows)

    clutches_df["date_born_sort"] = clutches_df["date_born"].replace("", np.nan)
    clutches_df["date_born_sort"] = pd.to_datetime(clutches_df["date_born_sort"], errors="coerce")
    clutches_df = clutches_df.sort_values(["date_born_sort", "legacy_clutch_key"]).reset_index(drop=True)

    clutches_df["clutch_code"] = [f"LCL-{i:04d}" for i in range(1, len(clutches_df) + 1)]

    mem_rows = []
    for (clutch_key, plate_code, slot_index), grp in df2.groupby(["legacy_clutch_key", "plate_code", "slot_index"], dropna=False):
        if plate_code is None or pd.isna(plate_code) or pd.isna(slot_index):
            continue
        mem_rows.append(
            {
                "legacy_clutch_key": str(clutch_key),
                "plate_code": str(plate_code),
                "slot_index": int(slot_index),
                "roi_count": int(len(grp)),
            }
        )

    mem_df = pd.DataFrame(mem_rows)
    mem_df = mem_df.merge(clutches_df[["legacy_clutch_key", "clutch_code"]], on="legacy_clutch_key", how="left")

    clutches_df = clutches_df[
        [
            "clutch_code",
            "legacy_clutch_key",
            "date_born",
            "parent_female_genotype_text",
            "parent_male_genotype_text",
            "treatment_rna_rna_base_code",
            "treatment_plasmid_plasmid_base_code",
            "roi_count",
            "datasets",
        ]
    ]

    mem_df = mem_df[
        [
            "clutch_code",
            "legacy_clutch_key",
            "plate_code",
            "slot_index",
            "roi_count",
        ]
    ]

    return clutches_df, mem_df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build v9-native legacy clutches and memberships from the SAME ROI feed used to create plates/slots."
    )
    parser.add_argument(
        "--csv",
        default="seed_kits/legacy_wrangling_v4/working/legacy_imaging_annotations_for_loader_v9_compat.csv",
        help="Path to legacy_imaging_annotations_for_loader_v9_compat.csv",
    )
    parser.add_argument(
        "--out-dir",
        default="seed_kits/legacy_wrangling_v4/working",
        help="Output directory for legacy_clutches_v9.csv + legacy_clutch_memberships_v9.csv",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"Input CSV not found: {csv_path}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    clutches_df, mem_df = build_clutches_and_memberships(df)

    clutches_out = out_dir / "legacy_clutches_v9.csv"
    memberships_out = out_dir / "legacy_clutch_memberships_v9.csv"

    clutches_df.to_csv(clutches_out, index=False)
    mem_df.to_csv(memberships_out, index=False)

    print("v9_build_legacy_clutches_from_v9:")
    print(f"  input: {csv_path}")
    print(f"  wrote clutches:     {clutches_out} (n={len(clutches_df)})")
    print(f"  wrote memberships:  {memberships_out} (n={len(mem_df)})")


if __name__ == "__main__":
    main()
