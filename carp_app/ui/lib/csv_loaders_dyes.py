from __future__ import annotations

from typing import Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection


def normalize_dyes_table(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Strict normalization for seed dyes.csv.

    Expected headers (exact, case-insensitive):
      nickname,localization,excitation_nm,emission_nm
    """
    df = df_raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["nickname", "localization", "excitation_nm", "emission_nm"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Dyes CSV missing required column(s): {missing}")

    out = pd.DataFrame(
        {
            "nickname": df["nickname"].map(lambda v: "" if v is None else str(v).strip()),
            "localization": df["localization"].map(lambda v: "" if v is None else str(v).strip()),
            "excitation_nm": df["excitation_nm"].map(
                lambda v: None
                if v is None or str(v).strip().lower() in {"", "nan", "none", "null"}
                else int(float(str(v).strip()))
            ),
            "emission_nm": df["emission_nm"].map(
                lambda v: None
                if v is None or str(v).strip().lower() in {"", "nan", "none", "null"}
                else int(float(str(v).strip()))
            ),
        }
    )

    # drop empty nicknames
    out = out[out["nickname"] != ""].copy()

    if out["nickname"].duplicated().any():
        dup = out[out["nickname"].duplicated()]["nickname"].unique().tolist()
        raise ValueError(f"Duplicate dye nickname values in dyes CSV: {dup}")

    return out


def upsert_dyes(df_norm: pd.DataFrame, cx: Connection) -> Tuple[int, int]:
    """
    Upsert dyes into public.dyes using nickname as the handle.

    Assumes schema roughly like:

      public.dyes(
        id uuid pk,
        dye_name text,
        localization text,
        excitation_nm smallint,
        emission_nm smallint,
        ...
      )

    We do NOT require or touch any 'dye_code' column at the DB level here.
    """
    created = 0
    updated = 0

    select_stmt = text("""
      SELECT id FROM public.dyes
      WHERE dye_name = :dye_name
      LIMIT 1
    """)

    insert_stmt = text("""
      INSERT INTO public.dyes (dye_name, localization, excitation_nm, emission_nm)
      VALUES (:dye_name, NULLIF(:localization,''), :excitation_nm, :emission_nm)
      RETURNING id
    """)

    update_stmt = text("""
      UPDATE public.dyes
      SET localization  = NULLIF(:localization,''),
          excitation_nm = :excitation_nm,
          emission_nm   = :emission_nm
      WHERE id = :id
    """)

    for row in df_norm.to_dict(orient="records"):
        dye_name = row["nickname"]
        localization = row["localization"]
        ex = row["excitation_nm"]
        em = row["emission_nm"]

        existing = cx.execute(select_stmt, {"dye_name": dye_name}).mappings().first()
        if existing:
            did = existing["id"]
            cx.execute(
                update_stmt,
                {
                    "id": did,
                    "localization": localization,
                    "excitation_nm": ex,
                    "emission_nm": em,
                },
            )
            updated += 1
        else:
            new_row = cx.execute(
                insert_stmt,
                {
                    "dye_name": dye_name,
                    "localization": localization,
                    "excitation_nm": ex,
                    "emission_nm": em,
                },
            ).mappings().first()
            _ = new_row["id"]
            created += 1

    return created, updated


def load_dyes_from_df(
    df_raw: pd.DataFrame, cx: Connection
) -> Tuple[int, int, pd.DataFrame]:
    """
    High-level helper: normalize + upsert dyes.
    Returns (created, updated, normalized_df)
    """
    df_norm = normalize_dyes_table(df_raw)
    created, updated = upsert_dyes(df_norm, cx)
    return created, updated, df_norm
