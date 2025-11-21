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


def _read_roi_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = ["roi_dir", "injection plasmid"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"ROI CSV missing required columns: {missing}")
    return df


def _load_plasmid_codes(engine) -> set[str]:
    sql = text("SELECT code FROM public.plasmids")
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)
    return set(df["code"].astype(str))


def _build_links(df_roi: pd.DataFrame, plasmid_codes: set[str]) -> pd.DataFrame:
    df = df_roi.copy()

    df = df[df["injection plasmid"].notna()].copy()

    df["injection plasmid"] = (
        df["injection plasmid"].astype(str).str.replace(" ", "", regex=False)
    )
    df["injection_list"] = df["injection plasmid"].str.split(",")

    df = df.explode("injection_list")
    df["transgene_base_code"] = df["injection_list"].astype(str).str.strip()
    df = df[df["transgene_base_code"] != ""]

    df["allele_number"] = 0

    df["plasmid_known"] = df["transgene_base_code"].isin(plasmid_codes)
    df["mapping_note"] = df.apply(
        lambda r: (
            "ok"
            if r["plasmid_known"]
            else f"unknown_plasmid_code:{r['transgene_base_code']}"
        ),
        axis=1,
    )

    # Normalize injection type column name
    inj_type_col = "injection type" if "injection type" in df.columns else None
    if inj_type_col:
        df.rename(columns={inj_type_col: "injection_type"}, inplace=True)
    else:
        df["injection_type"] = ""

    out = df[
        [
            "roi_dir",
            "transgene_base_code",
            "allele_number",
            "injection_type",
            "mapping_note",
        ]
    ].copy()

    out = out.drop_duplicates(
        subset=["roi_dir", "transgene_base_code", "allele_number"]
    ).reset_index(drop=True)

    return out


def main():
    ap = argparse.ArgumentParser(
        description="Build CSV of ROI ↔ injection plasmid links from ROI CSV"
    )
    ap.add_argument(
        "--roi-csv",
        required=True,
        help="Path to ROI CSV (e.g. roi_missing_parents_for_manual_mapping_*.csv)",
    )
    ap.add_argument(
        "--out-csv",
        required=True,
        help="Output CSV path for imaging_injections-style mapping",
    )
    args = ap.parse_args()

    engine = _get_engine()

    df_roi = _read_roi_csv(args.roi_csv)
    plasmid_codes = _load_plasmid_codes(engine)

    links = _build_links(df_roi, plasmid_codes)

    if links.empty:
        print("No links built; nothing to write.")
        return

    out_dir = os.path.dirname(args.out_csv)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    links.to_csv(args.out_csv, index=False)
    print(f"Wrote {len(links)} rows to {args.out_csv}")


if __name__ == "__main__":
    main()
