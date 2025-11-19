import os
import argparse
from typing import Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL environment variable is not set")
    print(f"DB_URL={db_url}")
    return create_engine(db_url)


def upsert_genotypes(engine: Engine, df: pd.DataFrame) -> Tuple[int, int]:
    """
    Load canonical line-level genotypes into public.genotypes.

    Assumes columns in CSV:
      - genotype_code
      - genotype_name
      - genetic_background
      - source_system
      - notes
    """
    inserted = 0
    updated = 0

    required_cols = {
        "genotype_code",
        "genotype_name",
        "genetic_background",
        "source_system",
        "notes",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"genotypes CSV missing required columns: {missing}")

    sql = text(
        """
        INSERT INTO public.genotypes (
          genotype_code,
          genotype_name,
          genetic_background,
          source_system,
          notes
        )
        VALUES (
          :code,
          :name,
          :background,
          :source_system,
          :notes
        )
        ON CONFLICT (genotype_code) DO UPDATE SET
          genotype_name      = EXCLUDED.genotype_name,
          genetic_background = EXCLUDED.genetic_background,
          source_system      = EXCLUDED.source_system,
          notes              = EXCLUDED.notes
        """
    )

    with engine.begin() as cx:
        for _, row in df.iterrows():
            code = str(row["genotype_code"]).strip()
            if not code:
                continue

            params = {
                "code": code,
                "name": str(row["genotype_name"]).strip() if pd.notna(row["genotype_name"]) else None,
                "background": str(row["genetic_background"]).strip() if pd.notna(row["genetic_background"]) else None,
                "source_system": str(row["source_system"]).strip() if pd.notna(row["source_system"]) else None,
                "notes": str(row["notes"]).strip() if pd.notna(row["notes"]) else None,
            }
            cx.execute(sql, params)
            inserted += 1

    return inserted, updated


def upsert_genotype_alleles(engine: Engine, df: pd.DataFrame) -> Tuple[int, int]:
    """
    Load genotype → allele mappings into public.genotype_transgene_alleles.

    CRITICAL PER SPEC:
      - allele_number is canonical (1, 2, 3, …) from transgene_alleles.
      - allele_nickname is legacy shorthand (301, 315, …) and must NOT be
        treated as allele_number.

    So we:
      - Resolve (base_code, allele_nickname) -> allele_number via transgene_alleles.
      - If no match, we WARN and SKIP (treat as ambiguous).
    """
    inserted = 0
    updated = 0

    required_cols = {
        "genotype_code",
        "transgene_base_code",
        "allele_nickname",
        "zygosity",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"genotype_alleles CSV missing required columns: {missing}")

    allele_lookup_sql = text(
        """
        SELECT allele_number
        FROM public.transgene_alleles
        WHERE lower(transgene_base_code) = lower(:base_code)
          AND allele_nickname           = :allele_nickname
        """
    )

    insert_sql = text(
        """
        INSERT INTO public.genotype_transgene_alleles (
          genotype_code,
          transgene_base_code,
          allele_number,
          zygosity
        )
        VALUES (
          :genotype_code,
          :base_code,
          :allele_number,
          :zygosity
        )
        ON CONFLICT (genotype_code, transgene_base_code, allele_number) DO UPDATE SET
          zygosity = EXCLUDED.zygosity
        """
    )

    with engine.begin() as cx:
        for _, row in df.iterrows():
            genotype_code = str(row["genotype_code"]).strip()
            base_code = str(row["transgene_base_code"]).strip()
            allele_nickname = str(row["allele_nickname"]).strip()

            if not genotype_code or not base_code or not allele_nickname:
                continue

            allele_number = cx.execute(
                allele_lookup_sql,
                {"base_code": base_code, "allele_nickname": allele_nickname},
            ).scalar()

            if allele_number is None:
                print(
                    f"[WARN] genotype '{genotype_code}': "
                    f"(base_code='{base_code}', allele_nickname='{allele_nickname}') "
                    "not found in transgene_alleles; skipping"
                )
                continue

            params = {
                "genotype_code": genotype_code,
                "base_code": base_code,
                "allele_number": allele_number,
                "zygosity": str(row["zygosity"]).strip() if pd.notna(row["zygosity"]) else None,
            }
            cx.execute(insert_sql, params)
            inserted += 1

    return inserted, updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load v8 genotypes and genotype_transgene_alleles from standard fish seed CSVs"
    )
    parser.add_argument(
        "--genotypes-csv",
        required=True,
        help="Path to genotypes_from_standard_fish.csv",
    )
    parser.add_argument(
        "--genotype-alleles-csv",
        required=True,
        help="Path to genotype_alleles_from_standard_fish.csv",
    )
    args = parser.parse_args()

    engine = get_engine()

    if not os.path.exists(args.genotypes_csv):
        raise FileNotFoundError(f"genotypes CSV not found: {args.genotypes_csv}")
    if not os.path.exists(args.genotype_alleles_csv):
        raise FileNotFoundError(f"genotype_alleles CSV not found: {args.genotype_alleles_csv}")

    df_genotypes = pd.read_csv(args.genotypes_csv)
    df_alleles = pd.read_csv(args.genotype_alleles_csv)

    ins_genotypes, _ = upsert_genotypes(engine, df_genotypes)
    print(f"genotypes: handled={ins_genotypes}")

    ins_alleles, _ = upsert_genotype_alleles(engine, df_alleles)
    print(f"genotype_transgene_alleles: handled={ins_alleles}")


if __name__ == "__main__":
    main()
