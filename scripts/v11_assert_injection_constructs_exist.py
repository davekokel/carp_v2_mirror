#!/usr/bin/env python3
from __future__ import annotations

import os
from sqlalchemy import create_engine, text


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL must be set")

    eng = create_engine(db_url)
    sql = text(
        """
        WITH inj_markers AS (
          SELECT
            t.treat_code,
            lower(regexp_replace(t.treat_code, '^INJ-'::text, ''::text)) AS inj_base_code,
            c.id::text   AS construct_id,
            c.construct_code,
            c.base_code
          FROM public.treatments t
          LEFT JOIN public.constructs c
            ON lower(c.base_code) = lower(regexp_replace(t.treat_code, '^INJ-'::text, ''::text))
            OR lower(c.construct_code) = lower(regexp_replace(t.treat_code, '^INJ-'::text, ''::text))
          WHERE t.treat_code ILIKE 'INJ-%'
        )
        SELECT
          treat_code,
          inj_base_code,
          construct_id,
          construct_code,
          base_code
        FROM inj_markers
        WHERE construct_id IS NULL
        ORDER BY treat_code;
        """
    )

    with eng.begin() as cx:
        rows = list(cx.execute(sql))

    if not rows:
        print("[OK] All INJ-* treatments map to existing constructs.")
        return

    print("[ERROR] Found INJ-* treatments whose base codes do not map to any construct:")
    for treat_code, inj_base_code, construct_id, construct_code, base_code in rows:
        print(
            f"  treat_code={treat_code} inj_base_code={inj_base_code} "
            f"construct_id={construct_id} construct_code={construct_code} base_code={base_code}"
        )

    raise SystemExit("Refusing to proceed: some INJ-* treatments refer to non-existent constructs.")
    

if __name__ == "__main__":
    main()
