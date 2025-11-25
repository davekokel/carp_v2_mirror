from __future__ import annotations

import os
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or DB_URL env")
    print(f"DB_URL={url}")
    return create_engine(url)


SQL = text(
    """
    WITH gp AS (
      SELECT
        f.id         AS fish_id,
        f.fish_code  AS fish_code,
        string_agg(
          DISTINCT jfta.transgene_base_code || '(' ||
            CASE
              WHEN ta.allele_name IS NULL OR ta.allele_name = ''
                THEN ta.allele_number::text
              ELSE ta.allele_name
            END || ')',
          ', ' ORDER BY jfta.transgene_base_code || '(' ||
                         CASE
                           WHEN ta.allele_name IS NULL OR ta.allele_name = ''
                             THEN ta.allele_number::text
                           ELSE ta.allele_name
                         END || ')'
        ) AS genotype_pretty
      FROM public.fish_instance f
      LEFT JOIN public.join_fish_transgene_alleles jfta
        ON jfta.fish_id = f.id
      LEFT JOIN public.transgene_alleles ta
        ON ta.transgene_base_code = jfta.transgene_base_code
       AND ta.allele_number       = jfta.allele_number
      GROUP BY f.id, f.fish_code
    )
    SELECT
      f.fish_code,
      f.nickname,
      f.genetic_background,
      f.line_building_stage,
      gp.genotype_pretty
    FROM public.fish_instance f
    LEFT JOIN gp ON gp.fish_id = f.id
    WHERE gp.genotype_pretty IS NULL
       OR gp.genotype_pretty = ''
    ORDER BY f.created_at DESC NULLS LAST, f.fish_code;
    """
)


def main() -> None:
    engine = get_engine(os.environ.get("DB_URL"))
    with engine.begin() as cx:
        df = pd.read_sql(SQL, cx)

    print(f"[v9_report_fish_missing_genotypes] rows with empty genotype_pretty: {len(df)}")
    if df.empty:
        return

    # Print a compact table to stdout
    pd.set_option("display.max_rows", 200)
    pd.set_option("display.width", 160)
    print(df.to_string(index=False))

    # Also write to CSV in case you want to open in Excel
    out_path = "fish_missing_genotypes_v9.csv"
    df.to_csv(out_path, index=False)
    print(f"[v9_report_fish_missing_genotypes] wrote CSV to {out_path}")


if __name__ == "__main__":
    main()
