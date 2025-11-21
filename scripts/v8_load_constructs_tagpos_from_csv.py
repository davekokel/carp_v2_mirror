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


def _read_constructs(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = ["plasmid_code", "fluor_code", "tag_code", "tag_pos"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"constructs CSV missing required columns: {missing}")

    df = df[required].copy()

    df = df[df["tag_pos"].notna()].copy()
    df = df[df["tag_pos"].astype(str).str.strip() != ""].copy()
    df = df[df["tag_code"].notna()].copy()
    df = df[df["tag_code"].astype(str).str.strip() != ""].copy()

    df["plasmid_code"] = df["plasmid_code"].astype(str).str.strip()
    df["fluor_code"] = df["fluor_code"].astype(str).str.strip()
    df["tag_code"] = df["tag_code"].astype(str).str.strip()
    df["tag_pos"] = df["tag_pos"].astype(str).str.strip()

    df = df.drop_duplicates(
        subset=["plasmid_code", "fluor_code", "tag_code"]
    ).reset_index(drop=True)

    return df


def _update_tag_pos(engine, df: pd.DataFrame) -> int:
    sql = text(
        """
        UPDATE public.fusions AS f
        SET tag_pos = :tag_pos
        FROM public.join_plasmid_fusions jpf
        JOIN public.plasmids p
          ON p.id = jpf.plasmid_id
        JOIN public.fusions fu
          ON fu.id = jpf.fusion_id
        JOIN public.fluors fl
          ON fl.id = fu.fluor_id
        JOIN public.tags tg
          ON tg.id = fu.tag_id
        WHERE f.id = fu.id
          AND p.code = :plasmid_code
          AND fl.fluor_code = :fluor_code
          AND tg.tag_code = :tag_code
        """
    )

    updated = 0
    with engine.begin() as cx:
        for _, row in df.iterrows():
            params = {
                "tag_pos": row["tag_pos"],
                "plasmid_code": row["plasmid_code"],
                "fluor_code": row["fluor_code"],
                "tag_code": row["tag_code"],
            }
            res = cx.execute(sql, params)
            updated += res.rowcount or 0
    return updated


def main():
    ap = argparse.ArgumentParser(
        description="Load fusion tag_pos from constructs_plasmid.csv into public.fusions"
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
        print("No rows with tag_pos in constructs CSV; nothing to do.")
        return

    updated = _update_tag_pos(engine, df)
    print(f"Updated tag_pos for {updated} fusion row(s).")


if __name__ == "__main__":
    main()
