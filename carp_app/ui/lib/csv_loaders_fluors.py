from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection


def _is_blank(x: Any) -> bool:
    if x is None:
        return True
    if isinstance(x, float) and math.isnan(x):
        return True
    s = str(x).strip().lower()
    return s in {"", "nan", "none", "null"}


def _to_smallint_or_none(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    s = str(v).strip().lower()
    if s in {"", "nan", "none", "null"}:
        return None
    try:
        iv = int(float(s))
    except Exception:
        return None
    return None if iv == 0 else iv


def _slug(s: str | None) -> str | None:
    if not s:
        return None
    return re.sub(r"[^a-z0-9]+", "-", str(s).strip().lower()).strip("-") or None


def _split_alts(x: Any) -> List[str]:
    if _is_blank(x):
        return []
    parts = [p.strip() for p in re.split(r"[;,|/]", str(x)) if p.strip()]
    seen, out = set(), []
    for p in parts:
        k = p.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


# header alias map (same as page)
_HEADER_ALIASES: Dict[str, List[str]] = {
    "fluor_name": ["fluor_name", "fluor_nickname", "fluor", "name", "nickname"],
    "excitation_nm": ["excitation_nm", "ex_nm", "exc", "excitation"],
    "emission_nm": ["emission_nm", "em_nm", "emi", "emission"],
    "alt_names": ["alt_names", "aliases", "aka", "alts"],
    "notes": ["notes", "note", "description", "desc"],
}


def _pick_header(df: pd.DataFrame, key: str) -> str | None:
    for c in _HEADER_ALIASES[key]:
        if c in df.columns:
            return c
    return None


def normalize_fluor_table(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Normalize a raw fluors table into the same shape the upload page uses:

      columns: fluor_name, excitation_nm, emission_nm, alt_names, notes, fluor_code

    Returns:
      (normalized_df, soft_warnings)
    """
    df = df_raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    col_nm = _pick_header(df, "fluor_name")
    col_ex = _pick_header(df, "excitation_nm")
    col_em = _pick_header(df, "emission_nm")
    col_al = _pick_header(df, "alt_names")
    col_nt = _pick_header(df, "notes")

    if not col_nm:
        raise ValueError("Missing required column: `fluor_name` (or `fluor_nickname`).")

    out = pd.DataFrame(
        {
            "fluor_name": df[col_nm].map(lambda v: None if _is_blank(v) else str(v).strip()),
            "excitation_nm": df[col_ex] if col_ex else None,
            "emission_nm": df[col_em] if col_em else None,
            "alt_names": df[col_al] if col_al else "",
            "notes": df[col_nt] if col_nt else "",
        }
    )

    out["excitation_nm"] = out["excitation_nm"].map(_to_smallint_or_none)
    out["emission_nm"] = out["emission_nm"].map(_to_smallint_or_none)
    out = out.astype({"excitation_nm": "object", "emission_nm": "object"})
    out["fluor_code"] = out["fluor_name"].map(_slug)

    soft_warn: List[str] = []
    unusual = out[
        (~out["excitation_nm"].isna() & ~out["excitation_nm"].between(250, 900))
        | (~out["emission_nm"].isna() & ~out["emission_nm"].between(250, 900))
    ]
    if not unusual.empty:
        soft_warn.append(
            f"{len(unusual)} row(s) have wavelengths outside 250–900 nm (accepted)."
        )

    return out, soft_warn


def build_fluor_rows(out: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    From normalized out, build the 'rows' list used for upsert:
      {"code","name","ex","em","alts","notes"}
    """
    rows: List[Dict[str, Any]] = []
    for r in out.itertuples(index=False):
        if not r.fluor_name or not r.fluor_code:
            continue
        ex = None if pd.isna(r.excitation_nm) else int(r.excitation_nm)
        em = None if pd.isna(r.emission_nm) else int(r.emission_nm)
        rows.append(
            {
                "code": r.fluor_code,
                "name": r.fluor_name,
                "ex": ex,
                "em": em,
                "alts": _split_alts(r.alt_names) if isinstance(r.alt_names, str) else None,
                "notes": (
                    r.notes
                    if isinstance(r.notes, str) and r.notes.strip()
                    else None
                ),
            }
        )
    return rows


def upsert_fluors(rows: List[Dict[str, Any]], cx: Connection) -> Tuple[int, int]:
    """
    Given normalized rows, perform upsert into public.fluors and join_aliases.
    Returns (created_count, updated_count).
    """
    if not rows:
        return 0, 0

    stmt = text(
        """
    INSERT INTO public.fluors (fluor_code, fluor_name, excitation_nm, emission_nm, alt_names, notes)
    VALUES (:code, :name, :ex, :em, :alts, :notes)
    ON CONFLICT (fluor_code) DO UPDATE
    SET  fluor_name    = EXCLUDED.fluor_name,
         excitation_nm = COALESCE(EXCLUDED.excitation_nm, public.fluors.excitation_nm),
         emission_nm   = COALESCE(EXCLUDED.emission_nm,   public.fluors.emission_nm),
         alt_names     = COALESCE(EXCLUDED.alt_names,     public.fluors.alt_names),
         notes         = COALESCE(EXCLUDED.notes,         public.fluors.notes)
    RETURNING id, (xmax = 0) AS inserted
"""
    )

    alias_stmt = text(
        """
  INSERT INTO public.join_aliases (target_kind, target_id, alias)
  VALUES ('fluor', :fid, :alias)
  ON CONFLICT (target_kind, target_id, alias_norm) DO NOTHING
"""
    )

    created = 0
    updated = 0

    for params in rows:
        m = cx.execute(stmt, params).mappings().first()
        if not m:
            continue
        fid = m["id"]
        if m.get("inserted"):
            created += 1
        else:
            updated += 1

        if params["name"]:
            cx.execute(alias_stmt, {"fid": fid, "alias": params["name"].strip()})

        if params["code"]:
            cx.execute(alias_stmt, {"fid": fid, "alias": params["code"].strip()})

        for alias in (params["alts"] or []):
            alias = alias.strip()
            if alias:
                cx.execute(alias_stmt, {"fid": fid, "alias": alias})

    return created, updated


def load_fluors_from_df(
    df_raw: pd.DataFrame, cx: Connection
) -> Tuple[int, int, List[Dict[str, Any]], List[str]]:
    """
    High-level helper:
      - normalize raw df
      - build rows
      - upsert into DB

    Returns:
      (created, updated, rows, soft_warnings)
    """
    out, soft_warnings = normalize_fluor_table(df_raw)
    rows = build_fluor_rows(out)
    created, updated = upsert_fluors(rows, cx)
    return created, updated, rows, soft_warnings
