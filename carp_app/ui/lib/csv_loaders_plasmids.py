from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection


# Basic header aliasing; adjust to match your real plasmid CSVs/pages as needed.
_HEADER_ALIASES: Dict[str, List[str]] = {
    "code": ["code", "plasmid_code", "plasmid", "base_code", "plasmid_base_code"],
    "name": ["name", "plasmid_name", "description", "desc"],
    "nickname": ["nickname", "nick", "short_name", "alias"],
    "notes": ["notes", "note", "comments", "comment"],
}


def _pick_header(df: pd.DataFrame, key: str) -> str | None:
    for c in _HEADER_ALIASES[key]:
        if c in df.columns:
            return c
    return None


def normalize_plasmid_table(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize plasmid table into a simple shape:

      columns: code, name, nickname, notes

    If no explicit name/description column is present, we fall back to using `code`
    as the display name.
    """
    df = df_raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    col_code = _pick_header(df, "code")
    col_name = _pick_header(df, "name")
    col_nick = _pick_header(df, "nickname")
    col_notes = _pick_header(df, "notes")

    if not col_code:
        raise ValueError("Plasmids CSV missing required column: code / plasmid_code / plasmid_base_code.")

    # Fallback: if no name column, use code as name
    if not col_name:
        col_name = col_code

    out = pd.DataFrame(
        {
            "code": df[col_code].map(lambda v: "" if v is None else str(v).strip()),
            "name": df[col_name].map(lambda v: "" if v is None else str(v).strip()),
            "nickname": df[col_nick].map(lambda v: "" if v is None else str(v).strip())
            if col_nick
            else "",
            "notes": df[col_notes].map(lambda v: "" if v is None else str(v).strip())
            if col_notes
            else "",
        }
    )

    # drop empty codes
    out = out[out["code"] != ""].copy()

    # basic duplicate check
    if out["code"].duplicated().any():
        dup = out[out["code"].duplicated()]["code"].unique().tolist()
        raise ValueError(f"Duplicate plasmid codes in CSV: {dup}")

    return out


def upsert_plasmids(df_norm: pd.DataFrame, cx: Connection) -> Tuple[int, int]:
    """
    Upsert plasmids into public.plasmids.

    Assumes a schema with at least:
      - code (unique)
      - name
      - nickname (optional)
      - notes (optional)

    Adjust column names in the SQL to match your real schema.
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
