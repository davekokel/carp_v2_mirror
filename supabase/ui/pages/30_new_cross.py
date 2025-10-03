# supabase/ui/pages/30_new_cross.py
from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

import os, hashlib, importlib, sys
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd

# repo shim
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import supabase.queries as _queries
importlib.reload(_queries)
from supabase import queries as Q

PAGE_TITLE = "CARP — New Cross / Offspring"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🧬")
st.title("🧬 Record New Cross → Create Offspring → Apply Treatments")

# ---- Connection (uses DB_URL from environment) ----
DB_URL = os.environ.get("DB_URL")
if not DB_URL:
    st.error("DB_URL not set")
    st.stop()

engine = create_engine(DB_URL)
DBKEY = hashlib.md5(DB_URL.encode()).hexdigest()[:8]
host = urlparse(DB_URL).hostname or ""
env = "LOCAL" if host in {"localhost","127.0.0.1","::1"} else "STAGING"
st.caption(f"Env: {env} • Host: {host} • Key: {DBKEY}")

# ---------- Helpers for "infinite scroll" parent pickers ----------
PAGE_SIZE = 50

def _ensure_state(key: str, init):
    if key not in st.session_state:
        st.session_state[key] = init
    return st.session_state[key]

def _load_overview_chunk(role: str, q: Optional[str], page: int) -> Tuple[int, pd.DataFrame]:
    try:
        total, df = Q.load_fish_overview(engine, page=page, page_size=PAGE_SIZE, q=q or None)
        # keep only columns we care about for picking
        keep_cols = [c for c in df.columns if c in {
            "fish_code","fish_name","nickname","line_building_stage",
            "transgene_pretty_filled","allele_code_filled","created_at"
        }]
        # if fish_code missing (unlikely), fallback minimal
        if "fish_code" not in df.columns:
            with engine.begin() as conn:
                rows = Q.list_fish_minimal(conn, q=q or None, limit=PAGE_SIZE)
            df = pd.DataFrame(rows)
            keep_cols = [c for c in df.columns if c in {"fish_code"}]
        return total, df[keep_cols].copy()
    except Exception:
        # fallback if the overview view doesn't exist locally
        with engine.begin() as conn:
            rows = Q.list_fish_minimal(conn, q=q or None, limit=PAGE_SIZE)
        df = pd.DataFrame(rows)
        if not df.empty and "created_at" not in df.columns:
            df["created_at"] = pd.NaT
        return len(df), df[["fish_code"]].copy() if not df.empty else (0, pd.DataFrame(columns=["fish_code"]))

def _parent_picker(role_label: str) -> Optional[str]:
    role = role_label.lower()  # "mom" or "dad"
    q_key     = f"{role}_q_{DBKEY}"
    page_key  = f"{role}_page_{DBKEY}"
    table_key = f"{role}_df_{DBKEY}"
    pick_key  = f"{role}_pick_{DBKEY}"

    q = _ensure_state(q_key, "")
    page = _ensure_state(page_key, 1)
    df = _ensure_state(table_key, pd.DataFrame())

    st.subheader(f"1) Select {role_label}")
    c1, c2, c3 = st.columns([3,1,1])
    with c1:
        new_q = st.text_input(f"Search {role_label} (code/name/transgene…)", value=q, key=f"{role}_search_{DBKEY}")
    with c2:
        if st.button("Search", key=f"{role}_search_btn_{DBKEY}"):
            # reset list for new search
            st.session_state[page_key] = 1
            total, chunk = _load_overview_chunk(role, new_q, 1)
            st.session_state[table_key] = chunk
            st.session_state[q_key] = new_q
            st.session_state[f"{role}_total_{DBKEY}"] = total
    with c3:
        if st.button("Load more", key=f"{role}_load_{DBKEY}"):
            # append next page
            cur_q = st.session_state[q_key]
            next_page = st.session_state[page_key] + 1
            _, chunk = _load_overview_chunk(role, cur_q, next_page)
            st.session_state[table_key] = pd.concat([st.session_state[table_key], chunk], ignore_index=True).drop_duplicates(subset=["fish_code"], keep="first")
            st.session_state[page_key] = next_page

    # initial fill if empty
    if st.session_state[table_key].empty:
        total, chunk = _load_overview_chunk(role, new_q, 1)
        st.session_state[table_key] = chunk
        st.session_state[q_key] = new_q
        st.session_state[f"{role}_total_{DBKEY}"] = total

    df_show = st.session_state[table_key]
    st.dataframe(df_show, use_container_width=True, height=300)

    # choose from currently loaded fish
    codes = df_show["fish_code"].dropna().astype(str).tolist()
    choice = st.radio(f"Pick {role_label}", options=codes, key=f"{role}_radio_{DBKEY}") if codes else None
    return choice

# ---------- Step 1: infinite-scroll pickers for Mom/Dad ----------
tab_m, tab_d = st.tabs(["Mom", "Dad"])
with tab_m:
    mom_choice = _parent_picker("Mom")
with tab_d:
    dad_choice = _parent_picker("Dad")

# resolve to ids
with engine.begin() as conn:
    moms_map = {r["fish_code"]: r["id_uuid"] for r in Q.list_fish_minimal(conn, q=mom_choice or None, limit=1)} if mom_choice else {}
    dads_map = {r["fish_code"]: r["id_uuid"] for r in Q.list_fish_minimal(conn, q=dad_choice or None, limit=1)} if dad_choice else {}
mom_id = moms_map.get(mom_choice)
dad_id = dads_map.get(dad_choice)

created_by = st.text_input("Created by", placeholder="initials", key=f"by_{DBKEY}")

# ---------- Step 2: Inherited Features (from canonical table if present) ----------
st.subheader("2) Inherited Features")
def _list_parent_alleles(conn, fish_id: Optional[str]):
    if not fish_id:
        return []
    try:
        return conn.execute(text("""
            select
              fta.transgene_base_code,
              fta.allele_number,
              coalesce(fta.zygosity, 'het') as zygosity
            from public.fish_transgene_alleles fta
            where fta.fish_id = :fish_id
            order by fta.transgene_base_code, fta.allele_number
        """), {"fish_id": fish_id}).mappings().all()
    except Exception:
        return []

inherited_mom, inherited_dad = [], []
with engine.begin() as conn:
    mom_feats = _list_parent_alleles(conn, mom_id)
    dad_feats = _list_parent_alleles(conn, dad_id)

c_m, c_d = st.columns(2, vertical_alignment="top")
with c_m:
    st.markdown("**From Mom**")
    if not mom_feats: st.caption("No alleles found (or canonical table not present).")
    for r in mom_feats:
        key = f"mom_{r['transgene_base_code']}_{r['allele_number']}_{DBKEY}"
        label = f"{r['transgene_base_code']} • {r['allele_number']} • {r['zygosity']}"
        if st.checkbox(label, key=key, value=True):
            inherited_mom.append(r)
with c_d:
    st.markdown("**From Dad**")
    if not dad_feats: st.caption("No alleles found (or canonical table not present).")
    for r in dad_feats:
        key = f"dad_{r['transgene_base_code']}_{r['allele_number']}_{DBKEY}"
        label = f"{r['transgene_base_code']} • {r['allele_number']} • {r['zygosity']}"
        if st.checkbox(label, key=key, value=True):
            inherited_dad.append(r)

# ---------- Step 3: Create offspring (DB auto fish_code) ----------
st.subheader("3) Offspring Fish")
nickname = st.text_input("Nickname", key=f"nick_{DBKEY}")

create_ok = bool(mom_id and dad_id)
if st.button("Create Offspring", type="primary", disabled=not create_ok, key=f"create_{DBKEY}"):
    try:
        with engine.begin() as conn:
            # Cross record
            cross_id = conn.execute(
                text("""
                  insert into public.crosses (mom_id, dad_id, crossed_at, created_by)
                  values (:mom, :dad, now(), :by)
                  returning id_uuid
                """),
                {"mom": mom_id, "dad": dad_id, "by": created_by},
            ).scalar_one()

            # Offspring fish: DB trigger generates fish_code (FSH-YYXXL)
            new_id, new_code = conn.execute(
                text("""
                  insert into public.fish (name, created_by, cross_id)
                  values (:nick, :by, :cross)
                  returning id_uuid, fish_code
                """),
                {"nick": nickname or None, "by": created_by, "cross": cross_id},
            ).one()

            # Parentage edges
            conn.execute(text("""
              insert into public.fish_parentage (child_id, parent_id, relation, created_by)
              values (:c,:m,'mom',:by)
              on conflict do nothing
            """), {"c": new_id, "m": mom_id, "by": created_by})
            conn.execute(text("""
              insert into public.fish_parentage (child_id, parent_id, relation, created_by)
              values (:c,:d,'dad',:by)
              on conflict do nothing
            """), {"c": new_id, "d": dad_id, "by": created_by})

            # Inherited alleles (if table exists)
            def _insert_inherited(rows, parent):
                for r in rows:
                    conn.execute(text("""
                      insert into public.fish_inherited_transgene_alleles
                        (child_id, source_parent_id, transgene_base_code, allele_number, zygosity, created_by)
                      values
                        (:child, :parent, :base, :allele, :zyg, :by)
                      on conflict (child_id, transgene_base_code, allele_number) do nothing
                    """), {
                        "child": new_id,
                        "parent": parent,
                        "base": r["transgene_base_code"],
                        "allele": int(r["allele_number"]),
                        "zyg": r.get("zygosity") or "het",
                        "by": created_by,
                    })
            if inherited_mom: _insert_inherited(inherited_mom, mom_id)
            if inherited_dad: _insert_inherited(inherited_dad, dad_id)

        st.success(f"Created offspring {new_code}  (id {new_id})")
        st.session_state[f"offspring_id_{DBKEY}"] = new_id
        st.session_state[f"offspring_code_{DBKEY}"] = new_code

        # Promote button (copies inherited → canonical fish_transgene_alleles, if present)
        st.info("Optionally promote inherited alleles into the canonical genotype table for the new fish.")
        if st.button("✅ Promote inherited alleles to canonical", key=f"promote_{DBKEY}"):
            try:
                with engine.begin() as conn:
                    n = conn.execute(
                        text("select public.promote_inherited_alleles(:child,:actor)"),
                        {"child": new_id, "actor": created_by or None}
                    ).scalar_one()
                st.success(f"Promoted {n} allele(s) into canonical genotype.")
            except Exception as e:
                st.exception(e)

    except Exception as e:
        st.exception(e)

# ---------- Step 4: Apply treatments to offspring ----------
if st.session_state.get(f"offspring_id_{DBKEY}"):
    st.subheader("4) Apply Treatments to Offspring")
    st.caption(f"New offspring: {st.session_state[f'offspring_code_{DBKEY}']}")

    d = st.date_input("applied_on", value=datetime.now().date(), key=f"tdate_{DBKEY}")
    t = st.time_input("time", value=datetime.now().time().replace(microsecond=0), key=f"ttime_{DBKEY}")
    applied_ts = datetime.combine(d, t)

    with engine.begin() as conn:
        trows = Q.list_treatments_minimal(conn, limit=300)
    treat_label = st.selectbox(
        "Treatment",
        [r["treatment_type"] for r in trows],
        key=f"treat_{DBKEY}"
    ) if trows else None
    treat_id = {r["treatment_type"]: r["id_uuid"] for r in trows}.get(treat_label)

    if st.button("Apply Treatment", type="primary", key=f"apply_{DBKEY}"):
        try:
            with engine.begin() as conn:
                Q.insert_fish_treatment_minimal(
                    conn,
                    fish_id=st.session_state[f"offspring_id_{DBKEY}"],
                    treatment_id=treat_id,
                    applied_at=applied_ts.isoformat(),
                    batch_label=None,
                    created_by=created_by or None,
                )
            st.success("Treatment applied to new offspring.")
        except Exception as e:
            st.exception(e)

# ----- Recent crosses (graceful if view missing) -----
st.divider()
st.subheader("Recent crosses")
n = st.number_input("Rows", min_value=5, max_value=100, value=20, step=5, key=f"xrows_{DBKEY}")

try:
    with engine.begin() as conn:
        exists = conn.execute(text("""
            select 1
            from information_schema.views
            where table_schema='public' and table_name='v_recent_crosses'
        """)).scalar()
        if exists:
            rows = conn.execute(
                text("""
                  select cross_id, crossed_at, mom_code, dad_code, offspring_count, offspring_codes
                  from public.v_recent_crosses
                  order by crossed_at desc
                  limit :lim
                """),
                {"lim": int(n)}
            ).mappings().all()
            st.dataframe(rows, use_container_width=True)
        else:
            st.info("v_recent_crosses is not present in this database yet.")
except Exception as e:
    st.exception(e)