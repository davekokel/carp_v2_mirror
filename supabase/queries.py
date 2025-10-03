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
    """
    Overview loader that works even when vw_fish_overview_with_label is absent.
    Falls back to public.fish with a minimal column set.
    """
    offset = (page - 1) * page_size
    with engine.connect() as cx:
        has_view = cx.execute(
            text("select to_regclass('public.vw_fish_overview_with_label')")
        ).scalar() is not None

        params: Dict[str, Any] = {}
        where = []

        if has_view:
            if q:
                params["q"] = f"%{q}%"
                where.append("("
                             " v.fish_code ILIKE :q"
                             " OR v.fish_name ILIKE :q"
                             " OR v.nickname ILIKE :q"
                             " OR v.transgene_base_code_filled ILIKE :q"
                             " OR v.allele_code_filled ILIKE :q"
                             " OR v.allele_name_filled ILIKE :q"
                             " OR v.transgene_pretty_filled ILIKE :q"
                             " OR v.transgene_pretty_nickname ILIKE :q"
                             ")")
            if stage and stage != "(any)":
                params["stage"] = stage
                where.append("v.line_building_stage = :stage")
            if strain:
                params["strain_like"] = f"%{strain}%"
                where.append("f.strain ILIKE :strain_like")

            where_sql = ("WHERE " + " AND ".join(where)) if where else ""

            sql_count = text(f"""
                SELECT COUNT(*)
                FROM public.vw_fish_overview_with_label v
                LEFT JOIN public.fish f
                  ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))
                {where_sql}
            """)
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

            total = cx.execute(sql_count, params).scalar() or 0
            df = pd.read_sql(sql_page, cx, params=params_page)
            return total, df

        # Fallback: minimal from public.fish
        fish_cols = [r[0] for r in cx.execute(text("""
            select column_name from information_schema.columns
            where table_schema='public' and table_name='fish'
        """)).fetchall()]
        select_cols = ["id_uuid", "fish_code"]
        if "name" in fish_cols: select_cols.append("name")
        if "created_at" in fish_cols: select_cols.append("created_at")
        if "created_by" in fish_cols: select_cols.append("created_by")

        if q:
            params["q"] = f"%{q}%"
            where.append("(fish_code ILIKE :q OR COALESCE(name,'') ILIKE :q)")
        if stage and "line_building_stage" in fish_cols:
            params["stage"] = stage
            where.append("line_building_stage = :stage")
        if strain and "strain" in fish_cols:
            params["strain_like"] = f"%{strain}%"
            where.append("strain ILIKE :strain_like")

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        sql_count = text(f"SELECT COUNT(*) FROM public.fish {where_sql}")
        sql_page  = text(f"""
            SELECT {", ".join(select_cols)}
            FROM public.fish
            {where_sql}
            ORDER BY COALESCE(created_at, now()) DESC
            LIMIT :limit OFFSET :offset
        """)
        params_page = dict(params)
        params_page["limit"] = page_size
        params_page["offset"] = offset

        total = cx.execute(sql_count, params).scalar() or 0
        df = pd.read_sql(sql_page, cx, params=params_page)
        if "name" in df.columns and "fish_name" not in df.columns:
            df = df.rename(columns={"name": "fish_name"})
        return total, df


def list_treatments_minimal(conn, q: Optional[str] = None, limit: int = 200):
    """
    Minimal treatments list for pickers.
    Works whether treatments uses a text code (treatment_type/treatment_code/display_name)
    and whether or not it has a UUID PK column.
    """
    qnorm = (None if (q is not None and q.strip() == "") else q)

    label_col = conn.execute(text("""
        select column_name
        from information_schema.columns
        where table_schema='public' and table_name='treatments'
          and column_name in ('treatment_type','treatment_code','display_name')
        order by case column_name
          when 'treatment_type' then 1
          when 'treatment_code' then 2
          when 'display_name'   then 3
          else 9 end
        limit 1
    """)).scalar()

    if not label_col:
        return []

    uuid_col = conn.execute(text("""
        select column_name
        from information_schema.columns
        where table_schema='public' and table_name='treatments'
          and data_type = 'uuid'
        limit 1
    """)).scalar()

    if uuid_col:
        sql = text(f"""
            select {uuid_col} as id_uuid, ({label_col}::text) as treatment_type
            from public.treatments
            where (:q is null or ({label_col}::text) ilike '%'||:q||'%')
            order by ({label_col}::text) asc
            limit :limit
        """)
    else:
        sql = text(f"""
            select NULL::uuid as id_uuid, ({label_col}::text) as treatment_type
            from public.treatments
            where (:q is null or ({label_col}::text) ilike '%'||:q||'%')
            order by ({label_col}::text) asc
            limit :limit
        """)

    return conn.execute(sql, {"q": qnorm, "limit": limit}).mappings().all()