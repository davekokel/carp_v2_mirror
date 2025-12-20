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

from carp_app.etl.fish_v11_shared import load_fish_from_csv as load_fish_from_df


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
    "transgene_base_code",
    "allele_nickname",
    "zygosity",
]


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed fish (transgenics.csv) via v11 fish importer (adapter).")
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
    out["transgene_base_code"] = df["transgene_base_code"].astype(str).str.strip()
    out["line_nickname"] = df["line_nickname"].astype(str).str.strip()
    out["allele_nickname"] = df["allele_nickname"].astype(str).str.strip()
    out["fish_nickname"] = ""
    out["instance_stage"] = df["instance_stage"].astype(str).str.strip()
    out["birthday"] = df["birthday"].astype(str).str.strip()
    out["genetic_background"] = df["genetic_background"].astype(str).str.strip()

    desc = df["description"].astype(str).where(~df["description"].isna(), "")
    created_by = df["created_by"].astype(str).where(~df["created_by"].isna(), "")
    zyg = df["zygosity"].astype(str).where(~df["zygosity"].isna(), "")
    out["notes"] = (
        ("created_by=" + created_by.str.strip()).where(created_by.str.strip() != "", "")
        + ("; zygosity=" + zyg.str.strip()).where(zyg.str.strip() != "", "")
        + ("; " + desc.str.strip()).where(desc.str.strip() != "", "")
    ).str.strip("; ").str.strip()

    eng = get_engine(args.db_url)
    with eng.begin() as cx:
        summary = load_fish_from_df(out, cx)

    print(summary)


if __name__ == "__main__":
    main()
