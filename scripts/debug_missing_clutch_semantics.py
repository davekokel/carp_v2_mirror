from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, text
import os

DB_URL = os.getenv("DB_URL")
LEGACY_CLUTCHES_CSV = "seed_kits/legacy_wrangling_v2/working/legacy_clutches_v9.csv"

def _n(s: str) -> str:
    return (str(s) if s is not None else "").strip()

def main() -> None:
    if not DB_URL:
        raise RuntimeError("DB_URL not set")
    eng = create_engine(DB_URL)

    # v11_clutch_star: which clutches are missing genotype and/or treatment?
    with eng.begin() as cx:
        star = pd.read_sql(
            text("""
              SELECT clutch_code,
                     COALESCE(genotype_base_codes,'') AS genotype_base_codes,
                     COALESCE(treat_codes,'')         AS treat_codes
              FROM public.v11_clutch_star
              ORDER BY clutch_code
            """),
            cx,
        )

    # legacy CSV: parents
    df_cl = pd.read_csv(LEGACY_CLUTCHES_CSV)

    merged = star.merge(
        df_cl[
            ["clutch_code", "parent_female_genotype_text", "parent_male_genotype_text"]
        ],
        on="clutch_code",
        how="left",
    )

    missing_geno = merged[merged["genotype_base_codes"].astype(str).str.strip() == ""].copy()
    missing_geno = missing_geno[
        ["clutch_code", "genotype_base_codes", "treat_codes",
         "parent_female_genotype_text", "parent_male_genotype_text"]
    ]

    print("[MISSING GENOTYPE_BASE_CODES]")
    for _, r in missing_geno.iterrows():
        print(
            f"{_n(r['clutch_code'])} | geno='' | tx='{_n(r['treat_codes'])}' "
            f"| mom='{_n(r['parent_female_genotype_text'])}' "
            f"| dad='{_n(r['parent_male_genotype_text'])}'"
        )

if __name__ == "__main__":
    main()
