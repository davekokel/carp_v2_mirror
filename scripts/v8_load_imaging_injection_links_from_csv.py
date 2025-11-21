#!/usr/bin/env python
from __future__ import annotations

import argparse
import os

import pandas as pd
from sqlalchemy import create_engine, text


JFTA_TABLE = "public.join_fish_transgene_alleles"


def _get_engine():
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL not set")
    return create_engine(db_url)


def _read_links_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = ["fish_id", "transgene_base_code", "allele_number"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"CSV missing required columns: {missing}")
    df = df[required].copy()
    df = df.dropna(subset=["fish_id", "transgene_base_code"])
    df["fish_id"] = df["fish_id"].astype(int)
    df["transgene_base_code"] = df["transgene_base_code"].astype(str).str.strip()
    df["allele_number"] = df["allele_number"].astype(int)
    df = df[df["transgene_base_code"] != ""]
    df = df.drop_duplicates(
        subset=["fish_id", "transgene_base_code", "allele_number"]
    ).reset_index(drop=True)
    return df


def _load_existing(engine) -> set[tuple[int, str, int]]:
    sql = text(
        f"""
        SELECT fish_id, transgene_base_code, allele_number
        FROM {JFTA_TABLE}
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)
    if df.empty:
        return set()
    df["fish_id"] = df["fish_id"].astype(int)
    df["transgene_base_code"] = df["transgene_base_code"].astype(str)
    df["allele_number"] = df["allele_number"].astype(int)
    return set(
        zip(df["fish_id"].tolist(),
            df["transgene_base_code"].tolist(),
            df["allele_number"].tolist())
    )


def _insert_missing(engine, links: pd.DataFrame) -> int:
    existing = _load_existing(engine)
    rows = []
    for _, row in links.iterrows():
        key = (
            int(row["fish_id"]),
            str(row["transgene_base_code"]),
            int(row["allele_number"]),
        )
        if key in existing:
            continue
        rows.append(key)

    if not rows:
        return 0

    sql = text(
        f"""
        INSERT INTO {JFTA_TABLE} (fish_id, transgene_base_code, allele_number)
        VALUES (:fish_id, :transgene_base_code, :allele_number)
        """
    )

    with engine.begin() as cx:
        for fish_id, base_code, allele_number in rows:
            cx.execute(
                sql,
                {
                    "fish_id": fish_id,
                    "transgene_base_code": base_code,
                    "allele_number": allele_number,
                },
            )

    return len(rows)


def main():
    ap = argparse.ArgumentParser(
        description="Load imaging injection links into join_fish_transgene_alleles"
    )
    ap.add_argument(
        "--links-csv",
        required=True,
        help="CSV produced by v8_build_imaging_injection_links_csv.py",
    )
    args = ap.parse_args()

    engine = _get_engine()
    links = _read_links_csv(args.links_csv)
    if links.empty:
        print("No links to insert; CSV is empty.")
        return

    inserted = _insert_missing(engine, links)
    print(f"Inserted {inserted} new rows into {JFTA_TABLE}")


if __name__ == "__main__":
    main()
