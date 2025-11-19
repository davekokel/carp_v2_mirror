import os
import argparse
from typing import Dict, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL environment variable is not set")
    print(f"DB_URL={db_url}")
    return create_engine(db_url)


def load_existing_alleles(engine: Engine) -> Tuple[Dict[Tuple[str, str], int], int]:
    sql = text(
        """
        SELECT transgene_base_code, allele_number, allele_nickname
        FROM public.transgene_alleles
        """
    )
    mapping: Dict[Tuple[str, str], int] = {}
    max_num = 0

    with engine.begin() as cx:
        rows = cx.execute(sql).fetchall()

    for base_code, allele_number, nickname in rows:
        key = (str(base_code), "" if nickname is None else str(nickname))
        mapping[key] = allele_number
        if allele_number is not None and allele_number > max_num:
            max_num = allele_number

    return mapping, max_num


def upsert_transgenes_from_genotype_csv(engine: Engine, df: pd.DataFrame) -> int:
    required_cols = {"transgene_base_code"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"genotype_alleles CSV missing required columns: {missing}")

    insert_sql = text(
        """
        INSERT INTO public.transgenes (transgene_base_code)
        VALUES (:code)
        ON CONFLICT (transgene_base_code) DO NOTHING
        """
    )

    inserted = 0
    seen: set[str] = set()

    with engine.begin() as cx:
        for base_code in df["transgene_base_code"]:
            if pd.isna(base_code):
                continue
            code = str(base_code).strip()
            if not code or code in seen:
                continue
            seen.add(code)
            cx.execute(insert_sql, {"code": code})
            inserted += 1

    return inserted


def upsert_transgene_alleles_from_genotype_csv(engine: Engine, df: pd.DataFrame) -> int:
    required_cols = {"transgene_base_code", "allele_nickname"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"genotype_alleles CSV missing required columns: {missing}")

    existing, max_num = load_existing_alleles(engine)

    insert_sql = text(
        """
        INSERT INTO public.transgene_alleles (
          transgene_base_code,
          allele_number,
          allele_name,
          allele_nickname
        )
        VALUES (
          :base_code,
          :allele_number,
          :allele_name,
          :allele_nickname
        )
        ON CONFLICT (transgene_base_code, allele_number) DO NOTHING
        """
    )

    inserted = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            raw_base = row.get("transgene_base_code")
            if pd.isna(raw_base):
                continue
            base_code = str(raw_base).strip()
            if not base_code:
                continue

            nick_raw = row.get("allele_nickname")
            nickname = ""
            if pd.notna(nick_raw):
                nickname = str(nick_raw).strip()

            key = (base_code, nickname)

            if key in existing:
                continue

            max_num += 1
            allele_number = max_num
            allele_name = f"gu{allele_number}"

            cx.execute(
                insert_sql,
                {
                    "base_code": base_code,
                    "allele_number": allele_number,
                    "allele_name": allele_name,
                    "allele_nickname": nickname if nickname else None,
                },
            )
            existing[key] = allele_number
            inserted += 1

    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v8: load transgenes + transgene_alleles from standard genotype_alleles CSV"
    )
    parser.add_argument(
        "--genotype-alleles-csv",
        required=True,
        help="Path to genotype_alleles_from_standard_fish.csv",
    )
    args = parser.parse_args()

    csv_path = args.genotype_alleles_csv
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"genotype_alleles CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    engine = get_engine()

    ins_transgenes = upsert_transgenes_from_genotype_csv(engine, df)
    print(f"transgenes: newly_inserted={ins_transgenes}")

    ins_alleles = upsert_transgene_alleles_from_genotype_csv(engine, df)
    print(f"transgene_alleles: newly_inserted={ins_alleles}")


if __name__ == "__main__":
    main()
