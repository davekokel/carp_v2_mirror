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