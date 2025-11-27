from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def norm(s: str | None) -> str:
    if s is None:
        return ""
    return str(s).strip()


def canonical_code(raw: str) -> Tuple[str, Optional[str], Optional[int]]:
    s = norm(raw)
    if not s:
        raise ValueError("Empty plasmid_code cannot be normalized")

    s_clean = s.strip()

    m = re.match(r"^([A-Za-z-]+?)(\d+)$", s_clean)
    if not m:
        return s_clean.upper(), None, None

    prefix_raw, num_raw = m.group(1), m.group(2)
    try:
        num_int = int(num_raw)
    except ValueError:
        return s_clean.upper(), None, None

    prefix = prefix_raw.upper().rstrip("-")
    construct_code = f"{prefix}-{num_int:03d}"
    series_prefix = prefix.lower()
    series_number = num_int
    return construct_code, series_prefix, series_number


def derive_kind(row: pd.Series) -> str:
    truthy = {"1", "true", "t", "yes", "y"}

    def flag(col: str) -> bool:
        v = str(row.get(col, "")).strip().lower()
        return v in truthy

    used_plasmid = flag("used_for_injection_plasmid")
    used_rna = flag("used_for_injection_rna")
    used_crispr = flag("used_for_injection_crispr")

    kinds: list[str] = []
    if used_plasmid:
        kinds.append("plasmid")
    if used_rna:
        kinds.append("rna")
    if used_crispr:
        kinds.append("crispr")

    if not kinds:
        return "plasmid"
    if len(kinds) == 1:
        return kinds[0]
    return "+".join(kinds)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v10: load constructs (with folded plasmid metadata) from constructs_plasmid.csv"
    )
    parser.add_argument(
        "--constructs-csv",
        required=True,
        help="Path to constructs_plasmid.csv",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    path = Path(args.constructs_csv)
    if not path.exists():
        raise SystemExit(f"[v10_load_constructs] constructs CSV not found: {path}")

    df = pd.read_csv(path)
    print(f"[v10_load_constructs] read {len(df)} row(s) from {path}")

    required_cols = [
        "plasmid_code",
        "plasmid_name",
        "resistance",
        "plasmid_notes",
        "used_for_injection_plasmid",
        "used_for_injection_rna",
        "used_for_injection_crispr",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise SystemExit(f"[v10_load_constructs] CSV missing required columns: {missing}")

    df_codes = (
        df
        .groupby("plasmid_code", as_index=False)
        .agg({
            "plasmid_name": "first",
            "plasmid_nickname": "first",
            "resistance": "first",
            "plasmid_notes": "first",
            "used_for_injection_plasmid": "first",
            "used_for_injection_rna": "first",
            "used_for_injection_crispr": "first",
        })
    )
    print(f"[v10_load_constructs] unique plasmid_code rows: {len(df_codes)}")

    engine = get_engine(args.db_url)

    sql_insert_construct = text(
        """
        INSERT INTO public.constructs (
          base_code,
          construct_code,
          construct_kind,
          construct_name,
          description,
          series_prefix,
          series_number,
          resistance,
          backbone,
          plasmid_notes
        )
        VALUES (
          :base_code,
          :construct_code,
          :construct_kind,
          :construct_name,
          :description,
          :series_prefix,
          :series_number,
          :resistance,
          NULL,
          :notes
        )
        ON CONFLICT (construct_code) DO UPDATE SET
          base_code      = EXCLUDED.base_code,
          construct_kind = EXCLUDED.construct_kind,
          construct_name = EXCLUDED.construct_name,
          description    = EXCLUDED.description,
          series_prefix  = EXCLUDED.series_prefix,
          series_number  = EXCLUDED.series_number,
          resistance     = EXCLUDED.resistance,
          backbone       = EXCLUDED.backbone,
          plasmid_notes  = EXCLUDED.plasmid_notes
        RETURNING id::text AS construct_id
        """
    )

    sql_insert_alias = text(
        """
        INSERT INTO public.construct_aliases (
          construct_id,
          alias,
          alias_kind
        )
        VALUES (
          :construct_id,
          :alias,
          'plasmid_code_from_csv'
        )
        ON CONFLICT (construct_id, alias, alias_kind) DO NOTHING
        """
    )

    inserted_constructs = 0
    alias_rows = 0

    with engine.begin() as cx:
        for _, row in df_codes.iterrows():
            plasmid_code = norm(row["plasmid_code"])
            if not plasmid_code:
                print("[v10_load_constructs] SKIP row with empty plasmid_code")
                continue

            try:
                construct_code, series_prefix, series_number = canonical_code(plasmid_code)
            except Exception as e:
                print(f"[v10_load_constructs] WARN: unable to canonicalize {plasmid_code!r}: {e}; skipping.")
                continue

            base_code = construct_code
            name = norm(row.get("plasmid_name")) or plasmid_code
            desc = norm(row.get("plasmid_notes")) or None
            resistance = norm(row.get("resistance")) or None
            construct_kind = derive_kind(row)

            res = cx.execute(
                sql_insert_construct,
                {
                    "base_code": base_code,
                    "construct_code": construct_code,
                    "construct_kind": construct_kind,
                    "construct_name": name,
                    "description": desc,
                    "series_prefix": series_prefix,
                    "series_number": series_number,
                    "resistance": resistance,
                    "notes": desc,
                },
            ).fetchone()
            construct_id = res._mapping["construct_id"]
            inserted_constructs += 1

            cx.execute(
                sql_insert_alias,
                {
                    "construct_id": construct_id,
                    "alias": plasmid_code,
                },
            )
            alias_rows += 1

    print(f"[v10_load_constructs] upserted {inserted_constructs} construct(s)")
    print(f"[v10_load_constructs] upserted {alias_rows} alias row(s)")


if __name__ == "__main__":
    main()
