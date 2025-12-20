from __future__ import annotations

import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set")
    print(f"DB_URL={url}")
    return create_engine(url)


def main() -> None:
    engine = get_engine()

    seed_sql = text(
        """
        WITH src AS (
          SELECT DISTINCT
            jct.clutch_id,
            jct.treatment_id
          FROM public.join_clutch_treatments jct
          JOIN public.imaging_clutch_memberships m
            ON m.clutch_id = jct.clutch_id
        ),
        ranked AS (
          SELECT
            src.clutch_id,
            src.treatment_id,
            row_number() OVER (PARTITION BY src.clutch_id ORDER BY src.treatment_id) - 1 AS idx0
          FROM src
        )
        INSERT INTO public.treated_clutches_v11 (
          id,
          clutch_id,
          treated_clutch_code,
          treatment_id,
          n_embryos,
          notes,
          created_at,
          created_by
        )
        SELECT
          gen_random_uuid(),
          c.id,
          ('TREAT-' || c.clutch_code || '-' || lpad(r.idx0::text, 2, '0')),
          r.treatment_id,
          NULL,
          'seed_from_join_clutch_treatments',
          now(),
          'v11_frontfill_imaging_clutch_memberships_treated'
        FROM ranked r
        JOIN public.clutches c
          ON c.id = r.clutch_id
        ON CONFLICT (treated_clutch_code) DO NOTHING;
        """
    )

    update_sql = text(
        """
        WITH counts AS (
          SELECT clutch_id, count(*) AS n
          FROM public.treated_clutches_v11
          GROUP BY clutch_id
        ),
        one_tc AS (
          SELECT tc.clutch_id, tc.id AS treated_clutch_id
          FROM public.treated_clutches_v11 tc
          JOIN counts c
            ON c.clutch_id = tc.clutch_id
          AND c.n = 1
        )
        UPDATE public.imaging_clutch_memberships m
        SET treated_clutch_id = one_tc.treated_clutch_id
        FROM one_tc
        WHERE m.treated_clutch_id IS NULL
          AND m.clutch_id = one_tc.clutch_id;
        """
    )

    qc_sql = text(
        """
        SELECT
          (SELECT count(*) FROM public.join_clutch_treatments) AS n_join_clutch_treatments,
          (SELECT count(*) FROM public.treated_clutches_v11) AS n_treated_clutches_v11,
          (SELECT count(*) FROM public.imaging_clutch_memberships) AS n_imaging_memberships,
          (SELECT count(*) FROM public.imaging_clutch_memberships WHERE treated_clutch_id IS NOT NULL) AS n_memberships_with_treated_clutch_id,
          (SELECT count(*) FROM public.imaging_clutch_memberships m
            JOIN public.join_clutch_treatments jct ON jct.clutch_id = m.clutch_id
            LEFT JOIN public.treated_clutches_v11 tc ON tc.clutch_id = m.clutch_id
            WHERE tc.id IS NULL
          ) AS n_memberships_with_join_treatments_but_no_treated_clutch,
          (SELECT count(*) FROM public.imaging_clutch_memberships m
            JOIN (
              SELECT clutch_id
              FROM public.treated_clutches_v11
              GROUP BY clutch_id
              HAVING count(*) > 1
            ) multi ON multi.clutch_id = m.clutch_id
            WHERE m.treated_clutch_id IS NULL
          ) AS n_memberships_multi_treatment_left_null
        ;
        """
    )

    with engine.begin() as cx:
        seed_res = cx.execute(seed_sql)
        try:
            n_seeded = seed_res.rowcount
        except Exception:
            n_seeded = None

        upd_res = cx.execute(update_sql)
        try:
            n_updated = upd_res.rowcount
        except Exception:
            n_updated = None

        qc = cx.execute(qc_sql).fetchone()

    print(f"[OK] Seeded treated_clutches_v11 rows: {n_seeded if n_seeded is not None else '?'}")
    print(f"[OK] Updated imaging_clutch_memberships.treated_clutch_id rows: {n_updated if n_updated is not None else '?'}")
    if qc is not None:
        print("[QC]", dict(qc._mapping))


if __name__ == "__main__":
    main()
