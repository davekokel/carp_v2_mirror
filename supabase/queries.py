from __future__ import annotations

from typing import Any, Dict, List, Optional
import pandas as pd
from sqlalchemy import text

def load_fish_overview(engine, q: Optional[str] = None, limit: int = 1000) -> pd.DataFrame:
    try:
        lim = max(1, min(int(limit), 10000))
    except Exception:
        lim = 1000

    params: Dict[str, Any] = {"lim": lim}
    filters: List[str] = []
    if q and q.strip():
        params["p"] = f"%{q.strip()}%"
        filters.append(
            "("
            "  v.fish_code ilike %(p)s"
            "  or coalesce(v.name,'') ilike %(p)s"
            "  or coalesce(v.transgene_base_code_filled,'') ilike %(p)s"
            "  or coalesce(v.allele_code_filled,'') ilike %(p)s"
            "  or coalesce(v.created_by_enriched,'') ilike %(p)s"
            "  or coalesce(v.batch_label,'') ilike %(p)s"
            ")"
        )
    where_sql = (" where " + " and ".join(filters)) if filters else ""

    # Derive id from public.fish via fish_code; tolerate if join fails (id may be null)
    sql = f"""
    select
      f.id as id,
      v.fish_code,
      v.name,
      v.transgene_base_code_filled  as transgene_base_code,
      v.allele_code_filled          as allele_code,
      v.allele_name_filled          as allele_name,
      v.line_building_stage,
      v.date_birth,
      v.age_days,
      v.age_weeks,
      v.batch_label,
      v.last_plasmid_injection_at,
      v.plasmid_injections_text,
      v.last_rna_injection_at,
      v.rna_injections_text,
      v.created_at,
      v.created_by_enriched         as created_by
    from public.vw_fish_overview_with_label v
    left join public.fish f on f.fish_code = v.fish_code
    {where_sql}
    order by v.fish_code
    limit %(lim)s
    """
    return pd.read_sql_query(sql, con=engine, params=params)
# --- compat shim: fish_overview_minimal --------------------------------------
from typing import Any, Dict, List, Optional
import pandas as pd

def _resolve_engine(obj):
    try:
        # SQLAlchemy Engine
        from sqlalchemy.engine import Engine, Connection
        if isinstance(obj, Engine):
            return obj
        if isinstance(obj, Connection):
            return obj.engine
    except Exception:
        pass
    return obj  # hope it's already an Engine

def fish_overview_minimal(conn_or_engine: Any, q: Optional[str] = None, limit: int = 1000, require_links: bool = True) -> List[Dict[str, Any]]:
    """
    Back-compat for older UI code expecting Q.fish_overview_minimal(conn, q, limit, require_links).
    Delegates to load_fish_overview(engine), applies a simple text filter, trims columns,
    and returns list-of-dicts. `require_links` is accepted but not enforced (no-op).
    """
    eng = _resolve_engine(conn_or_engine)
    df = load_fish_overview(eng)

    # derive batch_display if not present
    if "batch_display" not in df.columns:
        if "batch_label" in df.columns and "seed_batch_id" in df.columns:
            df["batch_display"] = df["batch_label"].fillna(df["seed_batch_id"])
        else:
            df["batch_display"] = df.get("batch_label") or df.get("seed_batch_id")

    # simple q filter
    if q:
        ql = str(q).strip().lower()
        cols = [c for c in ["fish_code","name","nickname","batch_display","created_by"] if c in df.columns]
        mask = pd.Series(False, index=df.index)
        for c in cols:
            mask |= df[c].fillna("").astype(str).str.lower().str.contains(ql, na=False)
        df = df[mask]

    # select a minimal, tolerant column set
    preferred = ["id_uuid","fish_code","name","nickname","batch_display","created_by","date_birth","created_at"]
    cols = [c for c in preferred if c in df.columns]
    if cols:
        df = df[cols]

    # limit
    if isinstance(limit, int) and limit > 0:
        df = df.head(limit)

    return df.to_dict(orient="records")

# --- compat shim (fixed): fish_overview_minimal --------------------------------
# Re-define to avoid pandas boolean-ambiguous 'or' between Series.
from typing import Any, Dict, List, Optional
import pandas as pd

def fish_overview_minimal(conn_or_engine: Any, q: Optional[str] = None, limit: int = 1000, require_links: bool = True) -> List[Dict[str, Any]]:
    """
    Back-compat for older UI code expecting Q.fish_overview_minimal(conn, q, limit, require_links).
    Delegates to load_fish_overview(engine), applies simple text filter, trims columns,
    and returns list-of-dicts. `require_links` is accepted but not enforced (no-op).
    """
    eng = _resolve_engine(conn_or_engine)
    df = load_fish_overview(eng).copy()

    # Ensure expected columns exist (tolerant)
    for c in ["batch_label", "seed_batch_id", "fish_code", "name", "nickname", "created_by", "date_birth", "created_at", "id_uuid", "id"]:
        if c not in df.columns:
            df[c] = None

    # Derive batch_display safely
    s1 = df["batch_label"] if "batch_label" in df.columns else None
    s2 = df["seed_batch_id"] if "seed_batch_id" in df.columns else None
    if s1 is not None and s2 is not None:
        df["batch_display"] = s1.fillna(s2)
    elif s1 is not None:
        df["batch_display"] = s1
    elif s2 is not None:
        df["batch_display"] = s2
    else:
        df["batch_display"] = None

    # Simple q filter
    if q:
        ql = str(q).strip().lower()
        cols = [c for c in ["fish_code","name","nickname","batch_display","created_by"] if c in df.columns]
        mask = pd.Series(False, index=df.index)
        for c in cols:
            mask |= df[c].fillna("").astype(str).str.lower().str.contains(ql, na=False)
        df = df[mask]

    # Select a minimal, tolerant column set (prefer id_uuid but fallback to id)
    preferred = ["id_uuid","id","fish_code","name","nickname","batch_display","created_by","date_birth","created_at"]
    cols = [c for c in preferred if c in df.columns]
    if cols:
        df = df[cols]

    # Row limit
    if isinstance(limit, int) and limit > 0:
        df = df.head(limit)

    # Normalize id_uuid: if missing but 'id' exists, map it
    if "id_uuid" in df.columns and df["id_uuid"].isna().all() and "id" in df.columns:
        df["id_uuid"] = df["id"]

    return df.to_dict(orient="records")

# --- compat shim tweak: add filled transgene/allele fields and tolerant ids ---
import pandas as pd

def _first_nonnull(*series) -> pd.Series:
    # return first non-null across provided Series (or None)
    base = None
    for s in series:
        if s is None: 
            continue
        if base is None:
            base = s
        else:
            base = base.where(base.notna(), s)
    if base is None:
        # make a Series of Nones if we can't infer length
        return pd.Series(dtype="object")
    return base

def fish_overview_minimal(conn_or_engine, q=None, limit: int = 1000, require_links: bool = True):
    # (redefine with enriched columns expected by older pages)
    eng = _resolve_engine(conn_or_engine)
    df = load_fish_overview(eng).copy()

    # Ensure expected columns exist
    for c in ["id_uuid","id","fish_code","name","nickname","created_by","date_birth","created_at",
              "batch_label","seed_batch_id","transgene_base_code","allele_number","allele_code",
              "transgene_base_code_filled","allele_code_filled"]:
        if c not in df.columns:
            df[c] = None

    # batch_display safely
    s1 = df["batch_label"]
    s2 = df["seed_batch_id"]
    df["batch_display"] = _first_nonnull(s1, s2)

    # filled transgene base code
    df["transgene_base_code_filled"] = _first_nonnull(df.get("transgene_base_code_filled"),
                                                      df.get("transgene_base_code"))

    # filled allele code
    if "allele_code_filled" not in df or df["allele_code_filled"].isna().all():
        # start with allele_code if present
        df["allele_code_filled"] = df.get("allele_code")
        # build from base + allele_number where missing
        if "transgene_base_code" in df.columns and "allele_number" in df.columns:
            mask = df["allele_code_filled"].isna() & df["transgene_base_code"].notna() & df["allele_number"].notna()
            df.loc[mask, "allele_code_filled"] = (
                df.loc[mask, "transgene_base_code"].astype(str) + "-" + df.loc[mask, "allele_number"].astype(str)
            )

    # q filter
    if q:
        ql = str(q).strip().lower()
        cols = [c for c in ["fish_code","name","nickname","batch_display","created_by",
                             "transgene_base_code_filled","allele_code_filled"] if c in df.columns]
        mask = pd.Series(False, index=df.index)
        for c in cols:
            mask |= df[c].fillna("").astype(str).str.lower().str.contains(ql, na=False)
        df = df[mask]

    # Make sure id exists (fallback to id_uuid)
    if "id" not in df.columns or df["id"].isna().all():
        if "id_uuid" in df.columns:
            df["id"] = df["id_uuid"]

    # Minimal column set expected by older page
    preferred = ["id","id_uuid","fish_code","name","nickname","batch_display",
                 "transgene_base_code_filled","allele_code_filled","created_by","date_birth","created_at"]
    cols = [c for c in preferred if c in df.columns]
    if cols:
        df = df[cols]

    if isinstance(limit, int) and limit > 0:
        df = df.head(limit)

    return df.to_dict(orient="records")
