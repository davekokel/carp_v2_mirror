import shlex
import pandas as pd
from typing import Any, Dict, List, Optional
from sqlalchemy import text

# Tailored to your label view columns
VIEW = "public.vw_fish_overview_with_label"

# These exist (from your \d+): use *_print where appropriate
SEARCH_COLUMNS = [
    "fish_code",
    "name",
    "nickname",
    "genotype_print",
    "genetic_background_print",
    "COALESCE(line_building_stage,line_building_stage_print)"
]

# For stage filtering / display we coalesce these
STAGE_COALESCE = "COALESCE(line_building_stage,line_building_stage_print)"

def _build_haystack() -> str:
    casted = [f"COALESCE(({c})::text,'')" for c in SEARCH_COLUMNS]
    return "concat_ws(' ', " + ", ".join(casted) + ")"

def load_fish_overview(engine, q: str = "", stages: List[str] | None = None, limit: int = 500, view: str | None = None):
    """
    Multi-term AND search with:
      - field-specific filters: name= / name: / genotype: / background: / fish_code= / stage=
      - quoted phrases
      - -negation for both haystack and field-specific
      - stage pill merges with auto-detected stage tokens
    """
    view = view or VIEW
    haystack = _build_haystack()

    # tokenize; ignore literal AND
    tokens = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]

    # allowed field aliases → SQL column/expression
    field_map: Dict[str, str] = {
        "fish_code": "fish_code",
        "name": "name",
        "nickname": "nickname",
        "genotype": "genotype_print",                         # alias
        "background": "genetic_background_print",             # alias
        "genetic_background": "genetic_background_print",
        "stage": STAGE_COALESCE,                              # expression
    }

    # stage vocabulary for auto-detection from free text
    STAGE_VALUES = {"FOUNDER", "F0", "F1", "F2", "F3", "F4"}

    params: Dict[str, object] = {"limit": int(limit)}
    where: List[str] = []
    auto_stage_filters: List[str] = []

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

        # exact: lower(col) = lower(:tN)
        if k_eq and k_eq in field_map:
            col = field_map[k_eq]
            key = f"t{i}"
            params[key] = v_eq
            clause = f"lower({col}) = lower(:{key})"
            where.append(("NOT " if neg else "") + f"({clause})")
            continue

        # contains: col ILIKE :tN
        if k_ct and k_ct in field_map:
            col = field_map[k_ct]
            key = f"t{i}"
            params[key] = f"%{v_ct}%"
            clause = f"{col} ILIKE :{key}"
            where.append(("NOT " if neg else "") + f"({clause})")
            continue

        # free text stage token → collect for equality filter later
        if core.upper() in STAGE_VALUES and not neg:
            auto_stage_filters.append(core.upper())
            continue

        # otherwise haystack contains / negated contains
        key = f"t{i}"
        if neg:
            params[key] = f"%{core}%"
            where.append(f"NOT ({haystack} ILIKE :{key})")
        else:
            params[key] = f"%{core}%"
            where.append(f"({haystack} ILIKE :{key})")

    # merge explicit stage pill with auto-detected tokens
    stage_filters = [s.upper() for s in (stages or [])]
    for s in auto_stage_filters:
        if s not in stage_filters:
            stage_filters.append(s)
    if stage_filters:
        where.append(f"UPPER({STAGE_COALESCE}) = ANY(:stages)")
        params["stages"] = stage_filters

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT *
        FROM {view}
        {where_sql}
        ORDER BY created_at DESC
        LIMIT :limit
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return rows

def fish_overview_minimal(conn_or_engine: Any, q: Optional[str] = None, limit: int = 1000, require_links: bool = True) -> List[Dict[str, Any]]:
    """
    Back-compat: delegate to load_fish_overview, then trim to a tolerant minimal set.
    """
    try:
        from sqlalchemy.engine import Engine, Connection
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

def load_label_rows(engine, q: str | None = None, limit: int = 500):
    """
    Convenience: fetch printable label rows with the same multi-term semantics.
    """
    view = VIEW  # default to the label-friendly view
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
# ---- overview view helpers ----
from typing import Optional, Mapping, List
from sqlalchemy import text
from sqlalchemy.engine import Engine

def load_containers_overview(engine: Engine, q: Optional[str] = None, limit: int = 200) -> List[Mapping]:
    sql = """
        select id, container_type, label, tank_code, status, status_changed_at, created_at
        from public.v_containers_overview
        where (:q is null)
           or (coalesce(label,'') ilike :qpat
            or coalesce(tank_code,'') ilike :qpat
            or coalesce(container_type,'') ilike :qpat)
        order by status_changed_at desc nulls last, created_at desc
        limit :lim
    """
    qpat = f"%{q}%" if (q is not None and str(q).strip() != '') else None
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), {"q": q, "qpat": qpat, "lim": limit}).mappings().all()]

def load_clutch_instances_overview(engine: Engine, limit: int = 200) -> List[Mapping]:
    sql = """
        select cross_instance_id, cross_run_code, birthday, clutch_code,
               clutch_instance_id, clutch_birthday, clutch_created_by
        from public.v_clutch_instances_overview
        order by birthday desc nulls last
        limit :lim
    """
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), {"lim": limit}).mappings().all()]
