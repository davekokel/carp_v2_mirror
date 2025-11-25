from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Tuple, Optional

import re
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: str | None) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def split_series(code: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Best-effort split of construct_code into (series_prefix, series_number),
    treating '-' as a delimiter, not part of the prefix.

    Examples:
      'pDQM005' -> ('pdqm', 5)
      'MGCO-01' -> ('mgco', 1)
      'HC-9'    -> ('hc', 9)

    If pattern doesn't match cleanly, returns (None, None).
    """
    s = code.strip()
    prefix_chars = []
    number_chars = []
    seen_digit = False

    for ch in s:
        if ch.isdigit():
            seen_digit = True
            number_chars.append(ch)
        else:
            if not seen_digit:
                if ch.isalpha():
                    prefix_chars.append(ch)
                else:
                    # treat '-' and other non-alpha as delimiters
                    continue
            else:
                # ignore any trailing non-digits once numbers start
                continue

    if not prefix_chars or not number_chars:
        return None, None

    prefix = "".join(prefix_chars).lower()
    number = int("".join(number_chars))
    return prefix, number


def canonical_code(prefix: Optional[str], number: Optional[int], raw_code: str) -> str:
    """
    Build a canonical construct_code.

    If prefix/number are available, use PREFIX-NNN (PREFIX uppercase, NNN zero-padded).
    Else fall back to the raw_code.
    """
    if prefix is None or number is None:
        return raw_code.strip()
    return f"{prefix.upper()}-{number:03d}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v10: load constructs + construct_plasmids from constructs_plasmid.csv"
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
        raise SystemExit(f"constructs_plasmid.csv not found: {path}")

    df = pd.read_csv(path)
    print(f"[v10_load_constructs] read {len(df)} row(s) from {path}")

    required = ["plasmid_code", "plasmid_name"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"constructs CSV missing required columns: {missing}; found {list(df.columns)}")

    df = df.copy()
    df["plasmid_code"] = df["plasmid_code"].astype(str).str.strip()
    df["plasmid_name"] = df["plasmid_name"].astype(str).str.strip()
    df["plasmid_notes"] = (
        df.get("plasmid_notes", df.get("notes", ""))
          .astype(str)
          .fillna("")
          .str.strip()
    )
    df["resistance"] = (
        df.get("resistance", "")
          .astype(str)
          .fillna("")
          .str.strip()
    )

    # drop empty codes, dedupe by plasmid_code
    df = df[df["plasmid_code"] != ""].drop_duplicates(subset=["plasmid_code"])

    # derive series_prefix/series_number and canonical_code
    df["series_prefix"] = None
    df["series_number"] = None
    df["canonical_code"] = None
    for idx, code in df["plasmid_code"].items():
        prefix, number = split_series(code)
        df.at[idx, "series_prefix"] = prefix
        df.at[idx, "series_number"] = number
        df.at[idx, "canonical_code"] = canonical_code(prefix, number, code)

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
          series_number
        )
        VALUES (
          :base_code,
          :code,
          'plasmid',
          :name,
          :desc,
          :prefix,
          :number
        )
        ON CONFLICT (construct_code) DO UPDATE SET
          base_code      = EXCLUDED.base_code,
          construct_kind = EXCLUDED.construct_kind,
          construct_name = EXCLUDED.construct_name,
          description    = EXCLUDED.description,
          series_prefix  = EXCLUDED.series_prefix,
          series_number  = EXCLUDED.series_number
        RETURNING id::text AS construct_id
        """
    )

    sql_insert_plasmid = text(
        """
        INSERT INTO public.construct_plasmids (
          construct_id,
          resistance,
          backbone,
          notes
        )
        VALUES (
          :construct_id,
          :resistance,
          NULL,
          :notes
        )
        ON CONFLICT (construct_id) DO UPDATE SET
          resistance = EXCLUDED.resistance,
          notes      = EXCLUDED.notes
        """
    )

    sql_insert_alias = text(
        """
        INSERT INTO public.construct_aliases (
          construct_id,
          alias,
          alias_kind,
          created_at
        )
        VALUES (
          :construct_id,
          :alias,
          :alias_kind,
          now()
        )
        ON CONFLICT (alias) DO UPDATE SET
          construct_id = EXCLUDED.construct_id,
          alias_kind   = EXCLUDED.alias_kind
        """
    )

    inserted_constructs = 0
    inserted_aliases = 0
    with engine.begin() as cx:
        for _, row in df.iterrows():
            raw_code  = row["plasmid_code"]
            name      = row["plasmid_name"]
            notes     = row["plasmid_notes"]
            resistance = row["resistance"]
            prefix    = row["series_prefix"]
            number    = row["series_number"]
            canon     = row["canonical_code"]

            res = cx.execute(
                sql_insert_construct,
                {
                    "base_code": canon,
                    "code": canon,
                    "name": name,
                    "desc": notes or None,
                    "prefix": prefix,
                    "number": number,
                },
            ).fetchone()
            construct_id = res._mapping["construct_id"]
            inserted_constructs += 1

            cx.execute(
                sql_insert_plasmid,
                {
                    "construct_id": construct_id,
                    "resistance": resistance or None,
                    "notes": notes or None,
                },
            )

            # insert plasmid_code as alias
            cx.execute(
                sql_insert_alias,
                {
                    "construct_id": construct_id,
                    "alias": raw_code,
                    "alias_kind": "plasmid_code_from_csv",
                },
            )
            inserted_aliases += 1

    print(f"[v10_load_constructs] upserted {inserted_constructs} construct(s)")
    print(f"[v10_load_constructs] upserted {inserted_aliases} alias row(s)")


if __name__ == "__main__":
    main()
