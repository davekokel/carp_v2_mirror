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

    where_clauses = []
    params: Dict[str, Any] = {}

    if q:
        params["q"] = f"%{q}%"
        where_clauses.append(
            "("
            " fish_name ILIKE :q OR nickname ILIKE :q OR strain ILIKE :q "
            " OR genotype_text ILIKE :q OR rna_injections_text ILIKE :q OR plasmid_injections_text ILIKE :q "
            ")"
        )

    if stage and stage != "(any)":
        params["stage"] = stage
        where_clauses.append("line_building_stage = :stage")

    if strain:
        params["strain_like"] = f"%{strain}%"
        where_clauses.append("strain ILIKE :strain_like")

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    sql_count = text(f"SELECT COUNT(*) FROM public.vw_fish_overview_with_label {where_sql}")
    sql_page = text(
        f"""
        SELECT
        *
        FROM public.vw_fish_overview_with_label
        {where_sql}
        ORDER BY fish_code NULLS LAST
        LIMIT :limit OFFSET :offset
        """
    )

    params_page = dict(params)
    params_page["limit"] = page_size
    params_page["offset"] = offset

    with engine.connect() as cx:
        total = cx.execute(sql_count, params).scalar() or 0
        df = pd.read_sql(sql_page, cx, params=params_page)

    return total, df