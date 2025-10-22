from __future__ import annotations

import shlex
import pandas as pd
from typing import Any, Dict, List, Optional, Mapping
from sqlalchemy import text
from sqlalchemy.engine import Engine, Connection

# ========= helpers =========

FISH_VIEW = "public.v_fish"          # canonical fish view (exists in your rebuilt DB)
TANKS_VIEW = "public.v_tanks"        # canonical tank view (exists in your rebuilt DB)

def _object_exists(engine: Engine, schema: str, name: str) -> bool:
    sql = text("""
      with t as (
        select table_schema as s, table_name as n from information_schema.tables
        union all
        select table_schema as s, table_name as n from information_schema.views
      )
      select exists(select 1 from t where s=:s and n=:n) as ok
    """)
    with engine.begin() as cx:
        return bool(pd.read_sql(sql, cx, params={"s": schema, "n": name})["ok"].iloc[0])

# ========= fish search (v_fish) =========

# Available columns in v_fish; keep haystack lean & stable
SEARCH_COLUMNS = [
    "fish_code",
    "name",
    "nickname",
    "genotype",
    "genetic_background",
]

def _build_haystack() -> str:
    casted = [f"COALESCE(({c})::text,'')" for c in SEARCH_COLUMNS]
    return "concat_ws(' ', " + ", ".join(casted) + ")"

def load_fish_overview(engine: Engine, q: str = "", stages: List[str] | None = None,
                       limit: int = 500, view: str | None = None):
    """
    Multi-term AND search over v_fish with simple field/contains filters.
    """
    view = view or FISH_VIEW
    haystack = _build_haystack()

    tokens = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]

    # allowed field aliases → SQL column
    field_map: Dict[str, str] = {
        "fish_code": "fish_code",
        "name": "name",
        "nickname": "nickname",
        "genotype": "genotype",
        "background": "genetic_background",
        "genetic_background": "genetic_background",
        # If you add stage to v_fish later, you can map: "stage": "stage",
    }

    params: Dict[str, object] = {"limit": int(limit)}
    where: List[str] = []

    for i, tok in enumerate(tokens):
        neg = tok.startswith("-")
        core = tok[1:] if neg else tok

        # field-specific exact (k=val) vs contains (k:val)
        k_eq = v_eq = None
        k_ct = v_ct = None
        if "=" in core:
            k_eq, v_eq = core.split("=", 1)
            k_eq = (k_eq or "").strip().lower()
            v_eq = (v_eq or "").strip().strip('"')
        elif ":" in core:
            k_ct, v_ct = core.split(":", 1)
            k_ct = (k_ct or "").strip().lower()
            v_ct = (v_ct or "").strip().strip('"')

        # exact
        if k_eq and k_eq in field_map:
            col = field_map[k_eq]
            key = f"t{i}"
            params[key] = v_eq
            clause = f"lower({col}) = lower(:{key})"
            where.append(("NOT " if neg else "") + f"({clause})")
            continue

        # contains
        if k_ct and k_ct in field_map:
            col = field_map[k_ct]
            key = f"t{i}"
            params[key] = f"%{v_ct}%"
            clause = f"{col} ILIKE :{key}"
            where.append(("NOT " if neg else "") + f"({clause})")
            continue

        # generic haystack contains / negated
        key = f"t{i}"
        params[key] = f"%{core}%"
        clause = f"{haystack} ILIKE :{key}"
        where.append(("NOT " if neg else "") + f"({clause})")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT *
        FROM {view}
        {where_sql}
        ORDER BY created_at DESC NULLS LAST
        LIMIT :limit
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return rows

def fish_overview_minimal(conn_or_engine: Any, q: Optional[str] = None,
                          limit: int = 1000, require_links: bool = True) -> List[Dict[str, Any]]:
    """
    Back-compat: delegate to load_fish_overview, then trim to a tolerant minimal set.
    """
    try:
        if isinstance(conn_or_engine, Engine):
            eng = conn_or_engine
        elif isinstance(conn_or_engine, Connection):
            eng = conn_or_engine.engine
        else:
            eng = conn_or_engine
    except Exception:
        eng = conn_or_engine

    data = load_fish_overview(eng, q=q or "", limit=limit)
    df = pd.DataFrame(data)

    for c in ["id","fish_code","name","nickname","batch_label","seed_batch_id","created_by","date_birth","created_at"]:
        if c not in df.columns:
            df[c] = None
    df["batch_display"] = df["batch_label"].fillna(df["seed_batch_id"])

    keep = [c for c in ["id","fish_code","name","nickname","batch_display","created_by","date_birth","created_at"] if c in df.columns]
    if keep:
        df = df[keep]

    if isinstance(limit, int) and limit > 0:
        df = df.head(limit)

    return df.to_dict(orient="records")

def load_label_rows(engine: Engine, q: str | None = None, limit: int = 500):
    """
    Convenience label rows with the same multi-term semantics, backed by v_fish.
    """
    view = FISH_VIEW
    haystack = _build_haystack()

    tokens = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]
    params: Dict[str, object] = {"lim": int(limit)}
    clauses: List[str] = []

    for i, tok in enumerate(tokens):
        neg = tok.startswith("-")
        term = tok[1:] if neg else tok
        key = f"t{i}"
        params[key] = f"%{term}%"
        clause = f"{haystack} ILIKE :{key}"
        clauses.append(("NOT " if neg else "") + f"({clause})")

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
      SELECT *
      FROM {view}
      {where_sql}
      ORDER BY fish_code
      LIMIT :lim
    """
    with engine.begin() as cx:
        return pd.read_sql_query(sql, cx, params=params)

# ========= containers overview (v_tanks) =========

def load_containers_overview(engine: Engine, q: Optional[str] = None, limit: int = 200) -> List[Mapping]:
    """
    Tank-centric overview backed by public.v_tanks.
    Returns a container-like shape for callers.
    """
    sql = """
        select
          t.tank_id                       as id,
          'inventory_tank'                as container_type,   -- v_tanks is tank-only
          t.label                         as label,
          t.tank_code                     as tank_code,
          t.status                        as status,
          t.tank_updated_at               as status_changed_at,
          t.tank_created_at               as created_at
        from public.v_tanks t
        where (:q is null)
           or (coalesce(t.label,'') ilike :qpat
            or coalesce(t.tank_code,'') ilike :qpat)
        order by status_changed_at desc nulls last, created_at desc
        limit :lim
    """
    qpat = f"%{q}%" if (q is not None and str(q).strip() != '') else None
    with engine.connect() as conn:
        return [
            dict(r) for r in conn.execute(
                text(sql), {"q": q, "qpat": qpat, "lim": int(limit)}
            ).mappings().all()
        ]

# ========= clutch instances overview (inline; no view dependency) =========

def load_clutch_instances_overview(engine: Engine, limit: int = 200) -> List[Mapping]:
    """
    Pair-centric clutch instances overview built inline (no v_clutch_instances_overview).
    """
    sql = """
      with b as (
        select
          x.id                                              as cross_instance_id,
          coalesce(x.cross_run_code, x.id::text)           as cross_run_code,
          x.cross_date                                      as birthday,
          ci.id                                             as clutch_instance_id,
          coalesce(ci.clutch_instance_code, ci.id::text)    as clutch_code,
          ci.date_birth                                     as clutch_birthday,
          coalesce(ci.annotated_by, x.created_by)           as clutch_created_by,
          vt_m.tank_code                                    as mother_tank_code,
          vt_f.tank_code                                    as father_tank_code
        from public.clutch_instances ci
        join public.cross_instances x    on x.id = ci.cross_instance_id
        left join public.tank_pairs tp   on tp.id = x.tank_pair_id
        left join public.v_tanks  vt_m   on vt_m.tank_id = tp.mother_tank_id
        left join public.v_tanks  vt_f   on vt_f.tank_id = tp.father_tank_id
      )
      select
        cross_instance_id, cross_run_code, birthday, clutch_code,
        clutch_instance_id, clutch_birthday, clutch_created_by
      from b
      order by birthday desc nulls last
      limit :lim
    """
    with engine.connect() as conn:
        return [
            dict(r) for r in conn.execute(
                text(sql), {"lim": int(limit)}
            ).mappings().all()
        ]

# ========= optional: human fish overview (fallback to v_fish if needed) =========

def load_fish_overview_human(engine: Engine, q: Optional[str] = None,
                             stages: Optional[List[str]] = None, limit: int = 500) -> List[Mapping]:
    """
    If public.v_fish_overview_human exists, use it; else fallback to public.v_fish with a reduced column set.
    """
    if _object_exists(engine, "public", "v_fish_overview_human"):
        cols = (
            "fish_id, fish_code, fish_name, fish_nickname, genetic_background, "
            "allele_number, allele_code, transgene, genotype_rollup, "
            "tank_code, tank_label, tank_status, "
            "stage, date_birth, created_at, created_by"
        )
        search_cols = [
            "fish_code", "fish_name", "fish_nickname",
            "genetic_background", "transgene", "genotype_rollup",
            "tank_code", "tank_label",
        ]
        view = "public.v_fish_overview_human"
    else:
        # fallback to v_fish
        cols = "id as fish_id, fish_code, name as fish_name, nickname as fish_nickname, genetic_background, genotype as genotype_rollup, created_at, null::text as created_by, null::text as tank_code, null::text as tank_label, null::text as tank_status, null::text as transgene, null::int as allele_number, null::text as allele_code, null::text as stage, date_birth"
        search_cols = ["fish_code", "name", "nickname", "genetic_background", "genotype"]
        view = FISH_VIEW

    # normalize q: empty/whitespace -> None
    q = (q.strip() if isinstance(q, str) else q) or None

    clauses: List[str] = []
    params: dict = {"lim": int(limit)}

    # optional stage filter (only if the column exists)
    if "stage" in cols and stages:
        stg = list({(s or "").strip().upper() for s in stages if (s or "").strip()})
        if stg:
            clauses.append("upper(coalesce(stage,'')) = ANY(:stages)")
            params["stages"] = stg

    # multi-term search
    if q:
        terms = [t for t in q.split() if t]
        for i, t in enumerate(terms, 1):
            key = f"t{i}"
            ors = " OR ".join([f"coalesce({c},'') ILIKE :{key}" for c in search_cols])
            clauses.append(f"({ors})")
            params[key] = f"%{t}%"

    sql = f"""
        select {cols}
        from {view}
        {"where " + " AND ".join(clauses) if clauses else ""}
        order by created_at desc nulls last
        limit :lim
    """
    with engine.connect() as cx:
        rows = cx.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]