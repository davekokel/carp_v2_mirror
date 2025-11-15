from __future__ import annotations

from typing import Tuple, List

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection


_TAG_NAME_ALIASES = ["tag_name", "nickname", "name", "tag"]


def _pick_tag_name_col(cols: list[str]) -> str | None:
    for c in _TAG_NAME_ALIASES:
        if c in cols:
            return c
    return None


def _split_aliases(raw: str) -> List[str]:
    if raw is None:
        return []
    s = str(raw).strip()
    if s.lower() in {"", "nan", "none", "null"}:
        return []
    parts = [p.strip() for p in str(s).replace("|", ";").replace(",", ";").split(";") if p.strip()]
    seen, out = set(), []
    for p in parts:
        k = p.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


def normalize_tags_table(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Normalization for seed tags.xlsx.

    Expected logical fields:
      tag_name (or nickname/name/tag), aliases, localization, note, citation_link

    We normalize headers by stripping + lowercasing before checking.
    """
    df = df_raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    tag_col = _pick_tag_name_col(list(df.columns))
    if not tag_col:
        raise ValueError(
            "Tags sheet missing tag name column; tried: " + ", ".join(_TAG_NAME_ALIASES)
        )

    required = ["aliases", "localization", "note", "citation_link"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Tags sheet missing required column(s): {missing}")

    out = pd.DataFrame(
        {
            "tag_name": df[tag_col].map(lambda v: "" if v is None else str(v).strip()),
            "aliases": df["aliases"].map(lambda v: "" if v is None else str(v).strip()),
            "localization": df["localization"].map(lambda v: "" if v is None else str(v).strip()),
            "note": df["note"].map(lambda v: "" if v is None else str(v).strip()),
            "citation_link": df["citation_link"].map(lambda v: "" if v is None else str(v).strip()),
        }
    )

    # drop empty tag_name rows
    out = out[out["tag_name"] != ""].copy()

    if out["tag_name"].duplicated().any():
        dup = out[out["tag_name"].duplicated()]["tag_name"].unique().tolist()
        raise ValueError(f"Duplicate tag_name values in tags sheet: {dup}")

    return out


def upsert_tags(df_norm: pd.DataFrame, cx: Connection) -> Tuple[int, int]:
    """
    Upsert tags into public.tags and write aliases into public.join_aliases.

    Assumes schema:

      public.tags(
        id uuid pk,
        tag_code text NOT NULL,
        tag_name text,
        localization text,
        note text,
        citation_link text,
        ...
      )

      public.join_aliases(
        target_kind text,
        target_id uuid,
        alias text,
        alias_norm text,
        ...
      )
    """
    created = 0
    updated = 0

    select_stmt = text(
        """
      SELECT id FROM public.tags
      WHERE tag_name = :tag_name
      LIMIT 1
    """
    )

    insert_stmt = text(
        """
      INSERT INTO public.tags (tag_code, tag_name, localization, note, citation_link)
      VALUES (:tag_code, :tag_name, NULLIF(:localization,''), NULLIF(:note,''), NULLIF(:citation_link,''))
      RETURNING id
    """
    )

    update_stmt = text(
        """
      UPDATE public.tags
      SET localization  = NULLIF(:localization,''),
          note          = NULLIF(:note,''),
          citation_link = NULLIF(:citation_link,'')
      WHERE id = :id
    """
    )

    alias_stmt = text(
        """
      INSERT INTO public.join_aliases (target_kind, target_id, alias)
      VALUES ('tag', :tid, :alias)
      ON CONFLICT (target_kind, target_id, alias_norm) DO NOTHING
    """
    )

    for row in df_norm.to_dict(orient="records"):
        tag_name = row["tag_name"]
        localization = row["localization"]
        note = row["note"]
        citation_link = row["citation_link"]

        # For now, use tag_name as tag_code (computed in loader, not from CSV)
        tag_code = tag_name

        # 1) see if tag already exists
        existing = cx.execute(select_stmt, {"tag_name": tag_name}).mappings().first()
        if existing:
            tid = existing["id"]
            cx.execute(
                update_stmt,
                {
                    "id": tid,
                    "localization": localization,
                    "note": note,
                    "citation_link": citation_link,
                },
            )
            updated += 1
        else:
            new_row = cx.execute(
                insert_stmt,
                {
                    "tag_code": tag_code,
                    "tag_name": tag_name,
                    "localization": localization,
                    "note": note,
                    "citation_link": citation_link,
                },
            ).mappings().first()
            tid = new_row["id"]
            created += 1

        # 2) aliases into join_aliases
        for alias in _split_aliases(row.get("aliases", "")):
            cx.execute(alias_stmt, {"tid": tid, "alias": alias})

    return created, updated


def load_tags_from_df(
    df_raw: pd.DataFrame, cx: Connection
) -> Tuple[int, int, pd.DataFrame]:
    """
    High-level helper: normalize + upsert tags.
    Returns (created, updated, normalized_df)
    """
    df_norm = normalize_tags_table(df_raw)
    created, updated = upsert_tags(df_norm, cx)
    return created, updated, df_norm
