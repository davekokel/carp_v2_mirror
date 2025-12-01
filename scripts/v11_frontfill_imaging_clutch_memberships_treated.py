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

    # 1) Ensure treated_clutches_v11 exists for all clutches used in imaging that have treat_codes.
    seed_sql = text(
        """
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
          'TREAT-' || c.clutch_code || '-00',
          t.id,
          NULL,
          NULL,
          now(),
          'seed_from_imaging_clutches_frontfill'
        FROM public.imaging_clutch_memberships m
        JOIN public.clutches c
          ON c.id = m.clutch_id
        JOIN public.v11_clutch_star cs
          ON cs.clutch_code = c.clutch_code
        JOIN LATERAL regexp_split_to_table(cs.treat_codes, ',') AS tc(treat_code)
          ON TRUE
        JOIN public.treatments t
          ON t.treat_code = trim(tc.treat_code)
        WHERE cs.treat_codes IS NOT NULL
          AND cs.treat_codes <> ''
        ON CONFLICT (treated_clutch_code) DO NOTHING;
        """
    )

    update_sql = text(
        """
        UPDATE public.imaging_clutch_memberships m
        SET treated_clutch_id = tc.id
        FROM public.treated_clutches_v11 tc
        WHERE m.treated_clutch_id IS NULL
          AND m.clutch_id = tc.clutch_id;
        """
    )

    with engine.begin() as cx:
        seed_res = cx.execute(seed_sql)
        try:
            n_seeded = seed_res.rowcount
        except Exception:
            n_seeded = None

        update_res = cx.execute(update_sql)
        try:
            n_updated = update_res.rowcount
        except Exception:
            n_updated = None

    print(f"[OK] Seeded treated_clutches for {n_seeded if n_seeded is not None else '?'} clutch(es).")
    print(f"[OK] Frontfilled treated_clutch_id for {n_updated if n_updated is not None else '?'} imaging_clutch_memberships row(s).")


if __name__ == "__main__":
    main()
