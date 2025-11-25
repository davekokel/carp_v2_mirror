from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL environment variable is not set")
    print(f"DB_URL={db_url}")
    return create_engine(db_url)


def main() -> None:
    ROOT = Path(__file__).resolve().parents[1]
    out_path = ROOT / "v10_fish_lines_report.csv"

    engine = get_engine()

    sql = text(
        """
        SELECT
          f.fish_code,
          f.nickname,
          f.genetic_background,
          f.line_building_stage,
          jfta.transgene_base_code,
          ta.allele_number,
          ta.allele_name,
          ta.allele_nickname
        FROM public.fish_instance f
        LEFT JOIN public.join_fish_transgene_alleles jfta
          ON jfta.fish_id = f.id
        LEFT JOIN public.transgene_alleles ta
          ON ta.transgene_base_code = jfta.transgene_base_code
         AND ta.allele_number       = jfta.allele_number
        ORDER BY
          f.fish_code,
          jfta.transgene_base_code,
          ta.allele_number
        """
    )

    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    print(f"[v10_report_fish_lines] fetched {len(df)} row(s)")

    df.to_csv(out_path, index=False)
    print(f"[v10_report_fish_lines] wrote report to {out_path}")


if __name__ == "__main__":
    main()
