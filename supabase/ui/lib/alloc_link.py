# supabase/ui/lib/alloc_link.py
from __future__ import annotations
from typing import Optional
from sqlalchemy import text


def column_exists(conn, table: str, col: str) -> bool:
    return bool(conn.execute(
        text("""
          select exists(
            select 1
            from information_schema.columns
            where table_schema='public' and table_name=:t and column_name=:c
          )
        """), {"t": table, "c": col}
    ).scalar())


# ---------- Number allocation (registry-first, legacy-safe) ----------
def resolve_or_allocate_number(conn, base: str, nickname: Optional[str], created_by: Optional[str]) -> Optional[int]:
    """
    Resolve (base, nickname) → allele_number using:
      1) modern key:    (transgene_base_code, allele_nickname)
      2) legacy key:    (base_code, legacy_label)   [if columns exist]
      3) allocate:      bump public.transgene_allele_counters.next_number and insert into registry
                        (including legacy columns if present), ON CONFLICT DO NOTHING
      4) read back:     modern first, then legacy
    Returns int or None.
    """
    base = (base or "").strip()
    nick = (nickname or "").strip() if nickname else None
    if not base or not nick:
        return None

    # 1) modern hit?
    n = conn.execute(
        text("""
          select allele_number
          from public.transgene_allele_registry
          where transgene_base_code = :b and allele_nickname = :n
          limit 1
        """), {"b": base, "n": nick}
    ).scalar()
    if n is not None:
        return int(n)

    # 2) legacy hit?
    has_base_code    = column_exists(conn, "transgene_allele_registry", "base_code")
    has_legacy_label = column_exists(conn, "transgene_allele_registry", "legacy_label")
    if has_base_code and has_legacy_label:
        n_legacy = conn.execute(
            text("""
              select allele_number
              from public.transgene_allele_registry
              where base_code = :b and legacy_label = :n
              limit 1
            """), {"b": base, "n": nick}
        ).scalar()
        if n_legacy is not None:
            return int(n_legacy)

    # 3) allocate: ensure counter row; atomically consume next_number
    conn.execute(
        text("""
          insert into public.transgene_allele_counters (transgene_base_code)
          values (:b) on conflict (transgene_base_code) do nothing
        """), {"b": base}
    )
    n = conn.execute(
        text("""
          update public.transgene_allele_counters
          set next_number = next_number + 1
          where transgene_base_code = :b
          returning next_number - 1
        """), {"b": base}
    ).scalar()
    if n == 0:
        n = 1

    # insert registry row (include legacy/created_by columns when present); ignore any unique conflict
    cols   = ["transgene_base_code", "allele_number", "allele_nickname"]
    params = {"transgene_base_code": base, "allele_number": int(n), "allele_nickname": nick}

    if column_exists(conn, "transgene_allele_registry", "created_by"):
        cols.append("created_by"); params["created_by"] = created_by
    if has_base_code:
        cols.append("base_code");  params["base_code"]  = base
    if has_legacy_label:
        cols.append("legacy_label"); params["legacy_label"] = nick

    placeholders = [f":{k}" for k in cols]
    conn.execute(
        text(f"""
          insert into public.transgene_allele_registry
            ({", ".join(cols)}) values ({", ".join(placeholders)})
          on conflict do nothing
        """),
        params,
    )

    # 4) read back (modern first, then legacy)
    n_mod = conn.execute(
        text("""
          select allele_number
          from public.transgene_allele_registry
          where transgene_base_code = :b and allele_nickname = :n
          limit 1
        """), {"b": base, "n": nick}
    ).scalar()
    if n_mod is not None:
        return int(n_mod)

    if has_base_code and has_legacy_label:
        n_legacy = conn.execute(
            text("""
              select allele_number
              from public.transgene_allele_registry
              where base_code = :b and legacy_label = :n
              limit 1
            """), {"b": base, "n": nick}
        ).scalar()
        if n_legacy is not None:
            return int(n_legacy)

    return None


# ---------- FK staging (ensures transgene_alleles pair exists) ----------
def ensure_transgene_pair(conn, base: str, allele_number: int) -> None:
    conn.execute(
        text("""
          insert into public.transgene_alleles (transgene_base_code, allele_number)
          values (:b, :a)
          on conflict (transgene_base_code, allele_number) do nothing
        """),
        {"b": base, "a": int(allele_number)},
    )


# ---------- Link fish to allele (with optional nickname) ----------
def link_fish_to(
    conn,
    fish_id: str,
    base: str,
    allele_number: int,
    zygosity: Optional[str],
    nickname: Optional[str] = None,
) -> None:
    has_nn = column_exists(conn, "fish_transgene_alleles", "allele_nickname")
    params = {"fid": fish_id, "b": base, "a": int(allele_number), "z": zygosity}
    if has_nn:
        params["nn"] = nickname
        conn.execute(
            text("""
              insert into public.fish_transgene_alleles
                (fish_id, transgene_base_code, allele_number, zygosity, allele_nickname)
              values (:fid, :b, :a, :z, :nn)
              on conflict do nothing
            """), params
        )
    else:
        conn.execute(
            text("""
              insert into public.fish_transgene_alleles
                (fish_id, transgene_base_code, allele_number, zygosity)
              values (:fid, :b, :a, :z)
              on conflict do nothing
            """), params
        )