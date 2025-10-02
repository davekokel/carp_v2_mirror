from typing import Optional, Tuple, Any, Dict
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text

def load_fish_overview(
    engine: Engine,
    page: int = 1,
    page_size: int = 50,
    q: Optional[str] = None,
    stage: Optional[str] = None,
    strain: Optional[str] = None,
) -> Tuple[int, pd.DataFrame]:
    offset = (page - 1) * page_size

    where_clauses: list[str] = []
    params: Dict[str, Any] = {}

    # 1) Global search across columns that exist in the view
    if q:
        params["q"] = f"%{q}%"
        where_clauses.append(
            "("
            " v.fish_code ILIKE :q"
            " OR v.fish_name ILIKE :q"
            " OR v.nickname ILIKE :q"
            " OR v.transgene_base_code_filled ILIKE :q"
            " OR v.allele_code_filled ILIKE :q"
            " OR v.allele_name_filled ILIKE :q"
            " OR v.transgene_pretty_filled ILIKE :q"
            " OR v.transgene_pretty_nickname ILIKE :q"
            ")"
        )

    # 2) Stage filter (column is in the view)
    if stage and stage != "(any)":
        params["stage"] = stage
        where_clauses.append("v.line_building_stage = :stage")

    # 3) Strain filter (join base table; some view variants don’t expose strain)
    if strain:
        params["strain_like"] = f"%{strain}%"
        where_clauses.append("f.strain ILIKE :strain_like")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # COUNT
    sql_count = text(f"""
        SELECT COUNT(*)
        FROM public.vw_fish_overview_with_label v
        LEFT JOIN public.fish f
          ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))
        {where_sql}
    """)

    # PAGE
    sql_page = text(f"""
        SELECT v.*
        FROM public.vw_fish_overview_with_label v
        LEFT JOIN public.fish f
          ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))
        {where_sql}
        ORDER BY v.fish_code NULLS LAST
        LIMIT :limit OFFSET :offset
    """)

    params_page = dict(params)
    params_page["limit"] = page_size
    params_page["offset"] = offset

    with engine.connect() as cx:
        total = cx.execute(sql_count, params).scalar() or 0
        df = pd.read_sql(sql_page, cx, params=params_page)

    return total, df

from typing import Optional
from sqlalchemy import text

def list_fish_minimal(conn, q: Optional[str] = None, limit: int = 200):
    sql = text("""
        select id_uuid, fish_code
        from public.fish
        where (:q is null or fish_code ilike '%' || :q || '%')
        order by fish_code asc
        limit :limit
    """)
    return conn.execute(sql, {"q": q, "limit": limit}).mappings().all()

def list_treatments_minimal(conn, q: Optional[str] = None, limit: int = 200):
    sql = text("""
        select id_uuid, treatment_code
        from treatments
        where (:q is null or treatment_code ilike '%' || :q || '%')
        order by treatment_code asc
        limit :limit
    """)
    return conn.execute(sql, {"q": q, "limit": limit}).mappings().all()

def insert_fish_treatment_minimal(conn, *, fish_id: str, treatment_id: str, applied_at: str, batch_label: Optional[str], created_by: Optional[str]):
    sql = text("""
        insert into fish_treatments (fish_id, treatment_id, applied_at, batch_label, created_by)
        values (:fish_id::uuid, :treatment_id::uuid, :applied_at::timestamptz, :batch_label, :created_by)
        returning id_uuid
    """)
    return conn.execute(sql, {
        "fish_id": fish_id,
        "treatment_id": treatment_id,
        "applied_at": applied_at,
        "batch_label": batch_label,
        "created_by": created_by,
    }).scalar_one()
