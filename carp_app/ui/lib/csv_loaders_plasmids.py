from __future__ import annotations

from typing import Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection


def normalize_plasmid_table(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Strict normalization for seed plasmids.csv.

    Expected headers (exact, case-insensitive):
      plasmid_base_code,nickname,notes
    """
    df = df_raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["plasmid_base_code", "nickname", "notes"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Plasmids CSV missing required column(s): {missing}")

    out = pd.DataFrame(
        {
            "code": df["plasmid_base_code"].map(lambda v: "" if v is None else str(v).strip()),
            "nickname": df["nickname"].map(lambda v: "" if v is None else str(v).strip()),
            "notes": df["notes"].map(
                lambda v: ""
                if v is None or str(v).strip().lower() in {"", "nan", "none", "null"}
                else str(v).strip()
            ),
        }
    )

    # use base code as human-readable name for now
    out["name"] = out["code"]

    # drop empty codes
    out = out[out["code"] != ""].copy()

    if out["code"].duplicated().any():
        dup = out[out["code"].duplicated()]["code"].unique().tolist()
        raise ValueError(f"Duplicate plasmid codes in CSV: {dup}")

    return out


def upsert_plasmids(df_norm: pd.DataFrame, cx: Connection) -> Tuple[int, int]:
    """
    Upsert plasmids into public.plasmids.

    Assumes schema with at least:
      - code (unique)
      - name
      - nickname (optional)
      - notes (optional)
    """
    created = 0
    updated = 0

    stmt = text(
        """
      INSERT INTO public.plasmids (code, name, nickname, notes)
      VALUES (:code, :name, NULLIF(:nickname,''), NULLIF(:notes,''))
      ON CONFLICT (code) DO UPDATE
        SET name     = EXCLUDED.name,
            nickname = COALESCE(EXCLUDED.nickname, public.plasmids.nickname),
            notes    = COALESCE(EXCLUDED.notes,    public.plasmids.notes)
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


def load_plasmids_from_df(
    df_raw: pd.DataFrame, cx: Connection
) -> Tuple[int, int, pd.DataFrame]:
    """
    High-level helper:
      - normalize raw df
      - upsert into DB

    Returns:
      (created, updated, normalized_df)
    """
    df_norm = normalize_plasmid_table(df_raw)
    created, updated = upsert_plasmids(df_norm, cx)
    return created, updated, df_norm
