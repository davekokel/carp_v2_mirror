from __future__ import annotations

from typing import Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection


def normalize_rna_table(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Strict normalization for seed rnas.csv.

    Expected headers (exact):
      rna_base_code,nickname,notes

    Produces columns:
      rna_code, nickname, notes
    """
    df = df_raw.copy()
    df.columns = [str(c).strip() for c in df.columns]

    required = ["rna_base_code", "nickname", "notes"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"RNAs CSV missing required column(s): {missing}")

    out = pd.DataFrame(
        {
            "rna_code": df["rna_base_code"].map(lambda v: "" if v is None else str(v).strip()),
            "nickname": df["nickname"].map(lambda v: "" if v is None else str(v).strip()),
            "notes": df["notes"].map(lambda v: "" if v is None else str(v).strip()),
        }
    )

    # drop empty codes
    out = out[out["rna_code"] != ""].copy()

    if out["rna_code"].duplicated().any():
        dup = out[out["rna_code"].duplicated()]["rna_code"].unique().tolist()
        raise ValueError(f"Duplicate RNA codes in CSV: {dup}")

    return out


def upsert_rnas(df_norm: pd.DataFrame, cx: Connection) -> Tuple[int, int]:
    """
    Upsert RNAs into public.rnas.

    Assumes a schema with at least:
      - rna_code (unique)
      - nickname (optional)
      - notes (optional)
    """
    created = 0
    updated = 0

    stmt = text(
        """
      INSERT INTO public.rnas (rna_code, nickname, notes)
      VALUES (:rna_code, NULLIF(:nickname,''), NULLIF(:notes,''))
      ON CONFLICT (rna_code) DO UPDATE
        SET nickname = COALESCE(EXCLUDED.nickname, public.rnas.nickname),
            notes    = COALESCE(EXCLUDED.notes,    public.rnas.notes)
      RETURNING (xmax = 0) AS inserted
    """
    )

    for row in df_norm.to_dict(orient="records"):
        m = cx.execute(stmt, row).mappings().first()
        if not m:
            continue
        if m.get("inserted"):
            created += 1
        else:
            updated += 1

    return created, updated


def load_rnas_from_df(
    df_raw: pd.DataFrame, cx: Connection
) -> Tuple[int, int, pd.DataFrame]:
    """
    High-level helper:
      - normalize raw df (rna_base_code → rna_code)
      - upsert into DB

    Returns:
      (created, updated, normalized_df)
    """
    df_norm = normalize_rna_table(df_raw)
    created, updated = upsert_rnas(df_norm, cx)
    return created, updated, df_norm
