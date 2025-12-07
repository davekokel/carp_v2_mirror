#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set (env DB_URL or --db-url)")
    print(f"DB_URL={url}")
    return create_engine(url)


ALLELE_RE = re.compile(r"allele\s+(\d+)", re.IGNORECASE)


def parse_allele(label: str | float | None) -> Optional[int]:
    """
    Given a parent label like 'ef1a:2xLynk:tdmSG(J) (F2 of allele 301)',
    return the allele number (e.g. 301). If none is found, return None.
    """
    if label is None:
        return None
    s = str(label).strip()
    if not s or s.lower() == "nan":
        return None
    m = ALLELE_RE.search(s)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load legacy clutch parents and parsed allele IDs into raw.legacy_clutch_parents_v9"
    )
    parser.add_argument(
        "--csv",
        default="seed_kits/legacy_wrangling_v2/working/legacy_clutches_v9_for_loader.csv",
        help="Path to legacy_clutches_v9_for_loader.csv",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    required = {"clutch_code", "parent_female", "parent_male", "date_born", "legacy_clutch_group"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(
            f"{csv_path} missing required columns {missing}; columns={list(df.columns)}"
        )

    df_out = pd.DataFrame()
    df_out["clutch_code"] = df["clutch_code"].astype(str).str.strip()
    df_out["date_born"] = pd.to_datetime(df["date_born"], errors="coerce").dt.date
    df_out["parent_female_label"] = df["parent_female"].astype(str).where(~df["parent_female"].isna(), None)
    df_out["parent_male_label"] = df["parent_male"].astype(str).where(~df["parent_male"].isna(), None)
    df_out["parent_female_allele"] = df["parent_female"].apply(parse_allele)
    df_out["parent_male_allele"] = df["parent_male"].apply(parse_allele)
    df_out["legacy_clutch_group"] = df["legacy_clutch_group"].astype(str).str.strip()

    print("[INFO] legacy_clutch_parents_v9: sample rows:")
    print(df_out.head(12).to_string(index=False))

    eng = get_engine(args.db_url)
    with eng.begin() as cx:
        cx.execute(text("TRUNCATE raw.legacy_clutch_parents_v9"))
        df_out.to_sql(
            "legacy_clutch_parents_v9",
            cx,
            schema="raw",
            if_exists="append",
            index=False,
        )

    print(f"[OK] loaded {len(df_out)} row(s) into raw.legacy_clutch_parents_v9")


if __name__ == "__main__":
    main()
