from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
from typing import List, Dict

import pandas as pd
import streamlit as st
from sqlalchemy import text

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.lib.config import engine as get_engine

sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="🧪 Add treatments to clutch", page_icon="🧪", layout="wide")
st.title("🧪 Add treatments to clutch")

_ENGINE = None
def _eng():
    global _ENGINE
    if _ENGINE: return _ENGINE
    url = os.getenv("DB_URL")
    if not url: st.error("DB_URL not set"); st.stop()
    _ENGINE = get_engine()
    return _ENGINE

def _table_exists(schema: str, name: str) -> bool:
    with _eng().begin() as cx:
        q = text("""select 1 from information_schema.tables where table_schema=:s and table_name=:t limit 1""")
        return bool(pd.read_sql(q, cx, params={"s": schema, "t": name}).shape[0])

def _cols(schema: str, name: str) -> List[str]:
    with _eng().begin() as cx:
        q = text("""select column_name from information_schema.columns where table_schema=:s and table_name=:t order by ordinal_position""")
        return pd.read_sql(q, cx, params={"s": schema, "t": name})["column_name"].tolist()

def _load_clutches(d1: date, d2: date, created_by: str, q: str) -> pd.DataFrame:
    sql = text("""
      select
        cl.id::text           as clutch_id,
        coalesce(cl.clutch_instance_code, left(cl.id::text, 8)) as clutch_code,
        ci.cross_run_code     as cross_run,
        ci.cross_date         as cross_date,
        x.cross_code          as cross_code,
        coalesce(x.cross_name_code, x.cross_code) as cross_name,
        coalesce(x.cross_name_genotype,'')        as cross_name_genotype,
        cl.created_by,
        cl.created_at
      from public.clutches cl
      join public.cross_instances ci on ci.id = cl.cross_instance_id
      join public.crosses x          on x.id  = ci.cross_id
      where (ci.cross_date between :d1 and :d2)
        and (:by = '' or cl.created_by ilike :byl)
        and (
          :q = '' or
          coalesce(cl.clutch_instance_code, left(cl.id::text,8)) ilike :ql or
          ci.cross_run_code ilike :ql or
          x.cross_code ilike :ql or
          coalesce(x.cross_name_code,'') ilike :ql or
          coalesce(x.cross_name_genotype,'') ilike :ql
        )
      order by ci.cross_date desc, cl.created_at desc
      limit 500
    """)
    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params={"d1": d1, "d2": d2, "by": created_by or "", "byl": f"%{created_by or ''}%", "q": q or "", "ql": f"%{q or ''}%"})

def _load_catalog(table_name: str, search: str) -> pd.DataFrame:
    if not _table_exists("public", table_name):
        return pd.DataFrame()
    with _eng().begin() as cx:
        cols = _cols("public", table_name)
        sel = []
        for c in ["code","name","nickname","fluors","resistance","supports_invitro_rna","created_at","created_by"]:
            if c in cols: sel.append(c)
        if "id" in cols and "code" not in cols: sel.insert(0, "id")
        base = ", ".join(sel) if sel else "*"
        sql = text(f"""
          select {base}
          from public.{table_name}
          where (:q = '' or coalesce(code,'') ilike :ql or coalesce(name,'') ilike :ql or coalesce(nickname,'') ilike :ql)
          order by coalesce(code,name,nickname) asc
          limit 1000
        """)
        return pd.read_sql(sql, cx, params={"q": search or "", "ql": f"%{search or ''}%"})

def _load_existing_treatments(clutch_id: str) -> pd.DataFrame:
    if not _table_exists("public", "clutch_plan_treatments"):
        return pd.DataFrame()
    with _eng().begin() as cx:
        sql = text("select * from public.clutch_plan_treatments where clutch_id = :cid order by created_at desc nulls last")
        return pd.read_sql(sql, cx, params={"cid": clutch_id})

def _insert_treatments(clutch_id: str, created_by: str, items: List[Dict], kind: str, note: str):
    if not _table_exists("public", "clutch_plan_treatments"):
        st.error("Table public.clutch_plan_treatments not found"); return 0, []
    cols = set(_cols("public", "clutch_plan_treatments"))
    inserted, errs = 0, []
    with _eng().begin() as cx:
        for it in items:
            code = it.get("code") or it.get("id") or ""
            try:
                if "plasmid_code" in cols and kind == "plasmid":
                    cx.execute(text("""
                      insert into public.clutch_plan_treatments (clutch_id, plasmid_code, note, created_by)
                      select :cid, :code, :note, :by
                      where not exists (select 1 from public.clutch_plan_treatments where clutch_id=:cid and plasmid_code=:code)
                    """), {"cid": clutch_id, "code": str(code), "note": note or "", "by": created_by})
                elif "rna_code" in cols and kind == "rna":
                    cx.execute(text("""
                      insert into public.clutch_plan_treatments (clutch_id, rna_code, note, created_by)
                      select :cid, :code, :note, :by
                      where not exists (select 1 from public.clutch_plan_treatments where clutch_id=:cid and rna_code=:code)
                    """), {"cid": clutch_id, "code": str(code), "note": note or "", "by": created_by})
                elif {"treatment_kind","treatment_code"}.issubset(cols):
                    cx.execute(text("""
                      insert into public.clutch_plan_treatments (clutch_id, treatment_kind, treatment_code, note, created_by)
                      select :cid, :kind, :code, :note, :by
                      where not exists (
                        select 1 from public.clutch_plan_treatments
                        where clutch_id=:cid and treatment_kind=:kind and treatment_code=:code
                      )
                    """), {"cid": clutch_id, "kind": kind, "code": str(code), "note": note or "", "by": created_by})
                else:
                    raise RuntimeError("Unsupported clutch_plan_treatments schema")
                inserted += 1
            except Exception as e:
                errs.append(f"{kind}:{code} → {e}")
    return inserted, errs

with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1,c2,c3,c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=30))
    with c2: d2 = st.date_input("To", value=today)
    with c3: created_by = st.text_input("Created by", value=os.environ.get("USER") or os.environ.get("USERNAME") or "")
    with c4: q = st.text_input("Search clutches (code/run/name/genotype)", value="")
    st.form_submit_button("Apply", use_container_width=True)

clutches = _load_clutches(d1, d2, created_by, q)
st.caption(f"{len(clutches)} clutch(es)")

if clutches.empty:
    st.info("No clutches found in this range.")
    st.stop()

view_cols = ["clutch_code","cross_run","cross_date","cross_code","cross_name","cross_name_genotype","created_by","created_at"]
dfv = clutches[view_cols].copy()
dfv.insert(0, "✓ Select", False)

clutch_edit = st.data_editor(
    dfv, hide_index=True, use_container_width=True, num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "cross_date": st.column_config.DateColumn("cross_date", disabled=True),
        "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
    },
    key="clutch_pick_editor",
)
sel_mask = clutch_edit.get("✓ Select", pd.Series(False, index=clutch_edit.index)).fillna(False).astype(bool)
picked = clutches.loc[sel_mask, :].reset_index(drop=True)

if picked.empty:
    st.info("Select a clutch above to attach treatments.")
    st.stop()

target = picked.iloc[0]
st.subheader("Selected clutch")
st.write(pd.DataFrame([{
    "clutch_code": target["clutch_code"],
    "cross_run": target["cross_run"],
    "cross_date": pd.to_datetime(target["cross_date"]).date(),
    "cross_code": target["cross_code"],
    "cross_name": target["cross_name"],
    "genotype": target["cross_name_genotype"],
}]))

st.subheader("Current treatments")
cur = _load_existing_treatments(target["clutch_id"])
if cur.empty:
    st.caption("No treatments attached yet.")
else:
    st.dataframe(cur, use_container_width=True, hide_index=True)

st.subheader("Add treatments")
tabs = st.tabs(["Plasmids","RNAs"])
with tabs[0]:
    c1, c2 = st.columns([2,1])
    with c1: q_pl = st.text_input("Search plasmids (code / name / nickname / fluors / resistance)", value="")
    with c2: note_pl = st.text_input("Note for selected plasmids", value="")
    df_pl = _load_catalog("plasmids", q_pl)
    if df_pl.empty:
        st.caption("No plasmids found.")
        picked_pl = pd.DataFrame()
    else:
        df_pl = df_pl.copy()
        if "code" not in df_pl.columns:
            df_pl.insert(0,"code",df_pl.get("id").astype(str))
        df_pl.insert(0,"✓ Select", False)
        eg_pl = st.data_editor(
            df_pl, hide_index=True, use_container_width=True, num_rows="fixed",
            column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
            key="plasmids_editor",
        )
        picked_pl = eg_pl[eg_pl["✓ Select"]].reset_index(drop=True)

with tabs[1]:
    c1, c2 = st.columns([2,1])
    with c1: q_rna = st.text_input("Search RNAs (code / name / nickname)", value="")
    with c2: note_rna = st.text_input("Note for selected RNAs", value="")
    df_rna = _load_catalog("rnas", q_rna)
    if df_rna.empty:
        st.caption("No RNAs found.")
        picked_rna = pd.DataFrame()
    else:
        df_rna = df_rna.copy()
        if "code" not in df_rna.columns:
            df_rna.insert(0,"code",df_rna.get("id").astype(str))
        df_rna.insert(0,"✓ Select", False)
        eg_rna = st.data_editor(
            df_rna, hide_index=True, use_container_width=True, num_rows="fixed",
            column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
            key="rnas_editor",
        )
        picked_rna = eg_rna[eg_rna["✓ Select"]].reset_index(drop=True)

st.subheader("Save")
creator = os.environ.get("USER") or os.environ.get("USERNAME") or "system"

btn1, btn2, btn3 = st.columns(3)
with btn1:
    if st.button("➕ Attach selected plasmids", use_container_width=True, disabled=picked_pl.empty):
        items = picked_pl.to_dict("records")
        n, errs = _insert_treatments(target["clutch_id"], creator, items, "plasmid", note_pl)
        if n: st.success(f"Attached {n} plasmid(s).")
        for e in errs: st.error(e)
        st.rerun()
with btn2:
    if st.button("➕ Attach selected RNAs", use_container_width=True, disabled=picked_rna.empty):
        items = picked_rna.to_dict("records")
        n, errs = _insert_treatments(target["clutch_id"], creator, items, "rna", note_rna)
        if n: st.success(f"Attached {n} RNA(s).")
        for e in errs: st.error(e)
        st.rerun()
with btn3:
    if st.button("↻ Refresh", use_container_width=True):
        st.rerun()