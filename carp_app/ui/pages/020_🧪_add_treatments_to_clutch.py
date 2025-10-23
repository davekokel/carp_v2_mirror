from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os, time
from datetime import date, timedelta
from typing import List, Dict, Tuple, Optional

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

def _view_exists(schema: str, name: str) -> bool:
    with _eng().begin() as cx:
        q = text("select 1 from information_schema.views where table_schema=:s and table_name=:t limit 1")
        return bool(pd.read_sql(q, cx, params={"s": schema, "t": name}).shape[0])

def _table_exists(schema: str, name: str) -> bool:
    with _eng().begin() as cx:
        q = text("select 1 from information_schema.tables where table_schema=:s and table_name=:t limit 1")
        return bool(pd.read_sql(q, cx, params={"s": schema, "t": name}).shape[0])

def _safe_date(v):
    try:
        return pd.to_datetime(v).date() if pd.notna(v) else None
    except Exception:
        return None

def _load_clutches(d_from, d_to, created_by: str, q: str, most_recent: bool) -> pd.DataFrame:
    """
    Source of truth: public.v_clutches (canonical).
    We pull the minimal columns and alias to what the grid expects.
    """
    where, params = [], {}

    if not most_recent:
        where.append("created_at::date between :d1 and :d2")
        params.update({"d1": d_from, "d2": d_to})

    if created_by.strip():
        where.append("coalesce(created_by,'') ilike :by")
        params["by"] = f"%{created_by.strip()}%"

    if q.strip():
        params["q"] = f"%{q.strip()}%"
        where.append("""
          (
            coalesce(clutch_code,'') ilike :q OR
            coalesce(name,'')        ilike :q OR
            coalesce(nickname,'')    ilike :q OR
            coalesce(mom_code,'')    ilike :q OR
            coalesce(dad_code,'')    ilike :q
          )
        """)

    where_sql = ("where " + " AND ".join(where)) if where else ""

    sql = text(f"""
      select
        clutch_code,
        name     as clutch_name,
        nickname as clutch_nickname,
        mom_code,
        dad_code,
        created_by,
        created_at
      from public.v_clutches
      {where_sql}
      order by created_at desc nulls last, clutch_code
      limit 1000
    """)

    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    # hygiene for grid
    for c in ["clutch_code","clutch_name","clutch_nickname","mom_code","dad_code","created_by"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str)

    # keep shape the rest of the page tolerates
    for c in ["treatments_count","treatments_pretty","created_by_instance","created_at_instance","clutch_birthday"]:
        if c not in df.columns:
            df[c] = pd.NA
    if "created_at" in df.columns:
        df["created_at_instance"] = df["created_at"]

    return df

def _resolve_ids_from_ci_or_cr(code_in: str) -> Tuple[Optional[str], Optional[str]]:
    import re, unicodedata
    def norm(s: str) -> str:
        if not s: return ""
        s = unicodedata.normalize("NFKC", s)
        s = s.replace("–", "-").replace("—", "-").replace("−", "-")
        s = re.sub(r"\s+", "", s)
        return s.upper()
    code = norm(code_in)
    if not code:
        return None, None
    def _ensure_ci_for_xid(xid: str) -> Optional[str]:
        with _eng().begin() as cx:
            lab = pd.read_sql(text("""
                select (cp.clutch_code || ' / ' || x.cross_run_code) as lbl
                from public.cross_instances x
                join public.crosses c          on c.id = x.cross_id
                join public.planned_crosses pc on pc.cross_id = c.id
                join public.clutch_plans cp    on cp.id = pc.clutch_id
                where x.id = cast(:xid as uuid)
                limit 1
            """), cx, params={"xid": xid})
            label = lab["lbl"].iloc[0] if not lab.empty else "clutch"
            cx.execute(text("""
                insert into public.clutch_instances (cross_instance_id, label, created_at)
                values (cast(:xid as uuid), :label, now())
                on conflict (cross_instance_id) do nothing
            """), {"xid": xid, "label": label})
            ci = pd.read_sql(text("""
                select id::text as clutch_instance_id
                from public.clutch_instances
                where cross_instance_id = cast(:xid as uuid)
                limit 1
            """), cx, params={"xid": xid})
            return ci["clutch_instance_id"].iloc[0] if not ci.empty else None
    if code.startswith("CI-"):
        with _eng().begin() as cx:
            exact = pd.read_sql(text("""
                select x.id::text as cross_instance_id,
                       ci.id::text as clutch_instance_id
                from public.clutch_instances ci
                join public.cross_instances x on x.id = ci.cross_instance_id
                where upper(replace(ci.clutch_instance_code, ' ', '')) = :ci
                limit 1
            """), cx, params={"ci": code})
        if not exact.empty:
            return exact["cross_instance_id"].iloc[0], exact["clutch_instance_id"].iloc[0]
        remainder = code[3:] if len(code) > 3 else ""
        candidates: List[str] = []
        if remainder:
            candidates.append(remainder)
        tokens = re.findall(r"(CR(?:OSS)?-[A-Z0-9\-]+)", code)
        candidates += tokens
        cand = []
        seen = set()
        for c in candidates:
            c = norm(c)
            if c and c not in seen:
                seen.add(c); cand.append(c)
        if cand:
            with _eng().begin() as cx:
                run = pd.read_sql(text("""
                    select x.id::text as cross_instance_id
                    from public.cross_instances x
                    where upper(replace(x.cross_run_code, ' ', '')) = any(:codes)
                    limit 1
                """), cx, params={"codes": cand})
            if not run.empty:
                xid = run["cross_instance_id"].iloc[0]
                cid = _ensure_ci_for_xid(xid)
                return xid, cid
        if cand:
            like_params = [f"%{c}%" for c in cand]
            with _eng().begin() as cx:
                run = pd.read_sql(text("""
                    select x.id::text as cross_instance_id
                    from public.cross_instances x
                    where """ + " OR ".join([f"x.cross_run_code ILIKE :p{i}" for i in range(len(like_params))]) + """
                    order by x.created_at desc nulls last
                    limit 1
                """), cx, params={f"p{i}": like_params[i] for i in range(len(like_params))})
            if not run.empty:
                xid = run["cross_instance_id"].iloc[0]
                cid = _ensure_ci_for_xid(xid)
                return xid, cid
        return None, None
    if code.startswith("CR"):
        with _eng().begin() as cx:
            cr = pd.read_sql(text("""
                select x.id::text as cross_instance_id
                from public.cross_instances x
                where upper(replace(x.cross_run_code, ' ', '')) = :rc
                limit 1
            """), cx, params={"rc": code})
        if cr.empty:
            with _eng().begin() as cx:
                cr = pd.read_sql(text("""
                    select x.id::text as cross_instance_id
                    from public.cross_instances x
                    where x.cross_run_code ILIKE :rc
                    order by x.created_at desc nulls last
                    limit 1
                """), cx, params={"rc": f"%{code}%"})
        if not cr.empty:
            xid = cr["cross_instance_id"].iloc[0]
            cid = _ensure_ci_for_xid(xid)
            return xid, cid
    return None, None

def _load_instance_treatments(clutch_instance_id: str) -> pd.DataFrame:
    if not _table_exists("public", "clutch_instance_treatments"):
        return pd.DataFrame()
    with _eng().begin() as cx:
        sql = text("""
          select created_at, material_type, material_code, material_name, notes, created_by
          from public.clutch_instance_treatments
          where clutch_instance_id = cast(:cid as uuid)
          order by created_at desc nulls last
        """)
        return pd.read_sql(sql, cx, params={"cid": clutch_instance_id})

def _insert_instance_treatments(clutch_instance_id: str, created_by: str, items: List[Dict], note: str):
    if not _table_exists("public", "clutch_instance_treatments"):
        st.error("Table public.clutch_instance_treatments not found"); return 0, []
    inserted, errs = 0, []
    with _eng().begin() as cx:
        for it in items:
            code = str(it.get("code") or it.get("id") or "").strip()
            name = str(it.get("name") or "").strip()
            if not code:
                errs.append(f"<empty-code> → skipped"); continue
            try:
                cx.execute(text("""
                  insert into public.clutch_instance_treatments
                    (clutch_instance_id, material_type, material_code, material_name, notes, created_by)
                  values
                    (cast(:iid as uuid), :kind, :code, :name, :notes, :who)
                  on conflict (clutch_instance_id,
                               lower(coalesce(material_type,'')),
                               lower(coalesce(material_code,'')))
                  do nothing
                """), {
                    "iid": clutch_instance_id,
                    "kind": ("plasmid" if it.get("source") == "plasmids" else
                             "rna" if it.get("source") == "v_rna_plasmids" else
                             it.get("material_type") or "generic"),
                    "code": code,
                    "name": name or code,
                    "notes": note or "",
                    "who": created_by or "",
                })
                inserted += 1
            except Exception as e:
                errs.append(f"{code} → {e}")
    return inserted, errs

def _load_run_overview(ci_code: str) -> pd.DataFrame:
    view = "public.v_clutches"
    if not _view_exists("public", "v_clutches"):
        return pd.DataFrame()

    with _eng().begin() as cx:
        df = pd.read_sql(text(f"""
            select *
            from {view}
            where clutch_code = :cc
            order by created_at desc nulls last
            limit 1
        """), cx, params={"cc": ci_code})

    if df.empty:
        return df

    # Normalize column names so the UI can read a stable set
    # Accept either “…_effective” or base names
    name_map = {
        "treatments_count_effective":        ["treatments_count_effective", "treatments_count"],
        "treatments_pretty_effective":       ["treatments_pretty_effective","treatments_pretty"],
        "genotype_treatment_rollup_effective":["genotype_treatment_rollup_effective","genotype_treatment_rollup"],
    }
    for target, options in name_map.items():
        for src in options:
            if src in df.columns:
                df[target] = df[src]
                break
        if target not in df.columns:
            df[target] = pd.NA

    if "treatments_count_effective" in df.columns:
        df["treatments_count_effective"] = (
            pd.to_numeric(df["treatments_count_effective"], errors="coerce")
              .fillna(0).astype(int)
        )

    df = df.loc[:, ~df.columns.duplicated()]
    return df

with st.form("filters_form", clear_on_submit=False):
    today = date.today()
    c1,c2,c3,c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=120))
    with c2: d2 = st.date_input("To",   value=today + timedelta(days=14))
    with c3: created_by = st.text_input("Created by (plan/instance)", value="")
    with c4: qtxt = st.text_input("Search (code/cross/clutch/genotype/strain)", value="")
    r1, r2 = st.columns([1,3])
    with r1: ignore_dates = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", use_container_width=True)

clutches = _load_clutches(d1, d2, created_by, qtxt, ignore_dates)
st.caption(f"{len(clutches)} clutch(es)")

if clutches.empty:
    st.info("No clutches found with the current filters."); st.stop()

view_cols = [
    "clutch_code","clutch_birthday","cross_name_pretty",
    "clutch_name","clutch_genotype_pretty","clutch_strain_pretty",
    "treatments_count_effective","treatments_pretty_effective",
    "genotype_treatment_rollup_effective",
    "created_by_instance","created_at_instance",
]
have = [c for c in view_cols if c in clutches.columns]
dfv = clutches[have].copy()
dfv = dfv.loc[:, ~dfv.columns.duplicated()]
if "treatments_count_effective" in dfv.columns:
    dfv["treatments_count_effective"] = pd.to_numeric(dfv["treatments_count_effective"], errors="coerce").fillna(0).astype(int)

last_ci = st.session_state.get("last_ci")
dfv.insert(0, "✓ Select", False)
if last_ci and "clutch_code" in dfv.columns:
    dfv.loc[dfv["clutch_code"] == last_ci, "✓ Select"] = True

picker = st.data_editor(
    dfv, hide_index=True, use_container_width=True, num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True),
        "created_at_instance": st.column_config.DatetimeColumn("created_at_instance", disabled=True),
    },
    key="ci_only_picker_v1",
)

sel_mask = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False).astype(bool)
picked = dfv.loc[sel_mask, :].reset_index(drop=True)

if picked.empty:
    st.info("Select a clutch row (CI-… preferred) and attach treatments below.")
    st.stop()

row = picked.iloc[0]
ci_code = str(row.get("clutch_code","")).strip()
st.session_state["last_ci"] = ci_code

if not ci_code.startswith("CI-"):
    st.warning("This looks like a plan (CL-…). Schedule a run to get a CI-… row, then attach treatments.")
    st.stop()

cross_instance_id, clutch_instance_id = _resolve_ids_from_ci_or_cr(ci_code)
if not cross_instance_id:
    st.error("Could not resolve the run from this CI/CR code."); st.stop()
if not clutch_instance_id:
    st.error("Could not create/find the clutch_instance for this run."); st.stop()

st.subheader("Add treatments to this clutch instance")
tabs = st.tabs(["Plasmids","RNAs"])

def _load_plasmids(search: str) -> pd.DataFrame:
    if not _table_exists("public","plasmids"): return pd.DataFrame()
    with _eng().begin() as cx:
        return pd.read_sql(text("""
          select code, name, coalesce(nickname,'') as nickname, created_at, created_by
          from public.plasmids
          where (:q = '' OR coalesce(code,'') ilike :ql OR coalesce(name,'') ilike :ql OR coalesce(nickname,'') ilike :ql)
          order by coalesce(created_at, now()) desc
          limit 1000
        """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})

def _load_rnas(search: str) -> pd.DataFrame:
    if not _view_exists("public","v_rna_plasmids"): return pd.DataFrame()
    with _eng().begin() as cx:
        return pd.read_sql(text("""
          select code, name, coalesce(nickname,'') as nickname, created_at, created_by
          from public.v_rna_plasmids
          where (:q = '' OR coalesce(code,'') ilike :ql OR coalesce(name,'') ilike :ql OR coalesce(nickname,'') ilike :ql)
          order by coalesce(created_at, now()) desc
          limit 1000
        """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})

with tabs[0]:
    c1, c2 = st.columns([2,1])
    with c1: q_pl = st.text_input("Search plasmids (code / name / nickname / fluors / resistance)", value="")
    with c2: note_pl = st.text_input("Note for selected plasmids", value="")
    df_pl = _load_plasmids(q_pl)
    st.caption(f"{len(df_pl)} plasmid(s)")
    if df_pl.empty:
        picked_pl = pd.DataFrame()
    else:
        df_pl = df_pl.copy(); df_pl.insert(0, "✓ Select", False)
        eg_pl = st.data_editor(
            df_pl, hide_index=True, use_container_width=True, num_rows="fixed",
            column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
            key="plasmids_editor_ci_v1",
        )
        picked_pl = eg_pl[eg_pl["✓ Select"]].reset_index(drop=True)
        if not picked_pl.empty: picked_pl["source"] = "plasmids"

with tabs[1]:
    c1, c2 = st.columns([2,1])
    with c1: q_rna = st.text_input("Search RNAs (code / name / nickname)", value="")
    with c2: note_rna = st.text_input("Note for selected RNAs", value="")
    df_rna = _load_rnas(q_rna)
    st.caption(f"{len(df_rna)} RNA(s)")
    if df_rna.empty:
        picked_rna = pd.DataFrame()
    else:
        df_rna = df_rna.copy(); df_rna.insert(0, "✓ Select", False)
        eg_rna = st.data_editor(
            df_rna, hide_index=True, use_container_width=True, num_rows="fixed",
            column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
            key="rnas_editor_ci_v1",
        )
        picked_rna = eg_rna[eg_rna["✓ Select"]].reset_index(drop=True)
        if not picked_rna.empty: picked_rna["source"] = "v_rna_plasmids"

st.subheader("Save")
creator = os.environ.get("USER") or os.environ.get("USERNAME") or (getattr(user, "email", "") or "system")

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("➕ Attach selected plasmids", use_container_width=True, key="attach_plasmids_ci_v1"):
        items = picked_pl.to_dict("records") if 'picked_pl' in locals() and not picked_pl.empty else []
        n, errs = _insert_instance_treatments(clutch_instance_id, creator, items, note_pl)
        st.session_state["treatments_result"] = {"instance": n, "errs": errs}
with col2:
    if st.button("➕ Attach selected RNAs", use_container_width=True, key="attach_rnas_ci_v1"):
        items = picked_rna.to_dict("records") if 'picked_rna' in locals() and not picked_rna.empty else []
        n, errs = _insert_instance_treatments(clutch_instance_id, creator, items, note_rna)
        st.session_state["treatments_result"] = {"instance": n, "errs": errs}
with col3:
    if st.button("↻ Refresh", use_container_width=True, key="refresh_ci_v1"):
        st.session_state["__manual_refresh__"] = True

_tmsg = st.session_state.pop("treatments_result", None)
if _tmsg:
    if _tmsg.get("instance"):
        st.success(f"Attached {_tmsg['instance']} treatment(s).")
    if _tmsg.get("errs"):
        st.warning("Some items were skipped:\n- " + "\n- ".join(_tmsg["errs"]))

st.subheader("Updated run summary")
run_df = _load_run_overview(ci_code)
if run_df.empty:
    st.info("No overview row found for this run.")
else:
    cnt = int(run_df.get("treatments_count_effective", pd.Series([0])).iloc[0])
    pretty = str(run_df.get("treatments_pretty_effective", pd.Series([""])).iloc[0] or "")
    gt_roll = str(run_df.get("genotype_treatment_rollup_effective", pd.Series([""])).iloc[0] or "")
    st.caption(f"Effective treatments: {cnt} — {pretty}")
    if gt_roll:
        st.caption(f"Genotype + treatments: {gt_roll}")
    st.dataframe(run_df, use_container_width=True, hide_index=True)

st.subheader("Treatments on this run")
treat_df = _load_instance_treatments(clutch_instance_id)
if not treat_df.empty:
    _norm = lambda s: (s or "").strip().lower()
    dedup = (
        treat_df.assign(
            _mt=treat_df["material_type"].map(_norm),
            _mc=treat_df["material_code"].map(_norm),
        )
        .drop_duplicates(["_mt", "_mc"])
        .sort_values("created_at", ascending=False)
    )
    live_count = int(dedup.shape[0])
    live_pretty = " + ".join(dedup["material_code"].tolist())
    st.info(f"Live treatments on this run → count: {live_count} | {live_pretty}")
if treat_df.empty:
    st.info("No treatments attached yet.")
else:
    st.dataframe(treat_df, use_container_width=True, hide_index=True)