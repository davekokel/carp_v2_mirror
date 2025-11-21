#!/usr/bin/env python
from __future__ import annotations

import argparse
import os

import pandas as pd
from sqlalchemy import create_engine, text


def _get_engine():
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL not set")
    return create_engine(db_url)


def _parse_flag(val) -> bool:
    """Robustly parse 0/1, True/False, 'TRUE', 'FALSE', etc. into bool."""
    if pd.isna(val):
        return False
    s = str(val).strip().lower()
    if s in ("1", "true", "t", "yes", "y"):
        return True
    if s in ("0", "false", "f", "no", "n", ""):
        return False
    # anything else: be conservative and treat as False
    return False


def _read_constructs(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    required = [
        "plasmid_code",
        "used_for_injection_plasmid",
        "used_for_injection_rna",
        "used_for_injection_crispr",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"constructs CSV missing required columns: {missing}")

    df["plasmid_code"] = df["plasmid_code"].astype(str).str.strip()

    # Normalize flags to real booleans
    for col in required[1:]:
        df[col] = df[col].apply(_parse_flag)

    # Aggregate across all rows per plasmid: any() over the flags
    grouped = (
        df.groupby("plasmid_code")[required[1:]]
        .any()
        .reset_index()
    )

    # Build construct_type string per plasmid
    def derive(row) -> str | None:
        types = []
        if row["used_for_injection_plasmid"]:
            types.append("DNA")
        if row["used_for_injection_rna"]:
            types.append("RNA")
        if row["used_for_injection_crispr"]:
            types.append("CRISPR")
        return ",".join(types) if types else None

    grouped["construct_type"] = grouped.apply(derive, axis=1)
    grouped = grouped[grouped["construct_type"].notna()].copy()
    grouped = grouped[["plasmid_code", "construct_type"]].reset_index(drop=True)

    return grouped


def _update_construct_type(engine, df: pd.DataFrame) -> int:
    sql = text(
        """
        UPDATE public.plasmids p
        SET construct_type = :construct_type
        WHERE p.code = :plasmid_code
           OR p.plasmid_base_code = :plasmid_code
        """
    )

    updated = 0
    with engine.begin() as cx:
        for _, row in df.iterrows():
            params = {
                "construct_type": row["construct_type"],
                "plasmid_code": row["plasmid_code"],
            }
            res = cx.execute(sql, params)
            updated += res.rowcount or 0
    return updated


def main():
    ap = argparse.ArgumentParser(
        description="Set plasmids.construct_type from constructs_plasmid.csv"
    )
    ap.add_argument(
        "--constructs-csv",
        required=True,
        help="Path to constructs_plasmid.csv",
    )
    args = ap.parse_args()

    engine = _get_engine()
    df = _read_constructs(args.constructs_csv)
    if df.empty:
        print("No construct types inferred; nothing to update.")
        return

    updated = _update_construct_type(engine, df)
    print(f"Updated construct_type for {updated} plasmid row(s).")


if __name__ == "__main__":
    main()
