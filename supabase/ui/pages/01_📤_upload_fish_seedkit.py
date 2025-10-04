# supabase/ui/pages/01_📤_upload_fish_seedkit.py
from __future__ import annotations

# --- sys.path before local imports ---
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]  # …/carp_v2
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Shared engine + helpers
from supabase.ui.lib_shared import current_engine, connection_info

# 🔒 auth
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

from datetime import datetime, UTC
from typing import List, Dict, Any, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text

PAGE_TITLE = "CARP — Upload Fish (CSV only)"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
st.title("📤 Upload Fish (CSV only)")

# --------------------------------------------------------------------------------------
# Engine / DB info
# --------------------------------------------------------------------------------------
eng = current_engine()
dbg = connection_info(eng)
st.caption(f"DB debug → db={dbg['db']} user={dbg['user']}")
# --- TEMP DIAG: what does THIS engine think about base_code?
with eng.begin() as _cx:
    diag = _cx.execute(text("""
        select current_database() as db,
               inet_server_addr()::text as host,
               inet_server_port()::int  as port
    """)).mappings().first()
    nn = _cx.execute(text("""
        select column_name, is_nullable
        from information_schema.columns
        where table_schema='public'
          and table_name='transgene_allele_registry'
          and column_name = 'base_code'
    """)).mappings().all()

st.caption(f"ENGINE → db={diag['db']} host={diag['host']} port={diag['port']}")
st.code(f"base_code is_nullable (app engine): {nn}", language="text")

# --------------------------------------------------------------------------------------
# Self-heal helpers (tables/views)
# --------------------------------------------------------------------------------------
def _has_column(conn, table: str, col: str) -> bool:
    return bool(conn.execute(
        text("""
          select exists(
            select 1 from information_schema.columns
            where table_schema='public' and table_name=:t and column_name=:c
          )
        """),
        {"t": table, "c": col},
    ).scalar())


def ensure_core_objects(conn) -> None:
    """
    Self-heal: pgcrypto, fish table, link table, base view v_fish_overview (EXISTS guard).
    """
    conn.execute(text("create extension if not exists pgcrypto"))
    conn.execute(text("""
    do $$
    begin
      if to_regclass('public.fish') is null then
        create table public.fish(
          id uuid primary key default gen_random_uuid(),
          fish_code text unique,
          name text,
          created_at timestamptz not null default now(),
          created_by text,
          date_birth date
        );
      end if;

      if not exists (
        select 1 from information_schema.columns
        where table_schema='public' and table_name='fish'
          and column_name in ('date_birth','date_of_birth')
      ) then
        alter table public.fish add column date_birth date;
      end if;

      if to_regclass('public.fish_transgene_alleles') is null then
        create table public.fish_transgene_alleles(
          fish_id uuid not null references public.fish(id) on delete cascade,
          transgene_base_code text not null,
          allele_number int not null,
          zygosity text,
          allele_nickname text,
          primary key (fish_id, transgene_base_code, allele_number)
        );
      else
        if not exists (
          select 1 from information_schema.columns
          where table_schema='public' and table_name='fish_transgene_alleles'
            and column_name='allele_nickname'
        ) then
          alter table public.fish_transgene_alleles add column allele_nickname text;
        end if;
      end if;

      if to_regclass('public.v_fish_overview') is null then
        create view public.v_fish_overview as
        select
          f.id,
          f.fish_code,
          f.name,
          (
            select array_to_string(array_agg(x.base), ', ')
            from (
              select distinct t.transgene_base_code as base
              from public.fish_transgene_alleles t
              where t.fish_id = f.id
              order by base
            ) x
          ) as transgene_base_code_filled,
          (
            select array_to_string(array_agg(x.an), ', ')
            from (
              select distinct (t.allele_number::text) as an
              from public.fish_transgene_alleles t
              where t.fish_id = f.id
              order by an
            ) x
          ) as allele_code_filled,
          null::text as allele_name_filled,
          f.created_at,
          f.created_by
        from public.fish f
        where exists (select 1 from public.fish_transgene_alleles t where t.fish_id = f.id)
        order by f.created_at desc;
      end if;
    end$$;
    """))

def ensure_registry_and_counters(conn) -> None:
    """
    Ensure nickname registry and per-base counters exist, with uniqueness.
    """
    conn.execute(text("""
    do $$
    begin
      if to_regclass('public.transgene_allele_registry') is null then
        create table public.transgene_allele_registry(
          id uuid primary key default gen_random_uuid(),
          transgene_base_code text not null,
          allele_number integer not null,
          allele_nickname text not null,
          created_at timestamptz not null default now(),
          created_by text null
        );
      end if;

      if not exists (select 1 from pg_class where relname='uq_tar_base_number' and relkind='i') then
        create unique index uq_tar_base_number
          on public.transgene_allele_registry (transgene_base_code, allele_number);
      end if;
      if not exists (select 1 from pg_class where relname='uq_tar_base_nickname' and relkind='i') then
        create unique index uq_tar_base_nickname
          on public.transgene_allele_registry (transgene_base_code, allele_nickname);
      end if;

      if to_regclass('public.transgene_allele_counters') is null then
        create table public.transgene_allele_counters (
          transgene_base_code text primary key,
          next_number integer not null default 1
        );
      end if;
    end$$;
    """))

# --------------------------------------------------------------------------------------
# Allocation (inline, no function dependency)
# --------------------------------------------------------------------------------------
def inline_allocate_number(conn, base: str, nick: str, by: Optional[str]) -> Optional[int]:
    """
    Allocate a stable allele_number for (base, nickname) with per-base counters + registry.
    Atomic and idempotent under unique indexes.
    """
    base = (base or "").strip()
    nick = (nick or "").strip()
    if not base or not nick:
        return None

    # existing mapping?
    n = conn.execute(
        text("""
          select allele_number
          from public.transgene_allele_registry
          where transgene_base_code = :base and allele_nickname = :nick
          limit 1
        """),
        {"base": base, "nick": nick},
    ).scalar()
    if n is not None:
        return int(n)

    # ensure a counter row for this base; then atomically consume next_number
    conn.execute(
        text("""
          insert into public.transgene_allele_counters (transgene_base_code)
          values (:base)
          on conflict (transgene_base_code) do nothing
        """),
        {"base": base},
    )
    n = conn.execute(
        text("""
          update public.transgene_allele_counters
          set next_number = next_number + 1
          where transgene_base_code = :base
          returning next_number - 1
        """),
        {"base": base},
    ).scalar()
    if n == 0:  # first ever allocation => make it 1
        n = 1

    # write registry entry; tolerate racing insert
    has_created_by = _has_column(conn, "transgene_allele_registry", "created_by")

    if has_created_by:
        conn.execute(
            text("""
            insert into public.transgene_allele_registry
                (transgene_base_code, allele_number, allele_nickname, created_by)
            values (:base, :allele, :nick, :by)
            on conflict (transgene_base_code, allele_nickname) do nothing
            """),
            {"base": base, "allele": int(n), "nick": nick, "by": by},
        )
    else:
        conn.execute(
            text("""
            insert into public.transgene_allele_registry
                (transgene_base_code, allele_number, allele_nickname)
            values (:base, :allele, :nick)
            on conflict (transgene_base_code, allele_nickname) do nothing
            """),
            {"base": base, "allele": int(n), "nick": nick},
        )

    # return the value from the registry (source of truth)
    n2 = conn.execute(
        text("""
          select allele_number
          from public.transgene_allele_registry
          where transgene_base_code = :base and allele_nickname = :nick
          limit 1
        """),
        {"base": base, "nick": nick},
    ).scalar()
    return int(n2) if n2 is not None else None

# --------------------------------------------------------------------------------------
# CSV normalizer
# --------------------------------------------------------------------------------------
def normalize_input(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize CSV columns to our contract.
    Required: fish_code, transgene_base_code, allele_nickname or allele_number (legacy).
    Optional: name, created_by, date_birth/date_of_birth, zygosity.
    """
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    def pick(names: List[str]) -> pd.Series:
        for n in names:
            if n in df.columns:
                return df[n]
        return pd.Series([None] * len(df))

    out = pd.DataFrame()
    out["fish_code"]           = pick(["fish_code","code","fish id","id"]).astype("string")
    out["name"]                = pick(["name","fish_name"]).astype("string")
    out["created_by"]          = pick(["created_by","user","owner"]).astype("string")

    dob_any = pick(["date_birth","date_of_birth","birth_date"])
    try:
        out["date_birth"] = pd.to_datetime(dob_any, errors="coerce").dt.date
    except Exception:
        out["date_birth"] = None

    out["transgene_base_code"] = pick(["transgene_base_code"]).astype("string")
    out["allele_nickname"]     = pick(["allele_nickname"]).astype("string")
    out["zygosity"]            = pick(["zygosity"]).astype("string")

    # No derivation of allele_number from nickname.
    if "allele_number" in df.columns:
        out["allele_number"] = pd.to_numeric(df["allele_number"], errors="coerce").astype("Int64")
    else:
        out["allele_number"] = pd.Series([pd.NA] * len(out), dtype="Int64")

    # Autogenerate fish_code if missing
    mask = out["fish_code"].isna() | (out["fish_code"].astype(str).str.strip() == "")
    if mask.any():
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        out.loc[mask, "fish_code"] = [f"FSH-{stamp}-{i:03d}" for i in range(1, int(mask.sum())+1)]

    return out

# --------------------------------------------------------------------------------------
# UI State
# --------------------------------------------------------------------------------------
PREVIEW_KEY = "upload_preview_df"
RESULT_KEY  = "upload_insert_result"

def _reset_preview():
    st.session_state.pop(PREVIEW_KEY, None)
    st.session_state.pop(RESULT_KEY, None)

uploaded = st.file_uploader("Upload .csv", type=["csv"], on_change=_reset_preview)

col1, col2 = st.columns([1,1])
with col1:
    load_clicked = st.button("Load preview", disabled=uploaded is None)
with col2:
    insert_clicked = st.button("Insert into database", disabled=(PREVIEW_KEY not in st.session_state))

# --------------------------------------------------------------------------------------
# Load Preview
# --------------------------------------------------------------------------------------
if load_clicked and uploaded is not None:
    try:
        raw = uploaded.read().decode("utf-8")
        df_in = pd.read_csv(io.StringIO(raw))
        df_norm = normalize_input(df_in)
        st.session_state[PREVIEW_KEY] = df_norm
    except Exception as e:
        st.exception(e)

if PREVIEW_KEY in st.session_state:
    df_norm = st.session_state[PREVIEW_KEY]

    # Heads-up if nothing will link (no base+nickname pairs)
    has_base = ("transgene_base_code" in df_norm.columns) and df_norm["transgene_base_code"].notna().any()
    has_nick = ("allele_nickname" in df_norm.columns)     and df_norm["allele_nickname"].notna().any()
    if not (has_base and has_nick):
        st.warning("No transgene_base_code + allele_nickname pairs detected; nothing will be linked.")

    st.subheader("Preview (normalized)")
    preview_cols = [
        "fish_code","name","created_by","date_birth",
        "transgene_base_code","allele_nickname","zygosity",
    ]
    present = [c for c in preview_cols if c in df_norm.columns]
    st.dataframe(df_norm[present], width="stretch")

# --------------------------------------------------------------------------------------
# Insert
# --------------------------------------------------------------------------------------
if insert_clicked and (PREVIEW_KEY in st.session_state):
    created_ct = 0
    updated_ct = 0
    linked_ct  = 0
    skipped_ct = 0

    try:
        with eng.begin() as conn:
            ensure_core_objects(conn)
            ensure_registry_and_counters(conn)

            df_norm = st.session_state[PREVIEW_KEY]

            # Upsert fish rows, collect ids
            fish_cols = ["fish_code","name","created_by","date_birth"]
            to_insert = df_norm[fish_cols].copy()

            created_rows: List[Dict[str, Any]] = []
            for _, r in to_insert.iterrows():
                row = conn.execute(
                    text("""
                        insert into public.fish (id, fish_code, name, created_by, date_birth)
                        values (gen_random_uuid(), :code, :name, :by, :dob)
                        on conflict (fish_code) do update set
                          name=excluded.name,
                          created_by=excluded.created_by,
                          date_birth=excluded.date_birth
                        returning id, fish_code
                    """),
                    {"code": r.get("fish_code"), "name": r.get("name"), "by": r.get("created_by"), "dob": r.get("date_birth")},
                ).mappings().first()
                created_rows.append(dict(row))
            created_ct = len(created_rows)

            # Link genotype: prefer nickname path, else numeric CSV fallback
            base_nonempty = df_norm.get("transgene_base_code").astype("string").str.strip().ne("")
            nick_nonempty = df_norm.get("allele_nickname").astype("string").str.strip().ne("")
            num_present   = df_norm.get("allele_number").notna() if "allele_number" in df_norm.columns else pd.Series(False, index=df_norm.index)
            gmask = base_nonempty & (nick_nonempty | num_present)
            st.caption(
                "debug: base_nonempty=%d nick_nonempty=%d gmask=%d"
                % (int(base_nonempty.sum()), int(nick_nonempty.sum()), int(gmask.sum()))
            )

            if gmask.any():
                code_to_id = {c["fish_code"]: c["id"] for c in created_rows}
                for _, r in df_norm.loc[gmask].iterrows():
                    fid = code_to_id.get(r["fish_code"]) or conn.execute(
                        text("select id from public.fish where fish_code=:c limit 1"),
                        {"c": r["fish_code"]},
                    ).scalar()
                    if not fid:
                        skipped_ct += 1
                        continue

                    base = (r.get("transgene_base_code") or "").strip()
                    nick = (r.get("allele_nickname") or "").strip() or None
                    by   = (r.get("created_by") or None)
                    zyg  = (r.get("zygosity") or None)

                    # allocate number inline if nickname present; else take numeric from CSV (legacy)
                    # 1) try registry first (deterministic & cheap)
                    n: Optional[int] = conn.execute(
                        text("""
                        select allele_number
                        from public.transgene_allele_registry
                        where transgene_base_code = :base and allele_nickname = :nick
                        limit 1
                        """),
                        {"base": base, "nick": nick},
                    ).scalar() if nick else None

                    if n is not None:
                        st.caption(f"alloc: registry hit base='{base}' nick='{nick}' -> n={int(n)}")

                    # 2) else try inline allocate (writes registry & bumps per-base counter)
                    if n is None and nick:
                        st.caption(f"alloc: inline start base='{base}' nick='{nick}'")
                        sp = conn.begin_nested()  # SAVEPOINT
                        try:
                            n = inline_allocate_number(conn, base, nick, by)
                            sp.commit()
                            st.caption(f"alloc: inline done base='{base}' nick='{nick}' -> n={n}")
                        except Exception as e:
                            sp.rollback()
                            st.caption(f"alloc: inline ERROR base='{base}' nick='{nick}' err={e}")
                            n = None

                    # 3) else fallback to numeric CSV (legacy)
                    if n is None:
                        try:
                            n = int(r.get("allele_number"))
                            st.caption(f"alloc: csv numeric base='{base}' -> n={n}")
                        except Exception:
                            n = None

                    # 4) still nothing? skip with explicit context
                    if n is None:
                        # show what registry actually has for this base to help diagnose
                        try:
                            rows = conn.execute(
                                text("""
                                select allele_nickname, allele_number
                                from public.transgene_allele_registry
                                where transgene_base_code = :base
                                order by allele_nickname
                                limit 10
                                """),
                                {"base": base},
                            ).mappings().all()
                            sample = ", ".join(f"{row['allele_nickname']}→{row['allele_number']}" for row in rows)
                            st.caption(f"alloc: registry sample for base='{base}' [{sample}]")
                        except Exception:
                            pass
                        st.caption(f"debug skip: base='{base}' nick='{nick}' (no number)")
                        skipped_ct += 1
                        continue

                    # FK: ensure (base, number) exists in transgene_alleles
                    conn.execute(
                        text("""
                          insert into public.transgene_alleles (transgene_base_code, allele_number)
                          values (:base, :allele)
                          on conflict (transgene_base_code, allele_number) do nothing
                        """),
                        {"base": base, "allele": int(n)},
                    )

                    # insert link (include nickname when available)
                    has_nn = conn.execute(text("""
                        select exists(
                          select 1
                          from information_schema.columns
                          where table_schema='public'
                            and table_name='fish_transgene_alleles'
                            and column_name='allele_nickname'
                        )
                    """)).scalar()

                    params_link = {"fid": str(fid), "base": base, "allele": int(n), "zyg": zyg}
                    if has_nn:
                        params_link["nn"] = nick
                        conn.execute(
                            text("""
                              insert into public.fish_transgene_alleles
                                (fish_id, transgene_base_code, allele_number, zygosity, allele_nickname)
                              values (:fid, :base, :allele, :zyg, :nn)
                              on conflict do nothing
                            """),
                            params_link,
                        )
                    else:
                        conn.execute(
                            text("""
                              insert into public.fish_transgene_alleles
                                (fish_id, transgene_base_code, allele_number, zygosity)
                              values (:fid, :base, :allele, :zyg)
                              on conflict do nothing
                            """),
                            params_link,
                        )
                    linked_ct += 1

        # write result once
        st.session_state["upload_insert_result"] = {
            "created": int(created_ct),
            "updated": int(updated_ct),
            "with_alleles": int(linked_ct),
            "skipped_no_allele": int(skipped_ct),
            "skipped": int(skipped_ct),
        }

    except Exception as e:
        st.exception(e)

# --------------------------------------------------------------------------------------
# Result + Overview slice
# --------------------------------------------------------------------------------------
res = st.session_state.get("upload_insert_result")
if res:
    created = int(res.get("created", 0))
    updated = int(res.get("updated", 0))
    with_alleles = int(res.get("with_alleles", 0))
    skipped = int(res.get("skipped_no_allele", res.get("skipped", 0)))

    st.success(
        f"Inserted {created} new, updated {updated}; "
        f"linked genotype for {with_alleles} rows; skipped {skipped} without allele."
    )

    st.markdown("#### Recent rows (from `v_fish_overview`)")
    try:
        recent = pd.read_sql(
            """
            select id, fish_code, name,
                   transgene_base_code_filled, allele_code_filled, allele_name_filled,
                   created_at, created_by
            from public.v_fish_overview
            order by created_at desc
            limit 50
            """,
            eng,
        )
        if "id" in recent.columns:
            recent["id"] = recent["id"].astype(str)
        st.dataframe(recent, width="stretch")
    except Exception as e:
        st.warning(f"Could not read v_fish_overview yet: {e}")