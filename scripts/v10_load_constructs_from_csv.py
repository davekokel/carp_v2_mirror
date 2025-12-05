#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# repo root on sys.path so we can import construct_normalizer
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from carp_app.etl.construct_normalizer import normalize_construct_code


def norm(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip()


def norm_optional(s: Any) -> Optional[str]:
    if s is None:
        return None
    if isinstance(s, float) and math.isnan(s):
        return None
    s2 = str(s).strip()
    if not s2 or s2.lower() == "nan":
        return None
    return s2


def as_bool_flag(v: Any) -> bool:
    s = str(v).strip().lower()
    if not s:
        return False
    return s in {"1", "true", "t", "yes", "y"}


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v10: load constructs from constructs_plasmid.csv "
        "(canonical codes, plasmid kind, injection use flags)."
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

    csv_path = Path(args.constructs_csv)
    if not csv_path.exists():
        raise SystemExit(f"[v10_load_constructs] CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    print(f"[v10_load_constructs] read {len(df)} row(s) from {csv_path}")

    required = [
        "plasmid_code",
        "plasmid_name",
        "plasmid_nickname",
        "resistance",
        "plasmid_notes",
        "used_for_injection_plasmid",
        "used_for_injection_rna",
        "used_for_injection_crispr",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(
            f"[v10_load_constructs] missing required column(s): {missing}"
        )

    # Deduplicate to one row per plasmid_code for the base construct record
    df["plasmid_code"] = df["plasmid_code"].astype("string").fillna("").str.strip()
    base = (
        df.sort_values("plasmid_code")
        .groupby("plasmid_code", as_index=False)
        .first()
    )
    print(
        f"[v10_load_constructs] unique plasmid_code rows: {len(base)} "
        f"(from {len(df)} CSV rows)"
    )

    engine = get_engine(args.db_url)

    sql_upsert = text(
        """
        INSERT INTO public.constructs (
          construct_code,
          base_code,
          construct_kind,
          construct_name,
          resistance,
          plasmid_notes,
          description,
          injection_use_plasmid,
          injection_use_rna,
          injection_use_crispr,
          created_at
        )
        VALUES (
          :construct_code,
          :base_code,
          :construct_kind,
          :construct_name,
          :resistance,
          :plasmid_notes,
          :description,
          :use_plasmid,
          :use_rna,
          :use_crispr,
          now()
        )
        ON CONFLICT (construct_code) DO UPDATE SET
          construct_name          = EXCLUDED.construct_name,
          resistance              = EXCLUDED.resistance,
          plasmid_notes           = EXCLUDED.plasmid_notes,
          description             = EXCLUDED.description,
          injection_use_plasmid   = public.constructs.injection_use_plasmid
                                     OR EXCLUDED.injection_use_plasmid,
          injection_use_rna       = public.constructs.injection_use_rna
                                     OR EXCLUDED.injection_use_rna,
          injection_use_crispr    = public.constructs.injection_use_crispr
                                     OR EXCLUDED.injection_use_crispr
        ;
        """
    )

    inserted = 0
    updated = 0

    with engine.begin() as cx:
        for _, row in base.iterrows():
            raw_code = norm(row["plasmid_code"])
            if not raw_code:
                continue

            # physical kind is always plasmid for this CSV
            construct_kind = "plasmid"

            # canonical code (lowercase prefix + '-' + integer), via shared normalizer
            canonical = normalize_construct_code(raw_code)
            if not canonical:
                print(
                    f"[v10_load_constructs] WARN: plasmid_code={raw_code!r} "
                    "could not be normalized; skipping."
                )
                continue

            base_code = canonical  # we treat canonical as both code + base_code

            name = norm_optional(row.get("plasmid_nickname")) or norm_optional(
                row.get("plasmid_name")
            )
            resistance = norm_optional(row.get("resistance"))
            plasmid_notes = norm_optional(row.get("plasmid_notes"))
            description = plasmid_notes  # keep description ≈ notes for overview

            use_plasmid = as_bool_flag(row.get("used_for_injection_plasmid"))
            use_rna = as_bool_flag(row.get("used_for_injection_rna"))
            use_crispr = as_bool_flag(row.get("used_for_injection_crispr"))

            r = cx.execute(
                sql_upsert,
                {
                    "construct_code": canonical,
                    "base_code": base_code,
                    "construct_kind": construct_kind,
                    "construct_name": name,
                    "resistance": resistance,
                    "plasmid_notes": plasmid_notes,
                    "description": description,
                    "use_plasmid": use_plasmid,
                    "use_rna": use_rna,
                    "use_crispr": use_crispr,
                },
            )
            # We can't easily distinguish insert vs update from here without another query,
            # so just count total affected rows.
            inserted += 1

    print(f"[v10_load_constructs] upserted {inserted} construct(s)")


if __name__ == "__main__":
    main()
