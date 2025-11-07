# =============================================================================
# 🧪 Add treatments to clutch — current design (v_clutch_instances + join_clutch_treatments)
#        • Plasmids + RNAs (RNAs from v_rna_plasmids if present, else plasmids.supports_invitro_rna)
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
from typing import List, Dict

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy import text as _sql

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

# ── Config (current design) ──────────────────────────────────────────────────
CLUTCHES_VIEW   = "public.v_clutch_instances"          # enriched, contract view
TREATMENTS_LINK = "public.join_clutch_treatments"      # canonical link table

REQUIRED_COLS = [
    "clutch_code", "clutch_birthday", "cross_name_pretty",
    "clutch_name", "clutch_genotype_pretty", "clutch_strain_pretty",
    "treatments_count_effective", "treatments_pretty_effective",
    "genotype_treatment_rollup_effective", "created_by_instance", "created_at_instance",
]

# ── Helpers / guards ─────────────────────────────────────────────────────────
def _assert_view_contract() -> None:
    sch, name = CLUTCHES_VIEW.split(".", 1)
    with _eng().begin() as cx:
        got = pd.read_sql(text("""
            select column_name
            from information_schema.columns
            where table_schema=:s and table_name=:n
        """), cx, params={"s": sch, "n": name})["column_name"].tolist()
    missing = [c for c in REQUIRED_COLS if c not in got]
    if missing:
        st.error(f"{CLUTCHES_VIEW} missing columns: " + ", ".join(missing)); st.stop()

def _assert_table(schema: str, name: str) -> None:
    with _eng().begin() as cx:
        ok = pd.read_sql(text("""
            select 1 from information_schema.tables
            where table_schema=:s and table_name=:n limit 1
        """), cx, params={"s": schema, "n": name}).shape[0] > 0
    if not ok:
        st.error(f"Required table {schema}.{name} not found."); st.stop()

def _view_exists(schema: str, name: str) -> bool:
    q = _sql("""
      SELECT 1 FROM information_schema.views WHERE table_schema=:s AND table_name=:n
      UNION ALL
      SELECT 1 FROM pg_catalog.pg_matviews WHERE schemaname=:s AND matviewname=:n
      LIMIT 1
    """)
    with _eng().begin() as cx:
        return cx.execute(q, {"s": schema, "n": name}).first() is not None

_assert_view_contract()
_assert_table("public","clutch_instances")
_assert_table("public","crosses")
_assert_table("public","join_clutch_treatments")

# ── Small utilities ──────────────────────────────────────────────────────────
def _treatments_first_rollup(treatments: str | None, genotype: str | None) -> str:
    t = (treatments or '').strip()
    g = (genotype or '').strip()
    if t and g: return f"{t} > {g}"
    return t or g

# ── Load clutches strictly from v_clutch_instances ───────────────────────────
def _load_clutches(d_from, d_to, created_by: str, q: str, most_recent: bool) -> pd.DataFrame:
    where, params = [], {}
    if not most_recent:
        where.append("v.created_at_instance::date between :d1 and :d2")
        params.update({"d1": d_from, "d2": d_to})
    if created_by.strip():
        where.append("coalesce(v.created_by_instance,'') ilike :by")
        params["by"] = f"%{created_by.strip()}%"
    if q.strip():
        params["q"] = f"%{q.strip()}%"
        where.append("""
        (
            v.clutch_code                ILIKE :q OR
            v.cross_name_pretty          ILIKE :q OR
            v.clutch_name                ILIKE :q OR
            v.clutch_genotype_pretty     ILIKE :q OR
            v.clutch_strain_pretty       ILIKE :q OR
            -- legacy rollup fields (keep for back-compat)
            v.treatments_pretty_effective ILIKE :q OR
            v.genotype_treatment_rollup_effective ILIKE :q OR
            -- new systematic fields
            COALESCE(v.clutch_treatments_codes,'')   ILIKE :q OR
            COALESCE(v.clutch_treatments_names,'')   ILIKE :q OR
            COALESCE(v.clutch_treatments_fusions,'') ILIKE :q OR
            COALESCE(v.clutch_genotype_fusions,'')   ILIKE :q OR
            COALESCE(v.clutch_lineage_pretty,'')     ILIKE :q OR
            COALESCE(v.clutch_lineage_fusions_pretty,'') ILIKE :q OR
            COALESCE(v.clutch_lineage_full_fusions_pretty,'') ILIKE :q
        )
        """)
    where_sql = ("where " + " AND ".join(where)) if where else ""

    sql = text(f"""
      select
        v.clutch_code,
        v.clutch_birthday,
        v.cross_name_pretty,
        v.clutch_name                            as view_clutch_name,
        v.clutch_genotype_pretty                 as view_genotype,
        v.clutch_strain_pretty,
        v.treatments_count_effective,
        v.treatments_pretty_effective,
        v.genotype_treatment_rollup_effective    as view_rollup,
        -- new lineage preview (codes)
        v.clutch_lineage_pretty                  as lineage_pretty,
        v.created_by_instance,
        v.created_at_instance
      from {CLUTCHES_VIEW} v
      {where_sql}
      order by v.created_at_instance desc nulls last, v.clutch_code
      limit 1000
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    df["treatments_count_effective"] = pd.to_numeric(df["treatments_count_effective"], errors="coerce").fillna(0).astype(int)
    df["rollup_effective"] = df["view_rollup"]
    return df.loc[:, ~df.columns.duplicated()]

# ── Resolve clutch code → IDs ────────────────────────────────────────────────
def _resolve_ids_from_ci(code_in: str):
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

# ── Treatments I/O (join_clutch_treatments only) ─────────────────────────────
def _load_instance_treatments(clutch_instance_id: str) -> pd.DataFrame:
    with _eng().begin() as cx:
        sql = text(f"""
          select
            jct.created_at,
            jct.treatment_type  as material_type,
            jct.treatment_code  as material_code,
            coalesce(jct.treatment_name, jct.treatment_code) as material_name,
            jct.notes,
            jct.created_by
          from {TREATMENTS_LINK} jct
          where jct.clutch_instance_id = cast(:cid as uuid)
          order by jct.created_at desc nulls last
        """)
        return pd.read_sql(sql, cx, params={"cid": clutch_instance_id})

def _insert_instance_treatments(clutch_instance_id: str, created_by: str, items: List[Dict], note: str):
    inserted, errs = 0, []
    with _eng().begin() as cx:
        for it in items:
            code = str(it.get("code") or it.get("id") or "").strip()
            name = str(it.get("name") or "").strip()
            if not code:
                errs.append(f"<empty-code> → skipped")
                continue
            try:
                kind = (
                    "plasmid" if it.get("source") == "plasmids"
                    else "rna" if it.get("source") == "v_rna_plasmids"
                    else (it.get("treatment_type") or "generic")
                )
                cx.execute(
                    text(f"""
                        insert into {TREATMENTS_LINK}
                          (clutch_instance_id, treatment_type, treatment_code, treatment_name, notes, created_by)
                        values
                          (cast(:iid as uuid), :kind, :code, :name, :notes, :who)
                        on conflict (clutch_instance_id, treatment_type_norm, treatment_code_norm)
                        do nothing
                    """),
                    {
                        "iid": clutch_instance_id,
                        "kind": kind,
                        "code": code,
                        "name": name or code,
                        "notes": note or "",
                        "who": created_by or "",
                    }
                )
                inserted += 1
            except Exception as e:
                errs.append(f"{code} → {e}")
    return inserted, errs

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

dfv = clutches[[
    "clutch_code",
    "clutch_birthday",
    "cross_name_pretty",
    "view_clutch_name",
    "view_genotype",
    "clutch_strain_pretty",
    "treatments_count_effective",
    "treatments_pretty_effective",
    "rollup_effective",
    "lineage_pretty",
    "created_by_instance",
    "created_at_instance",
]].copy()

dfv.insert(0, "✓ Select", False)
last_ci = st.session_state.get("last_ci")
if last_ci:
    dfv.loc[dfv["clutch_code"] == last_ci, "✓ Select"] = True

picker = st.data_editor(
    dfv,
    hide_index=True,
    width="stretch",
    num_rows="fixed",
    column_config={
        "✓ Select":                  st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday":           st.column_config.DateColumn("clutch_birthday", disabled=True, format="YYYY-MM-DD"),
        "created_at_instance":       st.column_config.DatetimeColumn("created_at_instance", disabled=True),
        "view_genotype":             st.column_config.TextColumn("clutch_genotype_pretty", disabled=True),
        "rollup_effective":          st.column_config.TextColumn("Treatments > genotype (legacy)", disabled=True),
        "lineage_pretty":            st.column_config.TextColumn("lineage (codes)", disabled=True),
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
selected_clutch_code = ci_code  # used in summary query below

cross_instance_id, clutch_instance_id = _resolve_ids_from_ci(ci_code)
if not cross_instance_id:
    st.error("Could not resolve the run from this CI code."); st.stop()
if not clutch_instance_id:
    st.error("Could not create/find the clutch_instance for this run."); st.stop()

# ── Catalog loaders ─────────────────────────────────────────────────────────
def _load_plasmids(search: str) -> pd.DataFrame:
    with _eng().begin() as cx:
        return pd.read_sql(text("""
          select code, name, coalesce(nickname,'') as nickname, created_at, created_by
          from public.plasmids
          where (:q = '' OR coalesce(code,'') ilike :ql OR coalesce(name,'') ilike :ql OR coalesce(nickname,'') ilike :ql)
          order by coalesce(created_at, now()) desc
          limit 1000
        """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})

_HAS_V_RNA = _view_exists("public", "v_rna_plasmids")
def _load_rnas(search: str) -> pd.DataFrame:
    with _eng().begin() as cx:
        if _HAS_V_RNA:
            return pd.read_sql(text("""
              select code, name, coalesce(nickname,'') as nickname, created_at, created_by
              from public.v_rna_plasmids
              where (:q = '' OR coalesce(code,'') ilike :ql OR coalesce(name,'') ilike :ql OR coalesce(nickname,'') ilike :ql)
              order by coalesce(created_at, now()) desc
              limit 1000
            """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})
        # fallback: plasmids that explicitly support in-vitro RNA
        return pd.read_sql(text("""
          select code, name, coalesce(nickname,'') as nickname, created_at, created_by
          from public.plasmids
          where (supports_invitro_rna is true)
            and (:q = '' OR coalesce(code,'') ilike :ql OR coalesce(name,'') ilike :ql OR coalesce(nickname,'') ilike :ql)
          order by coalesce(created_at, now()) desc
          limit 1000
        """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})

# ── Add treatments UI ────────────────────────────────────────────────────────
st.subheader("Add treatments to this clutch instance")
tabs = st.tabs(["Plasmids", "RNAs"])

# Plasmids
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
        if not picked_pl.empty:
            picked_pl = picked_pl.assign(
                treatment_type="plasmid",
                code=picked_pl["code"].astype(str),
                name=picked_pl["name"].astype(str),
            )

# RNAs
with tabs[1]:
    c1, c2 = st.columns([2,1])
    with c1: q_rna = st.text_input("Search RNAs (code / name / nickname)", value="")
    with c2: note_rna = st.text_input("Note for selected RNAs", value="")
    df_rna = _load_rnas(q_rna)
    src = "v_rna_plasmids" if _HAS_V_RNA else "plasmids.supports_invitro_rna"
    st.caption(f"{len(df_rna)} RNA(s) • source: {src}")
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
        if not picked_rna.empty:
            picked_rna = picked_rna.assign(
                treatment_type="rna",
                code=picked_rna["code"].astype(str),
                name=picked_rna["name"].astype(str),
            )

# ── Save actions ─────────────────────────────────────────────────────────────
st.subheader("Save")
creator = os.environ.get("USER") or os.environ.get("USERNAME") or (getattr(user, "email", "") or "system")

def _collect_items(df_sel: pd.DataFrame, ttype: str) -> List[Dict]:
    items: List[Dict] = []
    if df_sel is not None and not df_sel.empty:
        for _, r in df_sel.iterrows():
            items.append({
                "treatment_type": ttype,
                "code": str(r.get("code") or ""),
                "name": str(r.get("name") or ""),
            })
    return items

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("➕ Attach selected plasmids", width="stretch", key="attach_plasmids_ci_v1"):
        items = _collect_items(locals().get("picked_pl", pd.DataFrame()), "plasmid")
        n, errs = _insert_instance_treatments(clutch_instance_id, creator, items, locals().get("note_pl",""))
        st.session_state["treatments_result"] = {"instance": n, "errs": errs}
with col2:
    if st.button("➕ Attach selected RNAs", width="stretch", key="attach_rnas_ci_v1"):
        items = _collect_items(locals().get("picked_rna", pd.DataFrame()), "rna")
        n, errs = _insert_instance_treatments(clutch_instance_id, creator, items, locals().get("note_rna",""))
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

# ── Updated run summary ──────────────────────────────────────────────────────
st.subheader("Updated run summary")
# --- Updated run summary (uses new pretty fields from v_clutch_instances) ---
if hasattr(st, "segmented_control"):
    SHOW_TREATMENTS_AS = st.segmented_control(
        "Treatments label", options=["codes","names","fusions"], default="codes", key="tx_label_mode"
    )
else:
    SHOW_TREATMENTS_AS = st.selectbox(
        "Treatments label", options=["codes","names","fusions"], index=0, key="tx_label_mode"
    )

summary_sql = text("""
    SELECT
      v.clutch_code,
      v.clutch_birthday,
      v.cross_name_pretty,
      v.clutch_genotype_pretty,
      v.clutch_genotype_fusions,
      v.clutch_treatments_codes,
      v.clutch_treatments_names,
      v.clutch_treatments_fusions,
      v.clutch_lineage_pretty,
      v.clutch_lineage_fusions_pretty,
      v.clutch_lineage_full_fusions_pretty,
      v.treatments_count_effective
    FROM public.v_clutch_instances v
    WHERE v.clutch_code = :c
    LIMIT 1
""")

with _eng().begin() as cx:
    srow = pd.read_sql(summary_sql, cx, params={"c": selected_clutch_code})

if srow.empty:
    st.info("No summary found for this clutch.")
else:
    row = srow.iloc[0]

    if SHOW_TREATMENTS_AS == "codes":
        lineage = row.get("clutch_lineage_pretty")
        tx_label = row.get("clutch_treatments_codes")
    elif SHOW_TREATMENTS_AS == "names":
        tx_names = (row.get("clutch_treatments_names") or "").strip()
        lineage = (tx_names + " > " if tx_names else "") + (row.get("clutch_genotype_pretty") or "")
        tx_label = tx_names
    else:
        lineage = row.get("clutch_lineage_full_fusions_pretty")
        tx_label = row.get("clutch_treatments_fusions")

    show = pd.DataFrame([{
        "clutch_code": row.get("clutch_code"),
        "clutch_birthday": row.get("clutch_birthday"),
        "cross_name_pretty": row.get("cross_name_pretty"),
        "genotype (codes)": row.get("clutch_genotype_pretty"),
        "genotype (fusions)": row.get("clutch_genotype_fusions"),
        "treatments": tx_label,
        "lineage": lineage,
        "treatments_count_effective": int(row.get("treatments_count_effective") or 0),
    }])
    st.dataframe(show, hide_index=True, use_container_width=True)

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