#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Set, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# repo bootstrap so we can import the construct normalizer
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.construct_normalizer import normalize_construct_code  # type: ignore


def get_engine(db_url: str | None) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def _norm(s: object | None) -> str:
    if s is None:
        return ""
    return str(s).strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v11: seed transgenes + transgene_alleles from fish CSV using ensure_transgene_allele()."
    )
    parser.add_argument(
        "--fish-csv",
        required=True,
        help="Path to fish.csv (same file used by v11_seed_fish_from_csv.py)",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL (optional; defaults to env DB_URL)",
    )
    args = parser.parse_args()

    fish_path = Path(args.fish_csv)
    if not fish_path.exists():
        raise SystemExit(f"fish CSV not found: {fish_path}")

    df = pd.read_csv(fish_path)

    required_cols = {"transgene_base_code", "allele_nickname"}
    missing = required_cols - set(df.columns)
    if missing:
        raise SystemExit(
            f"fish CSV missing required columns {sorted(missing)}; "
            f"found {sorted(df.columns)}"
        )

    # Normalize raw columns
    df["transgene_base_code_raw"] = df["transgene_base_code"].map(_norm)
    df["allele_nickname_norm"] = df["allele_nickname"].map(_norm)

    # Drop rows without any transgene_base_code
    df = df[df["transgene_base_code_raw"] != ""].copy()
    if df.empty:
        print("[v11_seed_transgenes_alleles_from_fish_csv] No rows with transgene_base_code; nothing to do.")
        return

    # Apply the same normalizer as constructs loader
    df["base_code_canonical"] = df["transgene_base_code_raw"].map(
        lambda s: normalize_construct_code(_norm(s)) or ""
    )
    df = df[df["base_code_canonical"] != ""].copy()
    if df.empty:
        print("[v11_seed_transgenes_alleles_from_fish_csv] No rows with canonical basecodes; nothing to do.")
        return

    # Unique (canonical_base_code, allele_nickname) pairs
    pairs = (
        df[["base_code_canonical", "allele_nickname_norm"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    print(
        f"[v11_seed_transgenes_alleles_from_fish_csv] unique (canonical_base_code, allele_nickname) pairs: {len(pairs)}"
    )

    eng = get_engine(args.db_url)

    # Build known basecodes from constructs.construct_code
    with eng.begin() as cx:
        cdf = pd.read_sql(
            text(
                """
                SELECT construct_code
                FROM public.constructs
                WHERE construct_code IS NOT NULL
                  AND TRIM(construct_code) <> ''
                """
            ),
            cx,
        )

    known_bases: Set[str] = set()
    for _, row in cdf.iterrows():
        cc = _norm(row["construct_code"])
        if cc:
            known_bases.add(cc)
            known_bases.add(cc.lower())

    print(
        f"[v11_seed_transgenes_alleles_from_fish_csv] known canonical construct codes: {len(known_bases)//2}"
    )

    ensure_sql = text(
        """
        SELECT transgene_base_code, allele_number, allele_name, allele_nickname
        FROM public.ensure_transgene_allele(:base_code, :allele_nickname)
        """
    )

    seen: Set[Tuple[str, str]] = set()
    n_calls = 0
    skipped_unknown_base: Set[str] = set()

    with eng.begin() as cx:
        for _, row in pairs.iterrows():
            base_code = _norm(row["base_code_canonical"])
            nickname = _norm(row["allele_nickname_norm"]) or None

            if not base_code:
                continue

            key = (base_code, nickname or "")
            if key in seen:
                continue
            seen.add(key)

            # Enforce DOC 15: skip if canonical base_code not in constructs
            if base_code not in known_bases and base_code.lower() not in known_bases:
                skipped_unknown_base.add(base_code)
                continue

            res = cx.execute(
                ensure_sql,
                {"base_code": base_code, "allele_nickname": nickname},
            ).fetchone()
            if res is None:
                continue

            n_calls += 1

    print(
        f"[v11_seed_transgenes_alleles_from_fish_csv] processed {len(seen)} unique (base, nickname) pairs; "
        f"ensure_transgene_allele() called {n_calls} time(s)."
    )
    if skipped_unknown_base:
        print(
            "[v11_seed_transgenes_alleles_from_fish_csv] skipped canonical base_code(s) with no matching construct_code: "
            + ", ".join(sorted(skipped_unknown_base))
        )


if __name__ == "__main__":
    main()
