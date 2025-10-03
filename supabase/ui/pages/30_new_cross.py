# supabase/ui/pages/30_new_cross.py
from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

import os, hashlib, importlib, sys
from datetime import datetime
from typing import Optional
from pathlib import Path

import streamlit as st
from sqlalchemy import create_engine, text

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

DB_URL = os.environ.get("DB_URL")
if not DB_URL:
    st.error("DB_URL not set")
    st.stop()

engine = create_engine(DB_URL)
DBKEY = hashlib.md5(DB_URL.encode()).hexdigest()[:8]

# ---------- Step 1: Select parents ----------
st.subheader("1) Select Parents")
with engine.begin() as conn:
    moms = Q.list_fish_minimal(conn, limit=500)
    dads = Q.list_fish_minimal(conn, limit=500)

mom_label = st.selectbox("Mom", [m["fish_code"] for m in moms], key=f"mom_{DBKEY}") if moms else None
dad_label = st.selectbox("Dad", [d["fish_code"] for d in dads], key=f"dad_{DBKEY}") if dads else None
mom_id = {m["fish_code"]: m["id_uuid"] for m in moms}.get(mom_label)
dad_id = {d["fish_code"]: d["id_uuid"] for d in dads}.get(dad_label)

created_by = st.text_input("Created by", placeholder="initials", key=f"by_{DBKEY}")

# ---------- Step 2: Select inherited features (parent alleles) ----------
st.subheader("2) Inherited Features")
inherited_mom, inherited_dad = [], []

def _list_parent_alleles(conn, fish_id: Optional[str]):
    if not fish_id:
        return []
    try:
        # If fish_transgene_alleles exists:
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
        return []  # table not present in this environment

with engine.begin() as conn:
    mom_feats = _list_parent_alleles(conn, mom_id)
    dad_feats = _list_parent_alleles(conn, dad_id)

col_m, col_d = st.columns(2, vertical_alignment="top")
with col_m:
    st.markdown("**From Mom**")
    if not mom_feats:
        st.caption("No alleles found (or table not present).")
    for r in mom_feats:
        key = f"mom_{r['transgene_base_code']}_{r['allele_number']}_{DBKEY}"
        label = f"{r['transgene_base_code']} • {r['allele_number']} • {r['zygosity']}"
        if st.checkbox(label, key=key, value=True):
            inherited_mom.append(r)

with col_d:
    st.markdown("**From Dad**")
    if not dad_feats:
        st.caption("No alleles found (or table not present).")
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
            # insert cross
            cross_id = conn.execute(
                text("""
                  insert into public.crosses (mom_id, dad_id, crossed_at, created_by)
                  values (:mom, :dad, now(), :by)
                  returning id_uuid
                """),
                {"mom": mom_id, "dad": dad_id, "by": created_by},
            ).scalar_one()

            # create fish (DB will generate fish_code via trigger)
            new_id, new_code = conn.execute(
                text("""
                  insert into public.fish (name, created_by, cross_id)
                  values (:nick, :by, :cross)
                  returning id_uuid, fish_code
                """),
                {"nick": nickname or None, "by": created_by, "cross": cross_id},
            ).one()

            # parentage edges
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

            # inherited alleles (if table exists)
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

        st.success(f"Created offspring fish {new_code}  (id {new_id})")
        st.session_state[f"offspring_id_{DBKEY}"] = new_id
        st.session_state[f"offspring_code_{DBKEY}"] = new_code
    except Exception as e:
        st.exception(e)

# ---------- Step 4: Apply treatments to offspring ----------
if st.session_state.get(f"offspring_id_{DBKEY}"):
    st.subheader("4) Apply Treatments to Offspring")
    st.caption(f"New offspring: {st.session_state[f'offspring_code_{DBKEY}']}")

    # When (you can extend with dose/unit/vehicle like the other page)
    d = st.date_input("applied_on", value=datetime.now().date(), key=f"tdate_{DBKEY}")
    t = st.time_input("time", value=datetime.now().time().replace(microsecond=0), key=f"ttime_{DBKEY}")
    applied_ts = datetime.combine(d, t)

    # Treatment picker
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
# ----- Recent crosses -----
st.divider()
st.subheader("Recent crosses")
n = st.number_input("Rows", min_value=5, max_value=100, value=20, step=5, key=f"xrows_{DBKEY}")

try:
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
              select cross_id, crossed_at, mom_code, dad_code, offspring_count, offspring_codes
              from v_recent_crosses
              order by crossed_at desc
              limit :lim
            """),
            {"lim": int(n)}
        ).mappings().all()
    st.dataframe(rows, use_container_width=True)
except Exception as e:
    st.exception(e)