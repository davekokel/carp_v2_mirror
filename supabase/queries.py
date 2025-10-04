# supabase/queries.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy import text


def fish_overview_minimal(
    conn,
    q: Optional[str] = None,
    limit: int = 1000,
    require_links: bool = True,
) -> List[Dict[str, Any]]:
    """
    Minimal list of fish for pickers, sourced from the canonical base view.

    Returns rows with:
      - id (uuid)
      - fish_code (text)
      - name (text)
      - created_at (timestamptz)
      - created_by (text)
      - transgene_base_code_filled (text)
      - allele_code_filled (text)

    Behavior:
      - Prefer public.v_fish_overview (canonical; only linked fish).
      - If the view doesn't exist (early local env), fallback to public.fish.
      - If require_links=True, enforce EXISTS (…) even on the view (belt & suspenders).
    """
    # clamp limit
    try:
        lim = int(limit)
    except Exception:
        lim = 1000
    lim = max(1, min(lim, 10000))

    # does the canonical view exist?
    has_view = conn.execute(
        text("select to_regclass('public.v_fish_overview') is not null")
    ).scalar()

    params: Dict[str, Any] = {"lim": lim}
    where = []

    if q and q.strip():
        params["p"] = f"%{q.strip()}%"
        where.append(
            "(fish_code ilike :p or coalesce(name,'') ilike :p or "
            " coalesce(transgene_base_code_filled,'') ilike :p or "
            " coalesce(allele_code_filled,'') ilike :p)"
        )

    if has_view:
        where_sql = (" where " + " and ".join(where)) if where else ""
        # defensive EXISTS even though the view is already tightened
        if require_links:
            extra = (
                " and exists (select 1 from public.fish_transgene_alleles t where t.fish_id = v.id)"
                if where_sql else
                " where exists (select 1 from public.fish_transgene_alleles t where t.fish_id = v.id)"
            )
        else:
            extra = ""
        sql = text(f"""
            select
              v.id,
              v.fish_code,
              v.name,
              v.created_at,
              v.created_by,
              v.transgene_base_code_filled,
              v.allele_code_filled
            from public.v_fish_overview v
            {where_sql}{extra}
            order by v.created_at desc
            limit :lim
        """)
        rows = conn.execute(sql, params).mappings().all()
        return list(rows)

    # Fallback: raw fish table (older/local envs). Optionally enforce links.
    where_fb: List[str] = []
    if q and q.strip():
        where_fb.append("(fish_code ilike :p or coalesce(name,'') ilike :p)")
    if require_links:
        where_fb.append(
            "exists (select 1 from public.fish_transgene_alleles t where t.fish_id = f.id)"
        )
    where_fb_sql = (" where " + " and ".join(where_fb)) if where_fb else ""
    sql_fb = text(f"""
        select
          f.id,
          f.fish_code,
          coalesce(f.name,'')::text as name,
          f.created_at,
          f.created_by,
          null::text as transgene_base_code_filled,
          null::text as allele_code_filled
        from public.fish f
        {where_fb_sql}
        order by f.created_at desc
        limit :lim
    """)
    rows = conn.execute(sql_fb, params).mappings().all()
    return list(rows)


# Backwards compatibility: old name delegates to the canonical loader
def list_fish_minimal(conn, q: Optional[str] = None, limit: int = 200):
    return fish_overview_minimal(conn, q=q, limit=limit, require_links=True)


def alleles_for_fish(conn, fish_id: str) -> List[Dict[str, Any]]:
    """
    Utility to fetch genotype links for a single fish.
    Returns: [{transgene_base_code, allele_number, zygosity}]
    """
    rows = conn.execute(
        text("""
            select transgene_base_code, allele_number, zygosity
            from public.fish_transgene_alleles
            where fish_id = :fid
            order by transgene_base_code, allele_number
        """),
        {"fid": str(fish_id)},
    ).mappings().all()
    return list(rows)