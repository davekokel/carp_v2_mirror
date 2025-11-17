from __future__ import annotations

import sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import os
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from carp_app.etl.code_normalization import normalize_base_code


ROOT = Path(__file__).resolve().parents[1]
STD_ROOT = ROOT / "carp_app" / "seed_kits" / "standard_from_legacy"


def get_engine_from_env() -> Engine:
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL is not set in environment")
    return create_engine(db_url)


def _find_parent_csv(std_root: Path) -> Path:
    candidates = sorted(std_root.glob("Unique_parent_names__mom_dad*_preview_*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"No Unique_parent_names__mom_dad*_preview_*.csv found in {std_root}"
        )
    return candidates[0]


def _is_casper_rnf(name: Optional[str]) -> bool:
    if not name:
        return False
    s = str(name).strip().lower().replace(" ", "")
    return "casper/rnf" in s


def main() -> int:
    print(f"DB_URL={os.getenv('DB_URL')}")
    std_root = STD_ROOT
    std_root.mkdir(parents=True, exist_ok=True)

    parent_csv = _find_parent_csv(std_root)
    print(f"Using legacy parent CSV: {parent_csv}")

    df_parent = pd.read_csv(parent_csv)
    required = ["parent_fish_name", "plasmid_base_code", "allele"]
    missing = [c for c in required if c not in df_parent.columns]
    if missing:
        raise ValueError(f"Parent CSV missing columns: {missing}")

    engine = get_engine_from_env()
    with engine.begin() as cx:
        df_alleles = pd.read_sql(
            text(
                """
                SELECT
                  ta.transgene_base_code,
                  ta.allele_number,
                  ta.allele_nickname,
                  f.id   AS fish_id,
                  f.fish_code,
                  f.nickname
                FROM public.transgene_alleles ta
                JOIN public.join_fish_transgene_alleles jfta
                  ON jfta.transgene_base_code = ta.transgene_base_code
                 AND jfta.allele_number       = ta.allele_number
                JOIN public.fish_instance f
                  ON f.id = jfta.fish_id
                """
            ),
            cx,
        )
        df_casper = pd.read_sql(
            text(
                """
                SELECT
                  f.id,
                  f.fish_code,
                  f.genetic_background
                FROM public.fish_instance f
                WHERE f.genetic_background = 'casper'
                ORDER BY f.birthday NULLS LAST, f.fish_code
                """
            ),
            cx,
        )

    if df_alleles.empty:
        print("WARNING: No transgene_alleles / fish_instance links in DB; everything will look unmapped.")
    print(f"transgene_alleles in DB (with fish links): {len(df_alleles)}")
    print(f"casper fish_instance candidates: {len(df_casper)}")

    df_alleles["norm_base_code"] = df_alleles["transgene_base_code"].map(normalize_base_code)
    df_alleles["allele_nickname"] = (
        df_alleles["allele_nickname"].fillna("").astype(str).str.strip()
    )

    records: list[dict[str, object]] = []

    for _, row in df_parent.iterrows():
        parent_name = (
            str(row["parent_fish_name"]).strip()
            if pd.notna(row["parent_fish_name"])
            else ""
        )
        raw_base = (
            str(row["plasmid_base_code"]).strip()
            if pd.notna(row["plasmid_base_code"])
            else ""
        )
        allele_raw = (
            str(row["allele"]).strip() if pd.notna(row["allele"]) else ""
        )

        if not parent_name:
            continue

        norm_base = normalize_base_code(raw_base)
        allele_nick = allele_raw.strip()

        if _is_casper_rnf(parent_name):
            if not df_casper.empty:
                n_match_alleles = 0
                n_match_fish = 1
            else:
                n_match_alleles = 0
                n_match_fish = 0
        else:
            if not norm_base or not allele_nick:
                n_match_alleles = 0
                n_match_fish = 0
            else:
                mask = (df_alleles["norm_base_code"] == norm_base) & (
                    df_alleles["allele_nickname"] == allele_nick
                )
                sub = df_alleles.loc[mask]
                n_match_alleles = (
                    sub[["norm_base_code", "allele_number"]]
                    .drop_duplicates()
                    .shape[0]
                )
                n_match_fish = sub["fish_id"].nunique()

        records.append(
            {
                "parent_fish_name": parent_name,
                "raw_plasmid_base_code": raw_base,
                "norm_plasmid_base_code": norm_base,
                "allele_nickname": allele_nick,
                "n_matching_alleles": n_match_alleles,
                "n_matching_fish": n_match_fish,
            }
        )

    df_debug = pd.DataFrame(records)
    debug_csv = std_root / "legacy_parent_match_debug_v2.csv"
    df_debug.to_csv(debug_csv, index=False)
    print(f"Wrote legacy parent match debug to: {debug_csv}")
    print(f"Rows: {len(df_debug)}")

    casper_mask = df_debug["parent_fish_name"].fillna("").str.contains(
        "casper/rnf", case=False
    )

    problematic = df_debug[
        ((df_debug["n_matching_alleles"] == 0) | (df_debug["n_matching_fish"] == 0))
        & ~casper_mask
    ]
    if not problematic.empty:
        print("Problematic rows (no alleles or no fish, excluding casper/rnf):")
        print(problematic.to_string(index=False))
    else:
        print("All non-casper/rnf parents had at least one allele and fish match.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
