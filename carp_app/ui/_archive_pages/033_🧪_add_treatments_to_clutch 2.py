from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
from typing import List, Dict, Tuple

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

_tmsg = st.session_state.pop("treatments_result", None)
if _tmsg:
    if _tmsg.get("plasmids"):
        st.success(f"Attached {_tmsg['plasmids']} plasmid(s).")
    if _tmsg.get("rnas"):
        st.success(f"Attached {_tmsg['rnas']} RNA(s).")
    if _tmsg.get("errs"):
        st.warning("Some items were skipped:\n- " + "\n- ".join(_tmsg["errs"]))

_ENGINE = None
def _eng():
    global _ENGINE
    if _ENGINE: return _ENGINE
    url = os.getenv("DB_URL")
    if not url: st.error("DB_URL not set"); st.stop()
    _ENGINE = get_engine()
    return _ENGINE

def _view_exists(schema: str, name: str) -> bool:
    with _eng().begin() as cx:
        q = text("select 1 from information_schema.views where table_schema=:s and table_name=:t limit 1")
        return bool(pd.read_sql(q, cx, params={"s": schema, "t": name}).shape[0])

def _table_exists(schema: str, name: str) -> bool:
    with _eng().begin() as cx:
        q = text("select 1 from information_schema.tables where table_schema=:s and table_name=:t limit 1")
        return bool(pd.read_sql(q, cx, params={"s": schema, "t": name}).shape[0])

def _cols(schema: str, name: str) -> List[str]:
    with _eng().begin() as cx:
        q = text("select column_name from information_schema.columns where table_schema=:s and table_name=:t order by ordinal_position")
        return pd.read_sql(q, cx, params={"s": schema, "t": name})["column_name"].tolist()

def _safe_date(v):
    try:
        return pd.to_datetime(v).date() if pd.notna(v) else None
    except Exception:
        return None

def _load_clutches(d1: date, d2: date, created_by: str, q: str, ignore_dates: bool) -> pd.DataFrame:
    if not _view_exists("public", "v_clutches_overview_final"):
        st.error("Required view public.v_clutches_overview_final not found."); st.stop()

    where_bits, params = [], {}
    if not ignore_dates:
        where_bits.append("coalesce(clutch_birthday, date_planned) between :d1 and :d2")
        params["d1"], params["d2"] = d1, d2
    if (created_by or "").strip():
        where_bits.append("(created_by_instance ilike :byl or created_by_plan ilike :byl)")
        params["byl"] = f"%{created_by.strip()}%"
    if (q or "").strip():
        where_bits.append("""(
          coalesce(clutch_code,'') ilike :ql or
          coalesce(cross_name_pretty,'') ilike :ql or
          coalesce(cross_name,'') ilike :ql or
          coalesce(clutch_name,'') ilike :ql or
          coalesce(clutch_nickname,'') ilike :ql or
          coalesce(clutch_genotype_pretty,'') ilike :ql or
          coalesce(clutch_genotype_canonical,'') ilike :ql or
          coalesce(mom_strain,'') ilike :ql or
          coalesce(dad_strain,'') ilike :ql or
          coalesce(clutch_strain,'') ilike :ql
        )""")
        params["ql"] = f"%{q.strip()}%"
    where_sql = " AND ".join(where_bits) if where_bits else "true"

    sql = text(f"""
      select *
      from public.v_clutches_overview_final
      where {where_sql}
      order by created_at_instance desc nulls last, clutch_birthday desc nulls last
      limit 500
    """)
    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params=params)

def _load_plasmids(search: str) -> Tuple[pd.DataFrame, str]:
    if not _table_exists("public","plasmids"): return pd.DataFrame(), "(none)"
    with _eng().begin() as cx:
        df = pd.read_sql(text("""
          select code, name, coalesce(nickname,'') as nickname, created_at, created_by
          from public.plasmids
          where (:q = '' OR coalesce(code,'') ilike :ql OR coalesce(name,'') ilike :ql OR coalesce(nickname,'') ilike :ql)
          order by coalesce(created_at, now()) desc
          limit 1000
        """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})
    return df, "plasmids"

def _load_rnas(search: str) -> Tuple[pd.DataFrame, str]:
    if not _view_exists("public","v_rna_plasmids"): return pd.DataFrame(), "(none)"
    with _eng().begin() as cx:
        df = pd.read_sql(text("""
          select code, name, coalesce(nickname,'') as nickname, created_at, created_by
          from public.v_rna_plasmids
          where (:q = '' OR coalesce(code,'') ilike :ql OR coalesce(name,'') ilike :ql OR coalesce(nickname,'') ilike :ql)
          order by coalesce(created_at, now()) desc
          limit 1000
        """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})
    return df, "v_rna_plasmids"

def _insert_treatments(clutch_id: str, created_by: str, items: List[Dict], kind: str, note: str):
    if not _table_exists("public", "clutch_plan_treatments"):
        st.error("Table public.clutch_plan_treatments not found"); return 0, []
    cols = set(_cols("public", "clutch_plan_treatments"))
    use_generic = {"material_type","material_code","material_name","notes"}.issubset(cols)
    use_plasmid = ("plasmid_code" in cols) and ("notes" in cols)
    use_rna     = ("rna_code" in cols) and ("notes" in cols)
    inserted, errs = 0, []
    with _eng().begin() as cx:
        for it in items:
            code = str(it.get("code") or it.get("id") or "").strip()
            name = str(it.get("name") or "").strip()
            if not code:
                errs.append(f"{kind}:<empty-code> → skipped"); continue
            try:
                if use_generic:
                    cx.execute(text("""
                      insert into public.clutch_plan_treatments
                        (clutch_id, material_type, material_code, material_name, notes)
                      select cast(:cid as uuid), :kind, :code, :name, :notes
                      where not exists (
                        select 1 from public.clutch_plan_treatments
                        where clutch_id = cast(:cid as uuid)
                          and material_type = :kind
                          and material_code = :code
                      )
                    """), {"cid": clutch_id, "kind": kind, "code": code,
                           "name": name or code, "notes": note or ""})
                elif use_plasmid and kind == "plasmid":
                    cx.execute(text("""
                      insert into public.clutch_plan_treatments
                        (clutch_id, plasmid_code, notes)
                      select cast(:cid as uuid), :code, :notes
                      where not exists (
                        select 1 from public.clutch_plan_treatments
                        where clutch_id = cast(:cid as uuid) and plasmid_code = :code
                      )
                    """), {"cid": clutch_id, "code": code, "notes": note or ""})
                elif use_rna and kind == "rna":
                    cx.execute(text("""
                      insert into public.clutch_plan_treatments
                        (clutch_id, rna_code, notes)
                      select cast(:cid as uuid), :code, :notes
                      where not exists (
                        select 1 from public.clutch_plan_treatments
                        where clutch_id = cast(:cid as uuid) and rna_code = :code
                      )
                    """), {"cid": clutch_id, "code": code, "notes": note or ""})
                else:
                    raise RuntimeError("Unsupported clutch_plan_treatments schema (missing 'notes')")
                inserted += 1
            except Exception as e:
                errs.append(f"{kind}:{code} → {e}")
    return inserted, errs

with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1,c2,c3,c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=120))
    with c2: d2 = st.date_input("To",   value=today + timedelta(days=14))
    with c3: created_by = st.text_input("Created by (plan/instance)", value="")
    with c4: q = st.text_input("Search (code/cross/clutch/genotype/strain)", value="")
    r1, r2 = st.columns([1,3])
    with r1: ignore_dates = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", use_container_width=True)

clutches = _load_clutches(d1, d2, created_by, q, ignore_dates)
st.caption(f"{len(clutches)} clutch(es)")

if clutches.empty:
    st.info("No clutches found with the current filters.")
    st.stop()

view_cols = [
    "clutch_code","clutch_birthday","cross_name_pretty",
    "genotype_treatment_rollup",   # ← NEW (visible)
    "clutch_genotype_pretty","clutch_genotype_canonical",
    "mom_genotype","dad_genotype",
    "mom_strain","dad_strain","clutch_strain_pretty",
    "treatments_count","treatments_pretty",
    "created_by_instance","created_at_instance",
]
have = [c for c in view_cols if c in clutches.columns]
dfv = clutches[have].copy()
dfv.insert(0, "✓ Select", False)

clutch_edit = st.data_editor(
    dfv, hide_index=True, use_container_width=True, num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True),
        "created_at_instance": st.column_config.DatetimeColumn("created_at_instance", disabled=True),
        "treatments_count":  st.column_config.NumberColumn("treatments_count"),
        "treatments_pretty": st.column_config.TextColumn("treatments_pretty"),
    },
    key="clutch_pick_editor",
)
sel_mask = clutch_edit.get("✓ Select", pd.Series(False, index=clutch_edit.index)).fillna(False).astype(bool)
picked = clutches.loc[sel_mask, :].reset_index(drop=True)

if picked.empty:
    st.info("Select a clutch above to attach treatments.")
    st.stop()

target = picked.iloc[0]
clutch_id = str(target.get("clutch_id",""))

st.subheader("Selected clutch")
st.write(pd.DataFrame([{
    "clutch_code": target.get("clutch_code",""),
    "cross_name_pretty": target.get("cross_name_pretty",""),
    "clutch_name": target.get("clutch_name", target.get("clutch_genotype_pretty","")),
    "clutch_nickname": target.get("clutch_nickname", target.get("clutch_name","")),
    "clutch_genotype_pretty": target.get("clutch_genotype_pretty",""),
    "clutch_genotype_canonical": target.get("clutch_genotype_canonical",""),
    "mom_genotype": target.get("mom_genotype",""),
    "dad_genotype": target.get("dad_genotype",""),
    "mom_strain": target.get("mom_strain",""),
    "dad_strain": target.get("dad_strain",""),
    "clutch_strain_pretty": target.get("clutch_strain_pretty",""),
    "treatments_count": int(target.get("treatments_count") or 0),
    "genotype_treatment_rollup": target.get("genotype_treatment_rollup",""),  # ← NEW
    "treatments_pretty": target.get("treatments_pretty",""),                  # ← NEW
    "clutch_birthday": _safe_date(target.get("clutch_birthday")),
    "date_planned": _safe_date(target.get("date_planned")),
    "created_by_plan": target.get("created_by_plan",""),
    "created_at_plan": target.get("created_at_plan",""),
    "created_by_instance": target.get("created_by_instance",""),
    "created_at_instance": target.get("created_at_instance",""),
}]))

st.subheader("Current treatments")
def _load_existing_treatments(clutch_id: str) -> pd.DataFrame:
    if not _table_exists("public", "clutch_plan_treatments"):
        return pd.DataFrame()
    with _eng().begin() as cx:
        sql = text("""
          select created_at, material_type, material_code, material_name, notes
          from public.clutch_plan_treatments
          where clutch_id = :cid
          order by created_at desc nulls last
        """)
        return pd.read_sql(sql, cx, params={"cid": clutch_id})

cur = _load_existing_treatments(clutch_id)
if cur.empty:
    st.caption("No treatments attached yet.")
else:
    st.dataframe(cur, use_container_width=True, hide_index=True)

st.subheader("Add treatments")
tabs = st.tabs(["Plasmids","RNAs"])

def _load_plasmids(search: str) -> Tuple[pd.DataFrame, str]:
    if not _table_exists("public","plasmids"): return pd.DataFrame(), "(none)"
    with _eng().begin() as cx:
        df = pd.read_sql(text("""
          select code, name, coalesce(nickname,'') as nickname, created_at, created_by
          from public.plasmids
          where (:q = '' OR coalesce(code,'') ilike :ql OR coalesce(name,'') ilike :ql OR coalesce(nickname,'') ilike :ql)
          order by coalesce(created_at, now()) desc
          limit 1000
        """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})
    return df, "plasmids"

def _load_rnas(search: str) -> Tuple[pd.DataFrame, str]:
    if not _view_exists("public","v_rna_plasmids"): return pd.DataFrame(), "(none)"
    with _eng().begin() as cx:
        df = pd.read_sql(text("""
          select code, name, coalesce(nickname,'') as nickname, created_at, created_by
          from public.v_rna_plasmids
          where (:q = '' OR coalesce(code,'') ilike :ql OR coalesce(name,'') ilike :ql OR coalesce(nickname,'') ilike :ql)
          order by coalesce(created_at, now()) desc
          limit 1000
        """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})
    return df, "v_rna_plasmids"

with tabs[0]:
    c1, c2 = st.columns([2,1])
    with c1: q_pl = st.text_input("Search plasmids (code / name / nickname / fluors / resistance)", value="")
    with c2: note_pl = st.text_input("Note for selected plasmids", value="")
    df_pl, src_pl = _load_plasmids(q_pl)
    st.caption(f"{len(df_pl)} plasmid(s) • source: {src_pl}")
    if df_pl.empty:
        picked_pl = pd.DataFrame()
    else:
        df_pl = df_pl.copy()
        df_pl.insert(0, "✓ Select", False)
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
    df_rna, src_rna = _load_rnas(q_rna)
    st.caption(f"{len(df_rna)} RNA(s) • source: {src_rna}")
    if df_rna.empty:
        picked_rna = pd.DataFrame()
    else:
        df_rna = df_rna.copy()
        df_rna.insert(0, "✓ Select", False)
        eg_rna = st.data_editor(
            df_rna, hide_index=True, use_container_width=True, num_rows="fixed",
            column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
            key="rnas_editor",
        )
        picked_rna = eg_rna[eg_rna["✓ Select"]].reset_index(drop=True)

st.subheader("Save")
creator = os.environ.get("USER") or os.environ.get("USERNAME") or "system"

b1, b2, b3 = st.columns(3)
with b1:
    if st.button("➕ Attach selected plasmids", use_container_width=True, key="attach_plasmids"):
        items = picked_pl.to_dict("records") if not picked_pl.empty else []
        n, errs = _insert_treatments(clutch_id, creator, items, "plasmid", note_pl)
        st.session_state["treatments_result"] = {"plasmids": n, "errs": errs}
        st.rerun()
with b2:
    if st.button("➕ Attach selected RNAs", use_container_width=True, key="attach_rnas"):
        items = picked_rna.to_dict("records") if not picked_rna.empty else []
        n, errs = _insert_treatments(clutch_id, creator, items, "rna", note_rna)
        st.session_state["treatments_result"] = {"rnas": n, "errs": errs}
        st.rerun()
with b3:
    if st.button("↻ Refresh", use_container_width=True, key="refresh_page"):
        st.rerun()