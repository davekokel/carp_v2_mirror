#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from carp_app.etl.fish_v11_treatments_import import load_treated_fish_from_csv as load_treated_from_df


def get_engine(db_url: str | None) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set")
    print(f"DB_URL={url}")
    return create_engine(url)


REQ = [
    "line_nickname",
    "birthday",
    "genetic_background",
    "instance_stage",
    "treatment_basecode",
    "transgene_basecode",
    "allele_nickname",
    "zygosity",
]


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed treated fish (fish_treated.csv) via v11 treated importer (adapter).")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--db-url")
    args = ap.parse_args()

    p = Path(args.csv)
    if not p.exists():
        raise SystemExit(f"CSV not found: {p}")

    df = pd.read_csv(p, low_memory=False)
    missing = [c for c in REQ if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing required columns {missing}; got={list(df.columns)}")

    out = pd.DataFrame()
    out["line_nickname"] = df["line_nickname"].astype(str).str.strip()
    out["birthday"] = df["birthday"].astype(str).str.strip()
    out["genetic_background"] = df["genetic_background"].astype(str).str.strip()
    out["instance_stage"] = df["instance_stage"].astype(str).str.strip()
    out["treatment_basecode"] = df["treatment_basecode"].astype(str).str.strip()
    out["transgene_basecode"] = df["transgene_basecode"].astype(str).str.strip()
    out["allele_nickname"] = df["allele_nickname"].astype(str).str.strip()
    out["zygosity"] = df["zygosity"].astype(str).str.strip()
    out["created_by"] = df["created_by"].astype(str).where(~df["created_by"].isna(), "").str.strip()
    out["enzyme"] = df["enzyme"].astype(str).where(~df["enzyme"].isna(), "").str.strip()
    out["description"] = df["description"].astype(str).where(~df["description"].isna(), "").str.strip()

    eng = get_engine(args.db_url)
    with eng.begin() as cx:
        summary = load_treated_from_df(out, cx)

    print(summary)


if __name__ == "__main__":
    main()
