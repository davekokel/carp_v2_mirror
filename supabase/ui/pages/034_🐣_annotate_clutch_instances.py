from __future__ import annotations
import os, sys, re, uuid
from pathlib import Path
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ── path bootstrap ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Annotate Clutch Instances", page_icon="🐣", layout="wide")
st.title("🐣 Annotate Clutch Instances")

# ── engine / env ────────────────────────────────────────────────────────────────
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = create_engine(DB_URL, future=True, pool_pre_ping=True)

# DB badge (host + role) and capture user string for stamping
from sqlalchemy import text as _text
user = ""
try:
    url = getattr(eng, "url", None)
    host = (getattr(url, "host", None) or os.getenv("PGHOST", "") or "(unknown)")
    with eng.begin() as cx:
        role = cx.execute(_text("select current_setting('role', true)")).scalar()
        who  = cx.execute(_text("select current_user")).scalar()
    user = who or ""
    st.caption(f"DB: {host} • role={role or 'default'} • user={user}")
except Exception:
    pass

# (Optional) stamp app user into server-side session key app.user
try:
    from supabase.ui.lib.app_ctx import stamp_app_user
    who_ui = getattr(st.experimental_user, "email", "") if hasattr(st, "experimental_user") else ""
    if who_ui:
        user = who_ui
    stamp_app_user(eng, user)
except Exception:
    pass

# Ensure target table exists
with eng.begin() as cx:
    exists_tbl = cx.execute(text("select to_regclass('public.clutch_instances')")).scalar()
if not exists_tbl:
    st.error("Table public.clutch_instances not found in this DB.")
    st.stop()

# Helper: build VALUES list of uuid literals safely
_UUID_RE = re.compile(r"^[0-9a-fA-F-]{32,40}$")
def uuid_values_clause(ids: list[str]) -> str:
    vals = []
    for s in ids or []:
        s = (s or "").strip()
        if _UUID_RE.match(s):
            vals.append(f"('{s}'::uuid)")
    return ", ".join(vals)

# ── conceptual clutches (no date filters) ───────────────────────────────────────
st.markdown("## 🔍 Clutches — Conceptual overview")
with eng.begin() as cx:
    concept_df = pd.read_sql(
        text("""
            select
              conceptual_cross_code as clutch_code,
              name                  as clutch_name,
              nickname              as clutch_nickname,
              mom_code, dad_code, mom_code_tank, dad_code_tank,
              created_at
            from public.v_cross_concepts_overview
            order by created_at desc nulls last, clutch_code
            limit 2000
        """),
        cx,
    )

# selection model for concepts
sel_key = "_concept_table"
if sel_key not in st.session_state:
    t = concept_df.copy()
    t.insert(0, "✓ Select", False)
    st.session_state[sel_key] = t
else:
    base = st.session_state[sel_key].set_index("clutch_code")
    now  = concept_df.set_index("clutch_code")
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
    base = base.loc[now.index]
    st.session_state[sel_key] = base.reset_index()

st.markdown("### Conceptual clutches")
present_cols = [
    "✓ Select","clutch_code","clutch_name","clutch_nickname",
    "mom_code","dad_code","mom_code_tank","dad_code_tank","created_at",
]
present = [c for c in present_cols if c in st.session_state[sel_key].columns]
edited_concepts = st.data_editor(
    st.session_state[sel_key][present],
    hide_index=True,
    use_container_width=True,
    column_order=present,
    column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
    key="ci_concept_editor",
)
# Persist ✓ back to session model
st.session_state[sel_key].loc[edited_concepts.index, "✓ Select"] = edited_concepts["✓ Select"]

# STRICT selection: require at least one ✓
tbl = st.session_state.get(sel_key)
selected_codes: list[str] = []
if isinstance(tbl, pd.DataFrame):
    selected_codes = tbl.loc[tbl["✓ Select"] == True, "clutch_code"].astype(str).tolist()
if not selected_codes:
    st.info("Tick one or more clutches above to show realized instances.")
    st.stop()

# ── realized instances for selected concepts (no date filters) ──────────────────
st.markdown("### Realized instances for selection")
with eng.begin() as _cx_dbg:
    _host = (getattr(getattr(eng, "url", None), "host", None) or os.getenv("PGHOST", ""))
    _runs_cnt = pd.read_sql(text("select count(*) as c from public.vw_cross_runs_overview"), _cx_dbg)["c"].iloc[0]
st.caption(f"DBG • host={_host} • runs_in_view={_runs_cnt}")
st.caption(f"selected concepts used: {selected_codes}")

with eng.begin() as cx:
    sel_mom_dad = pd.read_sql(
        text("""
            select conceptual_cross_code as clutch_code, mom_code, dad_code
            from public.v_cross_concepts_overview
            where conceptual_cross_code = any(:codes)
        """),
        cx, params={"codes": selected_codes}
    )
    runs = pd.read_sql(
        text("""
            select
              cross_instance_id,
              cross_run_code,
              cross_date::date as cross_date,
              mom_code, dad_code,
              mother_tank_label, father_tank_label
            from public.vw_cross_runs_overview
        """),
        cx
    )

if sel_mom_dad.empty or runs.empty:
    st.info("No realized clutch instances yet.")
    st.stop()

# join by mom+dad
det = sel_mom_dad.merge(runs, how="inner", on=["mom_code","dad_code"]).sort_values(["cross_date"], ascending=[False])

# aggregate from clutch_instances by cross_instance_id
with eng.begin() as cx:
    agg = pd.read_sql(
        text("""
            select
              cross_instance_id,
              max(annotated_at)::date as day_annotated,
              string_agg(
                trim(
                  concat_ws(' ',
                    case when coalesce(red_intensity,'')   <> '' then 'red='   || red_intensity   end,
                    case when coalesce(green_intensity,'') <> '' then 'green=' || green_intensity end,
                    case when coalesce(notes,'')           <> '' then 'note='  || notes          end
                  )
                ),
                ' | ' order by created_at
              ) as annotations_rollup
            from public.clutch_instances
            group by cross_instance_id
        """),
        cx
    )

if "cross_instance_id" in det.columns and not agg.empty:
    det = det.merge(agg, how="left", on="cross_instance_id")
else:
    det["day_annotated"] = pd.NaT
    det["annotations_rollup"] = ""

# Normalize strings
det["birthday"] = det["cross_date"]  # clutch instance birthday = run date
det["day_annotated"] = det["day_annotated"].astype("string")
det["annotations_rollup"] = det["annotations_rollup"].fillna("").astype("string")

# runs grid
cols = [
    "clutch_code","cross_run_code","birthday",
    "day_annotated","annotations_rollup",
    "mom_code","dad_code","mother_tank_label","father_tank_label"
]
present_det = [c for c in cols if c in det.columns]
grid = det[present_det + (["cross_instance_id"] if "cross_instance_id" in det.columns else [])].copy()
grid.insert(0, "✓ Add", False)
edited_runs = st.data_editor(
    grid,
    hide_index=True,
    use_container_width=True,
    column_order=["✓ Add"] + present_det,
    column_config={"✓ Add": st.column_config.CheckboxColumn("✓", default=False)},
    key="ci_runs_editor_min",
)

# --- Existing selections for the checked run(s) ---------------------------------
st.markdown("#### Existing selections for the checked run(s)")

# Use mom_code+dad_code pairs from the checked rows (text binds are safest)
checked_pairs = pd.DataFrame(columns=["mom_code","dad_code"])
if {"mom_code","dad_code"}.issubset(edited_runs.columns):
    checked_pairs = (
        edited_runs.loc[edited_runs["✓ Add"] == True, ["mom_code","dad_code"]]
        .dropna()
        .astype(str)
        .drop_duplicates()
    )

if checked_pairs.empty:
    st.info("Select a run in the table above to view its existing selections.")
else:
    # Build VALUES (:m0,:d0),(:m1,:d1),...
    vals = []
    params = {}
    for i, (m, d) in enumerate(checked_pairs.itertuples(index=False, name=None)):
        vals.append(f"(:m{i}, :d{i})")
        params[f"m{i}"] = m
        params[f"d{i}"] = d
    values_clause = ", ".join(vals)

    sql_checked = text(f"""
        with pairs(mom_code, dad_code) as (values {values_clause})
        select
          s.selection_id,
          s.cross_instance_id,
          s.selection_created_at,
          s.selection_annotated_at,
          s.red_intensity,
          s.green_intensity,
          s.notes,
          s.annotated_by,
          s.label
        from public.v_clutch_instance_selections s
        join public.vw_cross_runs_overview r
          on r.cross_instance_id = s.cross_instance_id
        join pairs p
          on p.mom_code = r.mom_code and p.dad_code = r.dad_code
        order by coalesce(s.selection_annotated_at, s.selection_created_at) desc,
                 s.selection_created_at desc
    """)

    with eng.begin() as cx:
        rows = cx.execute(sql_checked, params).mappings().all()
    sel_rows = pd.DataFrame(rows)

    # Attach run context for display (clutch_code / cross_run_code / birthday)
    run_meta = det[["cross_instance_id","clutch_code","cross_run_code","birthday"]].drop_duplicates()
    table_checked = sel_rows.merge(run_meta, how="left", on="cross_instance_id")

    for c in [
        "clutch_code","cross_run_code","birthday",
        "selection_created_at","selection_annotated_at",
        "red_intensity","green_intensity","notes","annotated_by","label","selection_id",
    ]:
        if c not in table_checked.columns:
            table_checked[c] = ""

    show_cols = [
        "clutch_code","cross_run_code","birthday",
        "selection_created_at","selection_annotated_at",
        "red_intensity","green_intensity","notes","annotated_by","label","selection_id",
    ]
    present = [c for c in show_cols if c in table_checked.columns]
    st.dataframe(table_checked[present], hide_index=True, use_container_width=True)

# ---- Quick annotate selected (one per run) -------------------------------------
st.markdown("#### Quick annotate selected")
c1, c2, c3 = st.columns([1,1,3])
with c1:
    red_txt = st.text_input("red", value="", placeholder="text")
with c2:
    green_txt = st.text_input("green", value="", placeholder="text")
with c3:
    note_txt = st.text_input("note", value="", placeholder="optional")

if st.button("Submit"):
    if not (red_txt.strip() or green_txt.strip() or note_txt.strip()):
        st.warning("Provide at least one of red/green/note before submitting.")
        st.stop()

    sel_rows_for_insert = edited_runs.loc[edited_runs["✓ Add"] == True]
    if sel_rows_for_insert.empty:
        st.warning("No runs selected.")
    else:
        saved = 0
        with eng.begin() as cx:
            for _, r in sel_rows_for_insert.iterrows():
                xid   = str(r.get("cross_instance_id") or "").strip()
                ccode = str(r.get("clutch_code") or "").strip()
                rcode = str(r.get("cross_run_code") or "").strip()
                if not xid:
                    continue

                base_label = " / ".join([s for s in (ccode, rcode) if s]) or "clutch"
                existing = cx.execute(text("""
                    select count(*) from public.clutch_instances
                    where cross_instance_id = :xid
                """), {"xid": xid}).scalar() or 0
                suffix = f" [{existing + 1}]" if existing > 0 else ""
                label  = base_label + suffix

                cx.execute(text("""
                    insert into public.clutch_instances (
                        cross_instance_id, label, created_at,
                        red_intensity, green_intensity, notes,
                        red_selected, green_selected,
                        annotated_by, annotated_at
                    )
                    values (
                        :xid, :label, now(),
                        nullif(:red,''), nullif(:green,''), nullif(:note,''),
                        case when nullif(:red,'')   is not null then true else false end,
                        case when nullif(:green,'') is not null then true else false end,
                        coalesce(current_setting('app.user', true), :fallback_user),
                        now()
                    )
                """), {
                    "xid": xid,
                    "label": label,
                    "red":   red_txt,
                    "green": green_txt,
                    "note":  note_txt,
                    "fallback_user": (user or "")
                })
                saved += 1

        st.success(f"Created {saved} clutch instance(s).")
        st.rerun()

# ── Selection instances (distinct) for runs of the selected concepts ------------
st.markdown("### Selection instances (distinct)")

# Use all mom/dad pairs from det (all runs tied to selected concepts)
if not {"mom_code","dad_code"}.issubset(det.columns):
    st.caption("View does not expose mom_code/dad_code; cannot list selections.")
else:
    all_pairs = det[["mom_code","dad_code"]].dropna().astype(str).drop_duplicates()
    if all_pairs.empty:
        st.info("No selection instances yet for the selected runs.")
    else:
        vals_all = []
        params_all = {}
        for i, (m, d) in enumerate(all_pairs.itertuples(index=False, name=None)):
            vals_all.append(f"(:am{i}, :ad{i})")
            params_all[f"am{i}"] = m
            params_all[f"ad{i}"] = d
        values_clause_all = ", ".join(vals_all)

        sql_all = text(f"""
            with pairs(mom_code, dad_code) as (values {values_clause_all})
            select
              s.selection_id,
              s.cross_instance_id,
              s.selection_created_at,
              s.selection_annotated_at,
              s.red_intensity,
              s.green_intensity,
              s.notes,
              s.annotated_by,
              s.label
            from public.v_clutch_instance_selections s
            join public.vw_cross_runs_overview r
              on r.cross_instance_id = s.cross_instance_id
            join pairs p
              on p.mom_code = r.mom_code and p.dad_code = r.dad_code
            order by coalesce(s.selection_annotated_at, s.selection_created_at) desc,
                     s.selection_created_at desc
        """)

        with eng.begin() as cx:
            rows_all = cx.execute(sql_all, params_all).mappings().all()
        table_all = pd.DataFrame(rows_all)

        run_meta = det[["cross_instance_id","clutch_code","cross_run_code","birthday"]].drop_duplicates()
        table_all = table_all.merge(run_meta, how="left", on="cross_instance_id")

        for c in [
            "clutch_code","cross_run_code","birthday",
            "selection_created_at","selection_annotated_at",
            "red_intensity","green_intensity","notes","annotated_by","label","selection_id"
        ]:
            if c not in table_all.columns:
                table_all[c] = ""

        cols = [
            "clutch_code","cross_run_code","birthday",
            "selection_created_at","selection_annotated_at",
            "red_intensity","green_intensity","notes","annotated_by","label","selection_id",
        ]
        present = [c for c in cols if c in table_all.columns]
        st.dataframe(table_all[present], hide_index=True, use_container_width=True)