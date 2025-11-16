from __future__ import annotations

from typing import List, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection


def normalize_plasmid_fusions_table(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Strict normalization for seed plasmid_fusions.csv.

    Expected headers (exact, case-insensitive):
      plasmid_base_code,nickname,n_fluors_per_plasmid,fluor,tag,tag_pos
    """
    df = df_raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = [
        "plasmid_base_code",
        "nickname",
        "n_fluors_per_plasmid",
        "fluor",
        "tag",
        "tag_pos",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"plasmid_fusions CSV missing required column(s): {missing}")

    out = pd.DataFrame(
        {
            "plasmid_base_code": df["plasmid_base_code"].map(
                lambda v: "" if v is None else str(v).strip()
            ),
            "nickname": df["nickname"].map(lambda v: "" if v is None else str(v).strip()),
            "n_fluors_per_plasmid": df["n_fluors_per_plasmid"].map(
                lambda v: 0
                if v is None or str(v).strip().lower() in {"", "nan", "none", "null"}
                else int(float(str(v).strip()))
            ),
            "fluor": df["fluor"].map(lambda v: "" if v is None else str(v).strip()),
            "tag": df["tag"].map(lambda v: "" if v is None else str(v).strip()),
            "tag_pos": df["tag_pos"].map(lambda v: "" if v is None else str(v).strip()),
        }
    )

    out = out[out["plasmid_base_code"] != ""].copy()
    return out


def _resolve_plasmid_id(cx: Connection, base_code: str) -> str | None:
    return cx.execute(
        text("SELECT id::text FROM public.plasmids WHERE code = :c LIMIT 1"),
        {"c": base_code},
    ).scalar()


def _resolve_fluor_id(cx: Connection, name_or_alias: str) -> str | None:
    # direct match
    row = cx.execute(
        text(
            """
        SELECT id::text
        FROM public.fluors
        WHERE fluor_name = :c OR fluor_code = :c
        LIMIT 1
      """
        ),
        {"c": name_or_alias},
    ).scalar()
    if row:
        return row
    # alias
    return cx.execute(
        text(
            """
        SELECT target_id::text
        FROM public.join_aliases
        WHERE target_kind = 'fluor'
          AND alias_norm = lower(trim(:c))
        LIMIT 1
      """
        ),
        {"c": name_or_alias},
    ).scalar()


def _resolve_tag_id(cx: Connection, name_or_alias: str) -> str | None:
    row = cx.execute(
        text(
            """
        SELECT id::text
        FROM public.tags
        WHERE tag_name = :c OR tag_code = :c
        LIMIT 1
      """
        ),
        {"c": name_or_alias},
    ).scalar()
    if row:
        return row
    return cx.execute(
        text(
            """
        SELECT target_id::text
        FROM public.join_aliases
        WHERE target_kind = 'tag'
          AND alias_norm = lower(trim(:c))
        LIMIT 1
      """
        ),
        {"c": name_or_alias},
    ).scalar()


def _normalize_tag_pos(raw: str | None) -> str | None:
    s = (raw or "").strip()
    if not s:
        return None
    if s.lower() in {"nan", "none", "null"}:
        return None
    return s


def _get_or_create_fusion(
    cx: Connection, fluor_id: str, tag_id: str | None, tag_pos: str
) -> str:
    pos_norm = _normalize_tag_pos(tag_pos)

    row = cx.execute(
        text(
            """
        SELECT id::text
        FROM public.fusions
        WHERE fluor_id = :fid
          AND (
                (tag_id IS NULL AND :tid IS NULL) OR
                (tag_id = :tid)
              )
          AND COALESCE(tag_pos,'') = COALESCE(:pos,'')
        LIMIT 1
      """
        ),
        {"fid": fluor_id, "tid": tag_id, "pos": pos_norm or ""},
    ).mappings().first()
    if row:
        return row["id"]

    row = cx.execute(
        text(
            """
        INSERT INTO public.fusions (fluor_id, tag_id, tag_pos)
        VALUES (:fid, :tid, NULLIF(:pos,''))
        RETURNING id::text
      """
        ),
        {"fid": fluor_id, "tid": tag_id, "pos": pos_norm or ""},
    ).scalar()
    return str(row)


def load_plasmid_fusions_from_df(
    df_raw: pd.DataFrame, cx: Connection
) -> Tuple[int, List[str]]:
    """
    Validate and load plasmid fusions:

      - resolve plasmid_base_code -> plasmid_id
      - resolve fluor via name or alias
      - resolve optional tag via name or alias
      - find or create fusion(fluor_id, tag_id, tag_pos)
      - insert join_plasmid_fusions(plasmid_id, fusion_id)

    Returns:
      (valid_rows_loaded, warnings)
    """
    df = normalize_plasmid_fusions_table(df_raw)
    warnings: List[str] = []
    valid = 0

    for row in df.to_dict(orient="records"):
        pcode = row["plasmid_base_code"]
        fluor = row["fluor"]
        tag = row["tag"]
        pos = row["tag_pos"]

        pid = _resolve_plasmid_id(cx, pcode)
        if not pid:
            warnings.append(f"Plasmid fusion row skipped: plasmid '{pcode}' not found.")
            continue

        fid = _resolve_fluor_id(cx, fluor)
        if not fid:
            warnings.append(f"Plasmid fusion row skipped: fluor '{fluor}' not found.")
            continue

        t_raw = (tag or "").strip()
        tid: str | None = None
        if t_raw and t_raw.lower() not in {"nan", "none", "null"}:
            tid = _resolve_tag_id(cx, t_raw)
            if not tid:
                warnings.append(f"Plasmid fusion row skipped: tag '{tag}' not found.")
                continue
        # else: fluor-only fusion

        fusion_id = _get_or_create_fusion(cx, fid, tid, pos)

        cx.execute(
            text(
                """
          INSERT INTO public.join_plasmid_fusions (plasmid_id, fusion_id, created_at)
          VALUES (:pid, :fid, now())
          ON CONFLICT DO NOTHING
        """
            ),
            {"pid": pid, "fid": fusion_id},
        )

        valid += 1

    return valid, warnings
