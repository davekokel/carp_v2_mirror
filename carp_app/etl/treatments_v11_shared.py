from __future__ import annotations

from typing import Iterable
from sqlalchemy import text
from sqlalchemy.engine import Engine


def _clean_construct_codes(construct_codes: Iterable[str]) -> list[str]:
    codes: list[str] = []
    for raw in construct_codes:
        if raw is None:
            continue
        s = str(raw).strip()
        if not s:
            continue
        # allow "a;b,c" → split on both ; and ,
        for part in s.replace(";", ",").split(","):
            p = part.strip()
            if p:
                codes.append(p)
    return sorted(set(codes))


def ensure_treatment_mix_links(
    engine: Engine,
    treat_code: str,
    construct_codes: Iterable[str],
    created_by: str = "v11_treatment_loader",
) -> None:
    """
    Ensure that a treatment has:
      • at least one treatment_mixes row
      • one treatment_mix_constructs row per construct_code

    This uses only explicit construct_codes; no inference from treat_code.
    """
    codes = _clean_construct_codes(construct_codes)
    if not codes:
        return

    with engine.begin() as cx:
        treatment_id = cx.execute(
            text(
                """
                SELECT id
                FROM public.treatments
                WHERE treat_code = :treat_code
                LIMIT 1;
                """
            ),
            {"treat_code": treat_code},
        ).scalar()

        if not treatment_id:
            return

        mix_id = cx.execute(
            text(
                """
                SELECT id
                FROM public.treatment_mixes
                WHERE treatment_id = :treatment_id
                ORDER BY created_at
                LIMIT 1;
                """
            ),
            {"treatment_id": treatment_id},
        ).scalar()

        if not mix_id:
            mix_id = cx.execute(
                text(
                    """
                    INSERT INTO public.treatment_mixes (
                      id,
                      treatment_id,
                      created_at,
                      created_by,
                      notes
                    )
                    VALUES (
                      gen_random_uuid(),
                      :treatment_id,
                      now(),
                      :created_by,
                      'frontfilled by treatments loader'
                    )
                    RETURNING id;
                    """
                ),
                {
                    "treatment_id": treatment_id,
                    "created_by": created_by,
                },
            ).scalar()

        for code in codes:
            construct_id = cx.execute(
                text(
                    """
                    SELECT id
                    FROM public.constructs
                    WHERE construct_code = :construct_code
                    LIMIT 1;
                    """
                ),
                {"construct_code": code},
            ).scalar()

            if not construct_id:
                continue

            exists = cx.execute(
                text(
                    """
                    SELECT 1
                    FROM public.treatment_mix_constructs tmc
                    WHERE tmc.mix_id = :mix_id
                      AND tmc.construct_id = :construct_id
                    LIMIT 1;
                    """
                ),
                {"mix_id": mix_id, "construct_id": construct_id},
            ).scalar()

            if exists:
                continue

            cx.execute(
                text(
                    """
                    INSERT INTO public.treatment_mix_constructs (
                      id,
                      mix_id,
                      construct_id,
                      created_at,
                      created_by
                    )
                    VALUES (
                      gen_random_uuid(),
                      :mix_id,
                      :construct_id,
                      now(),
                      :created_by
                    );
                    """
                ),
                {
                    "mix_id": mix_id,
                    "construct_id": construct_id,
                    "created_by": created_by,
                },
            )
