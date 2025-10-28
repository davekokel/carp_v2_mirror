# =============================================================================
# 🧪 Add treatments to clutch — deterministic (strict v_clutch_instances)
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
from typing import List, Dict, Tuple, Optional, Any

import pandas as pd
import streamlit as st
from sqlalchemy import text

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine

# ── Auth / page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="🧪 Add treatments to clutch", page_icon="🧪", layout="wide")
st.title("🧪 Add treatments to clutch")

# ── Engine ───────────────────────────────────────────────────────────────────
_ENGINE = None
def _eng():
    global _ENGINE
    if _ENGINE: return _ENGINE
    url = os.getenv("DB_URL")
    if not url: st.error("DB_URL not set"); st.stop()
    _ENGINE = get_engine()
    return _ENGINE

# ── Deterministic contracts ──────────────────────────────────────────────────
CLUTCHES_VIEW = "public.v_clutch_instances_display"          # single source of truth
TREATMENTS_TABLE = "public.clutch_instance_treatments"

REQUIRED_VIEW_COLS = [
    # identity / display
    "clutch_code",
    "clutch_birthday",
    "cross_name_pretty",
    "clutch_name",
    "clutch_genotype_pretty",
    "clutch_strain_pretty",
    # rollups
    "treatments_count_effective",
    "treatments_pretty_effective",
    "genotype_treatment_rollup_effective",
    # audit / filter
    "created_by_instance",
    "created_at_instance",
]

def _assert_view_contract() -> None:
    with _eng().begin() as cx:
        got = pd.read_sql(text("""
            select column_name
            from information_schema.columns
            where table_schema='public' and table_name='v_clutch_instances'
            order by ordinal_position
        """), cx)["column_name"].tolist()
    missing = [c for c in REQUIRED_VIEW_COLS if c not in got]
    if missing:
        st.error(
            "Schema contract mismatch for public.v_clutch_instances.\n"
            "Missing columns: " + ", ".join(missing)
        ); st.stop()

def _assert_table_exists(schema: str, name: str) -> None:
    with _eng().begin() as cx:
        ok = pd.read_sql(text("""
            select 1
            from information_schema.tables
            where table_schema=:s and table_name=:t
            limit 1
        """), cx, params={"s": schema, "t": name}).shape[0] > 0
    if not ok:
        st.error(f"Required table {schema}.{name} not found."); st.stop()

_assert_view_contract()
_assert_table_exists("public", "clutch_instances")   # needed by resolver
_assert_table_exists("public", "cross_instances")    # needed by resolver
_assert_table_exists("public", "plasmids")           # for plasmid picker (optional fetch still handled)
# treatments table is asserted when we try to write, but we can also assert early:
_assert_table_exists("public", "clutch_instance_treatments")

# ── Utilities ────────────────────────────────────────────────────────────────
def _safe_date(v):
    try:
        return pd.to_datetime(v).date() if pd.notna(v) else None
    except Exception:
        return None

# ── Load clutches strictly from the view ─────────────────────────────────────
from sqlalchemy import text as _sql  # if not already imported

def _view_exists(schema: str, name: str) -> bool:
    """
    Return True if a normal or materialized view exists as schema.name.
    """
    q = _sql("""
      SELECT 1
      FROM information_schema.views
      WHERE table_schema = :schema AND table_name = :name
      UNION ALL
      SELECT 1
      FROM pg_catalog.pg_matviews
      WHERE schemaname = :schema AND matviewname = :name
      LIMIT 1
    """)
    with _eng().begin() as cx:   # 👈 changed from _get_engine()
        return cx.execute(q, {"schema": schema, "name": name}).first() is not None

def _load_clutches(d_from, d_to, created_by: str, q: str, most_recent: bool) -> pd.DataFrame:
    where, params = [], {}
    if not most_recent:
        where.append("created_at_instance::date between :d1 and :d2")
        params.update({"d1": d_from, "d2": d_to})
    if created_by.strip():
        where.append("coalesce(created_by_instance,'') ilike :by")
        params["by"] = f"%{created_by.strip()}%"
    if q.strip():
        params["q"] = f"%{q.strip()}%"
        where.append("""
          (
            clutch_code                      ilike :q OR
            cross_name_pretty                ilike :q OR
            clutch_name                      ilike :q OR
            clutch_genotype_pretty           ilike :q OR
            clutch_strain_pretty             ilike :q OR
            treatments_pretty_effective      ilike :q
          )
        """)
    where_sql = ("where " + " AND ".join(where)) if where else ""
    sql = text(f"""
      select
        clutch_code,
        clutch_birthday,
        cross_name_pretty,
        clutch_name,
        clutch_genotype_pretty,
        clutch_strain_pretty,
        treatments_count_effective,
        treatments_pretty_effective,
        genotype_treatment_rollup_effective,
        created_by_instance,
        created_at_instance
      from {CLUTCHES_VIEW}
      {where_sql}
      order by created_at_instance desc nulls last, clutch_code
      limit 1000
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    df["treatments_count_effective"] = pd.to_numeric(
        df["treatments_count_effective"], errors="coerce"
    ).fillna(0).astype(int)

    # De-dup any weirdness
    return df.loc[:, ~df.columns.duplicated()]

# ── Resolve CI/CR → IDs (deterministic rules; no heuristics beyond what’s here) ─
def _resolve_ids_from_ci_or_cr(code_in: str):
    code = (code_in or "").strip()
    if not code: return None, None
    with _eng().begin() as cx:
        row = pd.read_sql(text("""
            select ci.id::text as clutch_instance_id,
                   ci.cross_instance_id::text as cross_instance_id
            from public.clutch_instances ci
            where ci.clutch_instance_code = :code
            limit 1
        """), cx, params={"code": code})
    if row.empty: return None, None
    return row["cross_instance_id"].iloc[0], row["clutch_instance_id"].iloc[0]

# ── Treatments I/O ───────────────────────────────────────────────────────────
def _load_instance_treatments(clutch_instance_id: str) -> pd.DataFrame:
    with _eng().begin() as cx:
        sql = text("""
          select created_at, material_type, material_code, material_name, notes, created_by
          from public.clutch_instance_treatments
          where clutch_instance_id = cast(:cid as uuid)
          order by created_at desc nulls last
        """)
        return pd.read_sql(sql, cx, params={"cid": clutch_instance_id})

def _insert_instance_treatments(clutch_instance_id: str, created_by: str, items: List[Dict], note: str):
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

# ── Run overview (strictly from the clutch view) ─────────────────────────────
def _load_run_overview(ci_code: str) -> pd.DataFrame:
    with _eng().begin() as cx:
        df = pd.read_sql(text(f"""
            select *
            from {CLUTCHES_VIEW}
            where clutch_code = :cc
            order by created_at_instance desc nulls last
            limit 1
        """), cx, params={"cc": ci_code})

    if df.empty:
        return df

    # enforce the expected rollup cols (already required, but keep explicit)
    df["treatments_count_effective"] = pd.to_numeric(
        df["treatments_count_effective"], errors="coerce"
    ).fillna(0).astype(int)

    return df.loc[:, ~df.columns.duplicated()]

# ── Filters + picker ─────────────────────────────────────────────────────────
with st.form("filters_form", clear_on_submit=False):
    today = date.today()
    c1,c2,c3,c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=120))
    with c2: d2 = st.date_input("To",   value=today + timedelta(days=14))
    with c3: created_by = st.text_input("Created by (plan/instance)", value="")
    with c4: qtxt = st.text_input("Search (code/cross/clutch/genotype/strain)", value="")
    r1, r2 = st.columns([1,3])
    with r1: ignore_dates = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", width="stretch")

clutches = _load_clutches(d1, d2, created_by, qtxt, ignore_dates)
st.caption(f"{len(clutches)} clutch(es)")

if clutches.empty:
    st.info("No clutches found with the current filters."); st.stop()

view_cols = REQUIRED_VIEW_COLS.copy()
dfv = clutches[view_cols].copy()
dfv.insert(0, "✓ Select", False)

last_ci = st.session_state.get("last_ci")
if last_ci:
    dfv.loc[dfv["clutch_code"] == last_ci, "✓ Select"] = True

picker = st.data_editor(
    dfv, hide_index=True, width="stretch", num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True, format="YYYY-MM-DD"),
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

cross_instance_id, clutch_instance_id = _resolve_ids_from_ci_or_cr(ci_code)
if not cross_instance_id:
    st.error("Could not resolve the run from this CI/CR code."); st.stop()
if not clutch_instance_id:
    st.error("Could not create/find the clutch_instance for this run."); st.stop()

# ── Pickers for materials ────────────────────────────────────────────────────
def _load_plasmids(search: str) -> pd.DataFrame:
    with _eng().begin() as cx:
        return pd.read_sql(text("""
          select code, name, coalesce(nickname,'') as nickname, created_at, created_by
          from public.plasmids
          where (:q = '' OR coalesce(code,'') ilike :ql OR coalesce(name,'') ilike :ql OR coalesce(nickname,'') ilike :ql)
          order by coalesce(created_at, now()) desc
          limit 1000
        """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})

def _load_rnas(search: str) -> pd.DataFrame:
    view = "v_rna_plasmids"
    if not _view_exists("public", view):
        st.info("RNA library view not installed (public.v_rna_plasmids). Showing nothing.")
        return pd.DataFrame(columns=["code","name","nickname","created_at","created_by"])
    with _eng().begin() as cx:
        return pd.read_sql(text(f"""
          select code, name, coalesce(nickname,'') as nickname, created_at, created_by
          from public.{view}
          where (:q = '' OR coalesce(code,'') ilike :ql OR coalesce(name,'') ilike :ql OR coalesce(nickname,'') ilike :ql)
          order by coalesce(created_at, now()) desc
          limit 1000
        """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})

st.subheader("Add treatments to this clutch instance")
tabs = st.tabs(["Plasmids","RNAs"])

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
            df_pl, hide_index=True, width="stretch", num_rows="fixed",
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
            df_rna, hide_index=True, width="stretch", num_rows="fixed",
            column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
            key="rnas_editor_ci_v1",
        )
        picked_rna = eg_rna[eg_rna["✓ Select"]].reset_index(drop=True)
        if not picked_rna.empty: picked_rna["source"] = "v_rna_plasmids"

# ── Save actions ─────────────────────────────────────────────────────────────
st.subheader("Save")
creator = os.environ.get("USER") or os.environ.get("USERNAME") or (getattr(user, "email", "") or "system")

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("➕ Attach selected plasmids", width="stretch", key="attach_plasmids_ci_v1"):
        items = picked_pl.to_dict("records") if 'picked_pl' in locals() and not picked_pl.empty else []
        n, errs = _insert_instance_treatments(clutch_instance_id, creator, items, note_pl)
        st.session_state["treatments_result"] = {"instance": n, "errs": errs}
with col2:
    if st.button("➕ Attach selected RNAs", width="stretch", key="attach_rnas_ci_v1"):
        items = picked_rna.to_dict("records") if 'picked_rna' in locals() and not picked_rna.empty else []
        n, errs = _insert_instance_treatments(clutch_instance_id, creator, items, note_rna)
        st.session_state["treatments_result"] = {"instance": n, "errs": errs}
with col3:
    if st.button("↻ Refresh", width="stretch", key="refresh_ci_v1"):
        st.session_state["__manual_refresh__"] = True

# ── Feedback ─────────────────────────────────────────────────────────────────
_tmsg = st.session_state.pop("treatments_result", None)
if _tmsg:
    if _tmsg.get("instance"):
        st.success(f"Attached {_tmsg['instance']} treatment(s).")
    if _tmsg.get("errs"):
        st.warning("Some items were skipped:\n- " + "\n- ".join(_tmsg["errs"]))

# ── Updated run summary (from the same deterministic view) ───────────────────
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
    st.dataframe(run_df, width="stretch", hide_index=True)

# ── Treatments on this run ───────────────────────────────────────────────────
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
    st.dataframe(treat_df, width="stretch", hide_index=True)