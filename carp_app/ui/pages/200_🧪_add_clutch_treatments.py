# carp_app/ui/pages/200_🧪_add_clutch_treatments.py
# =============================================================================
# 🧪 Add treatments to clutch — v_clutch_instances + treated_clutches + join_clutch_treatments
#    • Plasmids + RNAs + Dyes
#    • RNAs: v_rna_plasmids if present, else plasmids.supports_invitro_rna  → saved as RNA(<code>)
#    • Single "Attach selected treatments" button
#    • On every save: auto-create a new treated-clutch group "T(<clutch_code>)-n" and attach all items to it
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
from sqlalchemy.engine import Engine

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine

# ── Auth / page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="🧪 Add treatments to clutch", page_icon="🧪", layout="wide")
st.title("🧪 Add treatments to clutch")

# ── Engine ───────────────────────────────────────────────────────────────────
_ENGINE: Engine | None = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        url = os.getenv("DB_URL")
        if not url:
            st.error("DB_URL not set"); st.stop()
        _ENGINE = get_engine()
    return _ENGINE

# ── Config ───────────────────────────────────────────────────────────────────
CLUTCHES_VIEW      = "public.v_clutch_instances"      # enriched contract view
TREATED_CLUTCHES   = "public.treated_clutches"
TREATMENTS_LINK    = "public.join_clutch_treatments"

REQUIRED_COLS = [
    "clutch_code","clutch_birthday","cross_name_pretty",
    "clutch_genotype_pretty","treatments_count_effective",
    "clutch_treatments_codes","treatment_genotype",
    "created_by_instance","created_at_instance",
]

# ── Guards ───────────────────────────────────────────────────────────────────
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
_assert_table("public","treated_clutches")
_assert_table("public","join_clutch_treatments")

# ── Data loaders / utils ─────────────────────────────────────────────────────
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
            v.clutch_code ILIKE :q OR
            v.cross_name_pretty ILIKE :q OR
            v.clutch_genotype_pretty ILIKE :q OR
            COALESCE(v.clutch_treatments_codes,'') ILIKE :q OR
            COALESCE(v.treatment_genotype,'') ILIKE :q
        )
        """)
    where_sql = ("where " + " AND ".join(where)) if where else ""
    sql = text(f"""
      select
        v.clutch_code, v.clutch_birthday, v.cross_name_pretty,
        v.clutch_genotype_pretty, v.treatments_count_effective,
        v.clutch_treatments_codes, v.treatment_genotype,
        v.created_by_instance, v.created_at_instance
      from {CLUTCHES_VIEW} v
      {where_sql}
      order by v.created_at_instance desc nulls last, v.clutch_code
      limit 1000
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    df["treatments_count_effective"] = pd.to_numeric(df["treatments_count_effective"], errors="coerce").fillna(0).astype(int)
    return df.loc[:, ~df.columns.duplicated()]

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

# Auto-create a treated-clutch group on every save: "T(<clutch_code>)-n"
def _create_autogroup(ci_id: str, clutch_code: str, who: str) -> dict:
    with _eng().begin() as cx:
        max_n = pd.read_sql(text("""
          SELECT COALESCE(MAX( (regexp_match(treated_clutch_code, '\-(\d+)$'))[1]::int ), 0) AS n
          FROM public.treated_clutches
          WHERE clutch_instance_id = cast(:cid as uuid)
            AND treated_clutch_code LIKE :prefix || '%'
        """), cx, params={"cid": ci_id, "prefix": f"T({clutch_code})-"}).iloc[0]["n"]
        code = f"T({clutch_code})-{int(max_n)+1}"
        m = cx.execute(
            text(f"""
              INSERT INTO {TREATED_CLUTCHES} (clutch_instance_id, treated_clutch_code, created_by)
              VALUES (cast(:cid as uuid), :code, :by)
              RETURNING id::text AS treated_clutch_id, treated_clutch_code
            """),
            {"cid": ci_id, "code": code, "by": who}
        ).mappings().first()
    return dict(m)

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
        return pd.read_sql(text("""
          select code, name, coalesce(nickname,'') as nickname, created_at, created_by
          from public.plasmids
          where (supports_invitro_rna is true)
            and (:q = '' OR coalesce(code,'') ilike :ql OR coalesce(name,'') ilike :ql OR coalesce(nickname,'') ilike :ql)
          order by coalesce(created_at, now()) desc
          limit 1000
        """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})

def _load_dyes(search: str) -> pd.DataFrame:
    with _eng().begin() as cx:
        return pd.read_sql(text("""
          select dye_code as code,
                 dye_name as name,
                 coalesce(localization,'') as localization,
                 excitation_nm, emission_nm
          from public.dyes
          where (:q = '' OR
                 coalesce(dye_code,'') ilike :ql OR
                 coalesce(dye_name,'') ilike :ql OR
                 coalesce(localization,'') ilike :ql)
          order by coalesce(dye_name, dye_code)
          limit 1000
        """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})

# Treatments I/O
def _load_instance_treatments(clutch_instance_id: str) -> pd.DataFrame:
    with _eng().begin() as cx:
        sql = text(f"""
          select
            jct.created_at,
            jct.treatment_type  as material_type,
            jct.treatment_code  as material_code,
            coalesce(jct.treatment_name, jct.treatment_code) as material_name,
            jct.notes,
            jct.created_by,
            tc.treated_clutch_code,
            coalesce(tc.label,'') as group_label
          from {TREATMENTS_LINK} jct
          left join {TREATED_CLUTCHES} tc on tc.id = jct.treated_clutch_id
          where jct.clutch_instance_id = cast(:cid as uuid)
          order by jct.created_at desc nulls last
        """)
        return pd.read_sql(sql, cx, params={"cid": clutch_instance_id})

def _insert_instance_treatments(clutch_instance_id: str, treated_clutch_id: str, created_by: str, items: List[Dict]):
    inserted, errs = 0, []
    with _eng().begin() as cx:
        for it in items:
            code = str(it.get("code") or "").strip()
            name = str(it.get("name") or "").strip()
            kind = str(it.get("treatment_type") or "generic").strip()
            note = str(it.get("note") or it.get("_note") or "").strip()
            if not code:
                errs.append("<empty-code> → skipped"); continue
            try:
                cx.execute(
                    text(f"""
                        insert into {TREATMENTS_LINK}
                          (clutch_instance_id, treated_clutch_id, treatment_type, treatment_code, treatment_name, notes, created_by)
                        values
                          (cast(:iid as uuid), cast(:gid as uuid), :kind, :code, :name, :notes, :who)
                        on conflict (treated_clutch_id, treatment_type_norm, treatment_code_norm)
                        do nothing
                    """),
                    {
                        "iid": clutch_instance_id,
                        "gid": treated_clutch_id,
                        "kind": kind,
                        "code": code,
                        "name": name or code,
                        "notes": note,
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
    with c4: qtxt = st.text_input("Search (code/cross/clutch/genotype)", value="")
    r1, r2 = st.columns([1,3])
    with r1: ignore_dates = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", width="stretch")

clutches = _load_clutches(d1, d2, created_by, qtxt, ignore_dates)
st.caption(f"{len(clutches)} clutch(es)")

if clutches.empty:
    st.info("No clutches found with the current filters."); st.stop()

dfv = clutches[[
    "clutch_code","clutch_birthday","cross_name_pretty",
    "clutch_genotype_pretty","treatments_count_effective",
    "clutch_treatments_codes","treatment_genotype",
    "created_by_instance","created_at_instance",
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
        "✓ Select":            st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday":     st.column_config.DateColumn("clutch_birthday", disabled=True, format="YYYY-MM-DD"),
        "created_at_instance": st.column_config.DatetimeColumn("created_at_instance", disabled=True),
        "treatments_count_effective": st.column_config.NumberColumn("treatments_count_effective", format="%d"),
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
selected_clutch_code = ci_code

cross_instance_id, clutch_instance_id = _resolve_ids_from_ci(ci_code)
if not cross_instance_id:
    st.error("Could not resolve the run from this CI code."); st.stop()
if not clutch_instance_id:
    st.error("Could not create/find the clutch_instance for this run."); st.stop()

creator = os.environ.get("USER") or os.environ.get("USERNAME") or (getattr(user, "email", "") or "system")

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
        return pd.read_sql(text("""
          select code, name, coalesce(nickname,'') as nickname, created_at, created_by
          from public.plasmids
          where (supports_invitro_rna is true)
            and (:q = '' OR coalesce(code,'') ilike :ql OR coalesce(name,'') ilike :ql OR coalesce(nickname,'') ilike :ql)
          order by coalesce(created_at, now()) desc
          limit 1000
        """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})

def _load_dyes(search: str) -> pd.DataFrame:
    with _eng().begin() as cx:
        return pd.read_sql(text("""
          select dye_code as code,
                 dye_name as name,
                 coalesce(localization,'') as localization,
                 excitation_nm, emission_nm
          from public.dyes
          where (:q = '' OR
                 coalesce(dye_code,'') ilike :ql OR
                 coalesce(dye_name,'') ilike :ql OR
                 coalesce(localization,'') ilike :ql)
          order by coalesce(dye_name, dye_code)
          limit 1000
        """), cx, params={"q": search or "", "ql": f"%{search or ''}%"})

# ── Add treatments UI ────────────────────────────────────────────────────────
st.subheader("Add treatments to this clutch instance")
tabs = st.tabs(["Plasmids", "RNAs", "Dyes"])

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
                _note=note_pl
            )

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
                code="RNA(" + picked_rna["code"].astype(str) + ")",   # canonical RNA(code)
                name=picked_rna["name"].astype(str),
                _note=note_rna
            )

with tabs[2]:
    c1, c2 = st.columns([2,1])
    with c1: q_dye = st.text_input("Search dyes (code / name / localization)", value="")
    with c2: note_dye = st.text_input("Note for selected dyes", value="")
    df_dye = _load_dyes(q_dye)
    st.caption(f"{len(df_dye)} dye(s)")
    if df_dye.empty:
        picked_dye = pd.DataFrame()
    else:
        df_dye = df_dye.copy(); df_dye.insert(0, "✓ Select", False)
        eg_dye = st.data_editor(
            df_dye, hide_index=True, width="stretch", num_rows="fixed",
            column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
            key="dyes_editor_ci_v1",
        )
        picked_dye = eg_dye[eg_dye["✓ Select"]].reset_index(drop=True)
        if not picked_dye.empty:
            picked_dye = picked_dye.assign(
                treatment_type="dye",
                code=picked_dye["code"].astype(str),
                name=picked_dye["name"].astype(str),
                _note=note_dye
            )

# ── Save actions (single button) — auto-group per click ----------------------
st.subheader("Save")
note_all = st.text_input("Note for selected treatments (optional)", value="")

def _collect_items(df_sel: pd.DataFrame) -> List[Dict]:
    items: List[Dict] = []
    if df_sel is not None and not df_sel.empty:
        for _, r in df_sel.iterrows():
            items.append({
                "treatment_type": str(r.get("treatment_type") or ""),
                "code":           str(r.get("code") or ""),
                "name":           str(r.get("name") or ""),
                "note":           str(r.get("_note") or note_all or ""),
            })
    return items

if st.button("➕ Attach selected treatments (new group)", width="stretch", key="attach_all_ci_v1"):
    items: List[Dict] = []
    items += _collect_items(locals().get("picked_pl",  pd.DataFrame()))
    items += _collect_items(locals().get("picked_rna", pd.DataFrame()))
    items += _collect_items(locals().get("picked_dye", pd.DataFrame()))

    if not items:
        st.warning("No treatments selected."); st.stop()

    # Create the new group now (T(<clutch_code>)-n)
    creator = os.environ.get("USER") or os.environ.get("USERNAME") or (getattr(user, "email", "") or "system")
    grp = _create_autogroup(clutch_instance_id, ci_code, creator)
    n, errs = _insert_instance_treatments(clutch_instance_id, grp["treated_clutch_id"], creator, items)
    st.session_state["treatments_result"] = {"instance": n, "errs": errs, "group_code": grp["treated_clutch_code"]}

# ── Feedback ─────────────────────────────────────────────────────────────────
_tmsg = st.session_state.pop("treatments_result", None)
if _tmsg:
    msg = f"Attached {_tmsg.get('instance',0)} treatment(s)"
    if _tmsg.get("group_code"):
        msg += f" to group {_tmsg['group_code']}"
    st.success(msg + ".")
    if _tmsg.get("errs"):
        st.warning("Some items were skipped:\n- " + "\n- ".join(_tmsg["errs"]))

# ── Updated run summary (per group) ──────────────────────────────────────────
st.subheader("Updated run summary (per group)")

grp_sql = text("""
    SELECT
      v.treated_clutch_code,
      v.group_created_at,
      v.treatments_count_group,
      v.treatments_codes_group,
      v.treatment_genotype_group
    FROM public.v_treated_clutches v
    WHERE v.clutch_code = :c
    ORDER BY v.group_created_at ASC, v.treated_clutch_code
""")
with _eng().begin() as cx:
    gdf = pd.read_sql(grp_sql, cx, params={"c": selected_clutch_code})

if gdf.empty:
    st.info("No treatment groups yet for this clutch.")
else:
    st.dataframe(
        gdf,
        hide_index=True,
        width="stretch",
        column_config={
            "treated_clutch_code":      st.column_config.TextColumn("treated_clutch_code", disabled=True),
            "group_created_at":         st.column_config.DatetimeColumn("created_at", disabled=True),
            "treatments_count_group":   st.column_config.NumberColumn("# tx", disabled=True, format="%d"),
            "treatments_codes_group":   st.column_config.TextColumn("treatments (codes)", disabled=True),
            "treatment_genotype_group": st.column_config.TextColumn("treatment > genotype", disabled=True),
        },
    )

# ── Treatments on this run ───────────────────────────────────────────────────
st.subheader("Treatments on this run")
treat_df = _load_instance_treatments(clutch_instance_id)

if treat_df.empty:
    st.info("No treatments attached yet.")
else:
    _norm = lambda s: (s or "").strip().lower()
    dedup = (
        treat_df.assign(
            _mt=treat_df["material_type"].map(_norm),
            _mc=treat_df["material_code"].map(_norm),
        )
        .drop_duplicates(["_mt", "_mc"])
        .sort_values("created_at", ascending=False)
    )
    live_count  = int(dedup.shape[0])
    live_pretty = " + ".join(dedup["material_code"].tolist())
    st.info(f"Live treatments on this run → count: {live_count} | {live_pretty}")

    # Reorder: treated_clutch_code first; omit group_label
    preferred = [
        "treated_clutch_code",
        "created_at", "material_type", "material_code", "material_name", "notes", "created_by"
    ]
    cols = [c for c in preferred if c in treat_df.columns] + \
           [c for c in treat_df.columns if c not in preferred and c != "group_label"]

    st.dataframe(treat_df[cols], width="stretch", hide_index=True)