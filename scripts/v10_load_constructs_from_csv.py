#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.construct_normalizer import normalize_construct_code


def norm(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip()


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    return create_engine(url)


def load_constructs_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = [
        "plasmid_code",
        "plasmid_name",
        "plasmid_nickname",
        "resistance",
        "plasmid_notes",
        "n_fluors_per_plasmid",
        "fluor_code",
        "tag_code",
        "tag_pos",
    ]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise SystemExit(f"[v10_load_constructs] missing columns in CSV: {missing}")

    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(norm)
    return df


def upsert_constructs(cx, df: pd.DataFrame) -> int:
    uniques = (
        df.groupby("plasmid_code")
        .agg(
            plasmid_name=("plasmid_name", "first"),
            plasmid_nickname=("plasmid_nickname", "first"),
            resistance=("resistance", "first"),
            plasmid_notes=("plasmid_notes", "first"),
        )
        .reset_index()
    )

    count = 0
    for _, r in uniques.iterrows():
        raw_code = r["plasmid_code"]
        canonical = normalize_construct_code(raw_code)
        if not canonical:
            print(f"[v10_load_constructs] WARNING: cannot normalize plasmid_code='{raw_code}', skipping")
            continue

        name = norm(r["plasmid_name"]) or canonical
        desc = norm(r["plasmid_notes"]) or ""

        cx.execute(
            text(
                """
                INSERT INTO public.constructs (
                  construct_code,
                  base_code,
                  construct_name,
                  construct_kind,
                  description
                )
                VALUES (
                  :code,
                  :code,
                  :name,
                  'plasmid',
                  :desc
                )
                ON CONFLICT (construct_code) DO UPDATE
                  SET construct_name = EXCLUDED.construct_name,
                      description   = EXCLUDED.description;
                """
            ),
            {
                "code": canonical,
                "name": name,
                "desc": desc,
            },
        )
        count += 1

    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--constructs-csv",
        required=True,
        help="Path to constructs_plasmid.csv",
    )
    args = parser.parse_args()

    path = Path(args.constructs_csv)
    if not path.exists():
        raise SystemExit(f"[v10_load_constructs] constructs CSV not found: {path}")

    df = load_constructs_csv(path)
    engine = get_engine()

    with engine.begin() as cx:
        n_constructs = upsert_constructs(cx, df)
        print(f"[v10_load_constructs] upserted {n_constructs} construct(s)")


if __name__ == "__main__":
    main()
