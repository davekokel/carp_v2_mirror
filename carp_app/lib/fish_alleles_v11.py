from __future__ import annotations

from typing import Iterable, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine

Allele = Tuple[str, int]


def upsert_fish_alleles(
    engine: Engine,
    *,
    fish_id: str,
    alleles: Iterable[Allele],
) -> None:
    rows = []
    for base_code, allele_number in alleles:
        if base_code is None:
            continue
        base = str(base_code).strip()
        if not base:
            continue
        try:
            num = int(allele_number)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "fish_id": fish_id,
                "base_code": base,
                "allele_number": num,
            }
        )
    if not rows:
        return

    sql = text(
        """
        INSERT INTO public.fish_transgene_alleles (
          fish_id,
          transgene_base_code,
          allele_number
        )
        VALUES (
          :fish_id,
          :base_code,
          :allele_number
        )
        ON CONFLICT (fish_id, transgene_base_code, allele_number)
        DO NOTHING;
        """
    )
    with engine.begin() as cx:
        cx.execute(sql, rows)
