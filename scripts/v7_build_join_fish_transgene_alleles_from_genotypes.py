from __future__ import annotations

import os
import pathlib
import sys
from typing import List

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def get_engine() -> Engine:
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL not set")
    return create_engine(db_url)

def main() -> None:
    engine = get_engine()
    print(f"DB_URL={os.getenv('DB_URL','')}")
    with engine.begin() as cx:
        rows = list(
            cx.execute(
                text(
                    """
                    SELECT
                      jfg.fish_id,
                      jgta.transgene_base_code,
                      jgta.allele_number,
                      jgta.zygosity
                    FROM public.join_fish_genotypes AS jfg
                    JOIN public.join_genotype_transgene_alleles AS jgta
                      ON jgta.genotype_id = jfg.genotype_id
                    """
                )
            ).mappings()
        )
        print(f"Found {len(rows)} fish×allele links from genotypes.")

        # Wipe and rebuild for these fish
        cx.execute(text("TRUNCATE TABLE public.join_fish_transgene_alleles;"))

        for row in rows:
            cx.execute(
                text(
                    """
                    INSERT INTO public.join_fish_transgene_alleles
                      (fish_id, transgene_base_code, allele_number, zygosity)
                    VALUES
                      (:fish_id, :base_code, :allele_number, :zyg)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "fish_id": row["fish_id"],
                    "base_code": row["transgene_base_code"],
                    "allele_number": row["allele_number"],
                    "zyg": (row["zygosity"] or None),
                },
            )

    print("Rebuilt join_fish_transgene_alleles from join_fish_genotypes × join_genotype_transgene_alleles.")

if __name__ == "__main__":
    main()
