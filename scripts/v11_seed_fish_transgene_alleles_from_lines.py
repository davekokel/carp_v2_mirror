#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection


def get_engine(db_url: Optional[str] = None) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def ensure_global_allele_sequence(cx: Connection) -> None:
    cx.execute(text("CREATE SEQUENCE IF NOT EXISTS public.transgene_allele_number_seq;"))
    cx.execute(
        text(
            """
            SELECT setval(
              'public.transgene_allele_number_seq',
              GREATEST(
                COALESCE((SELECT max(allele_number) FROM public.transgene_alleles), 0) + 1,
                1
              ),
              false
            );
            """
        )
    )


def ensure_allele_for_transgene(cx: Connection, base_code: str) -> None:
    base_code = (base_code or "").strip().lower()
    if not base_code:
        return

    exists = cx.execute(
        text(
            """
            SELECT 1
            FROM public.transgene_alleles
            WHERE lower(transgene_base_code) = :bc
            LIMIT 1;
            """
        ),
        {"bc": base_code},
    ).fetchone()
    if exists:
        return

    cx.execute(
        text(
            """
            INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_name)
            VALUES (:bc, nextval('public.transgene_allele_number_seq'), NULL)
            ON CONFLICT (transgene_base_code, allele_number) DO NOTHING;
            """
        ),
        {"bc": base_code},
    )


def main() -> None:
    engine = get_engine()

    with engine.begin() as cx:
        ensure_global_allele_sequence(cx)

        rows = cx.execute(
            text(
                """
                SELECT DISTINCT lower(btrim(construct_code)) AS bc
                FROM public.fish_lines
                WHERE construct_code IS NOT NULL
                  AND btrim(construct_code) <> '';
                """
            )
        ).fetchall()

        n = 0
        for (bc,) in rows:
            if not bc:
                continue
            ensure_allele_for_transgene(cx, bc)
            n += 1

    print(f"[OK] ensured transgene_alleles for {n} transgene base_code(s)")


if __name__ == "__main__":
    main()
