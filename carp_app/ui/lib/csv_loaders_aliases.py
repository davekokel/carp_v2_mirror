from __future__ import annotations

from typing import List, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection


def normalize_alias_table(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Strict normalization for seed alias.csv.

    Expected headers (exact):
      target_kind,target_key,alias
    """
    df = df_raw.copy()
    df.columns = [str(c).strip() for c in df.columns]

    required = ["target_kind", "target_key", "alias"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Alias CSV missing required column(s): {missing}")

    out = pd.DataFrame(
        {
            "target_kind": df["target_kind"].map(lambda v: "" if v is None else str(v).strip().lower()),
            "target_key": df["target_key"].map(lambda v: "" if v is None else str(v).strip()),
            "alias": df["alias"].map(lambda v: "" if v is None else str(v).strip()),
        }
    )

    out = out[(out["target_kind"] != "") & (out["target_key"] != "") & (out["alias"] != "")].copy()
    return out


def _resolve_fluor_id(cx: Connection, key: str) -> str | None:
    # Try slug/code first, then fluor_name/nickname
    return cx.execute(
        text(
            """
        SELECT id
        FROM public.fluors
        WHERE fluor_code = :k OR fluor_name = :k
        LIMIT 1
      """
        ),
        {"k": key},
    ).scalar()


def _resolve_tag_id(cx: Connection, key: str) -> str | None:
    # Assumes public.tags(tag_name, ...) with tag_name = key
    return cx.execute(
        text(
            """
        SELECT id
        FROM public.tags
        WHERE tag_name = :k
        LIMIT 1
      """
        ),
        {"k": key},
    ).scalar()


def load_aliases_from_df(df_raw: pd.DataFrame, cx: Connection) -> Tuple[int, List[str]]:
    """
    Insert aliases into public.join_aliases using target_kind/target_key.

    Supports:
      - target_kind='fluor' (target_key matches fluor_code or fluor_name)
      - target_kind='tag'   (target_key matches tag_name)

    Returns:
      (inserted_count, warnings)
    """
    df_norm = normalize_alias_table(df_raw)
    warnings: List[str] = []
    inserted = 0

    alias_stmt = text(
        """
      INSERT INTO public.join_aliases (target_kind, target_id, alias)
      VALUES (:kind, :tid, :alias)
      ON CONFLICT (target_kind, target_id, alias_norm) DO NOTHING
    """
    )

    for row in df_norm.to_dict(orient="records"):
        kind = row["target_kind"]
        key = row["target_key"]
        alias = row["alias"]

        if kind == "fluor":
            tid = _resolve_fluor_id(cx, key)
        elif kind == "tag":
            tid = _resolve_tag_id(cx, key)
        else:
            warnings.append(f"Skipped alias for unsupported target_kind '{kind}' with key '{key}'.")
            continue

        if not tid:
            warnings.append(f"Skipped alias: target not found for kind='{kind}' key='{key}'.")
            continue

        res = cx.execute(alias_stmt, {"kind": kind, "tid": tid, "alias": alias})
        if res.rowcount:
            inserted += 1

    return inserted, warnings
