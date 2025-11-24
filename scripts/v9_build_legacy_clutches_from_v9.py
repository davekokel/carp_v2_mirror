from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd


def plate_code_from_row(row: pd.Series) -> str | None:
    """
    Build plate_code from plate_date + plate_id_filled, e.g.
    plate_date=20250721, plate_id_filled=65 -> '20250721-plate65'.
    """
    plate_date = row.get("plate_date")
    plate_id = row.get("plate_id_filled")
    if pd.isna(plate_date) or pd.isna(plate_id):
        return None
    d_int = int(plate_date)
    plate_num = int(plate_id)
    return f"{d_int}-plate{plate_num}"


def is_nontrivial_clutch_key(key: str) -> bool:
    """
    legacy_clutch_key is 'date_born | mom_genotype | dad_genotype'.
    Treat it as trivial (empty) if all three parts are empty.
    """
    key = "" if key is None else str(key)
    parts = [p.strip() for p in key.split("|")]
    if len(parts) != 3:
        return key.strip() != ""
    date, mom, dad = parts
    return bool(date or mom or dad)


def first_nonnull(grp: pd.DataFrame, col: str) -> str:
    if col not in grp.columns:
        return ""
    s = grp[col].dropna().astype(str)
    return s.iloc[0] if len(s) else ""


def build_clutches_and_memberships(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # basic sanity
    required_cols: List[str] = [
        "legacy_clutch_key",
        "date_born",
        "parent_female_genotype_text",
        "parent_male_genotype_text",
        "treatment_rna_rna_base_code",
        "treatment_plasmid_plasmid_base_code",
        "plate_date",
        "plate_id_filled",
        "slot_id_filled",
        "roi_index_within_slot",
        "bruker_roi_id",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise SystemExit(f"v9_build_legacy_clutches_from_v9: CSV is missing required columns: {missing}")

    df2 = df.copy()

    # derive plate_code + slot_index to match the loader logic
    df2["plate_code"] = df2.apply(plate_code_from_row, axis=1)
    df2["slot_index"] = df2["slot_id_filled"].astype("Int64")

    # normalize clutch key
    df2["legacy_clutch_key"] = df2["legacy_clutch_key"].fillna("")

    # keep only rows with a non-trivial clutch key
    df2["has_clutch_key"] = df2["legacy_clutch_key"].apply(is_nontrivial_clutch_key)
    df_valid = df2[df2["has_clutch_key"]].copy()

    # ── build clutches table ────────────────────────────────────────────────
    clutch_rows = []
    for key, grp in df_valid.groupby("legacy_clutch_key"):
        row = {
            "legacy_clutch_key": key,
            "date_born": first_nonnull(grp, "date_born"),
            "parent_female_genotype_text": first_nonnull(grp, "parent_female_genotype_text"),
            "parent_male_genotype_text": first_nonnull(grp, "parent_male_genotype_text"),
            "treatment_rna_rna_base_code": first_nonnull(grp, "treatment_rna_rna_base_code"),
            "treatment_plasmid_plasmid_base_code": first_nonnull(grp, "treatment_plasmid_plasmid_base_code"),
            "roi_count": int(len(grp)),
        }
        # optional dataset summary
        if "dataset_slug" in grp.columns:
            row["datasets"] = ",".join(sorted(grp["dataset_slug"].dropna().astype(str).unique()))
        else:
            row["datasets"] = ""
        clutch_rows.append(row)

    clutches_df = pd.DataFrame(clutch_rows)

    # sort deterministically and assign LCL-style codes
    clutches_df["date_born_sort"] = clutches_df["date_born"].replace("", np.nan)
    clutches_df["date_born_sort"] = pd.to_datetime(
        clutches_df["date_born_sort"], errors="coerce"
    )
    clutches_df = clutches_df.sort_values(
        ["date_born_sort", "legacy_clutch_key"]
    ).reset_index(drop=True)

    clutches_df["clutch_code"] = [
        f"LCL-{i:04d}" for i in range(1, len(clutches_df) + 1)
    ]

    # ── build memberships table ─────────────────────────────────────────────
    mem_rows = []
    for key, grp in df_valid.groupby(["legacy_clutch_key", "plate_code", "slot_index"]):
        clutch_key, plate_code, slot_index = key
        if plate_code is None or pd.isna(plate_code) or pd.isna(slot_index):
            continue
        mem_rows.append(
            {
                "legacy_clutch_key": clutch_key,
                "plate_code": str(plate_code),
                "slot_index": int(slot_index),
                "roi_count": int(len(grp)),
            }
        )

    mem_df = pd.DataFrame(mem_rows)

    # attach clutch_code
    mem_df = mem_df.merge(
        clutches_df[["legacy_clutch_key", "clutch_code"]],
        on="legacy_clutch_key",
        how="left",
    )

    # tidy column order
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
        description="Build v9-native legacy clutches and memberships from v9 imaging CSV."
    )
    parser.add_argument(
        "--csv",
        default="seed_kits/legacy_wrangling_v2/working/legacy_imaging_annotations_for_db_v9.csv",
        help="Path to legacy_imaging_annotations_for_db_v9.csv",
    )
    parser.add_argument(
        "--out-dir",
        default="seed_kits/legacy_wrangling_v2/working",
        help="Output directory for legacy_clutches_v9.csv and legacy_clutch_memberships_v9.csv",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"Input CSV not found: {csv_path}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
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
