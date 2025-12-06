#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import List

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL environment variable DB_URL is not set")
    print(f"DB_URL={db_url}")
    return create_engine(db_url)


def main() -> None:
    eng = get_engine()

    sql = text(
        """
        WITH base_codes AS (
          SELECT DISTINCT base_code
          FROM public.constructs
          WHERE base_code IS NOT NULL
            AND TRIM(base_code) <> ''
        ),
        to_insert AS (
          SELECT
            bc.base_code AS transgene_base_code,
            bc.base_code AS nickname,
            bc.base_code AS display_name
          FROM base_codes bc
          LEFT JOIN public.transgenes t
            ON t.transgene_base_code = bc.base_code
          WHERE t.transgene_base_code IS NULL
        )
        INSERT INTO public.transgenes (
          transgene_base_code,
          nickname,
          display_name
        )
        SELECT
          transgene_base_code,
          nickname,
          display_name
        FROM to_insert
        RETURNING transgene_base_code;
        """
    )

    with eng.begin() as cx:
        rows = cx.execute(sql).fetchall()
        inserted_codes: List[str] = [r[0] for r in rows]

    print(f"[v11_seed_transgenes_from_constructs] inserted {len(inserted_codes)} transgene(s)")
    if inserted_codes:
        print("[v11_seed_transgenes_from_constructs] example codes:", ", ".join(inserted_codes[:10]))


if __name__ == "__main__":
    main()
