from __future__ import annotations
import os, sys
from pathlib import Path
import datetime as _dt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# Path bootstrap
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Annotate Clutch Instances", page_icon="🐣", layout="wide")
st.title("🐣 Annotate Clutch Instances")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set")
    st.stop()
eng = create_engine(DB_URL, future=True, pool_pre_ping=True)

# DB badge (host + role)
from sqlalchemy import text as _text
try:
    url = getattr(eng, "url", None)
    host = (getattr(url, "host", None) or os.getenv("PGHOST", "") or "(unknown)")
    with eng.begin() as cx:
        role = cx.execute(_text("select current_setting('role', true)")).scalar()
        user = cx.execute(_text("select current_user")).scalar()
    st.caption(f"DB: {host} • role={role or 'default'} • user={user}")
except Exception:
    pass

# Stamp user into session (for audit)
try:
    from supabase.ui.lib.app_ctx import stamp_app_user
    who = getattr(st.experimental_user, "email", "") if hasattr(st, "experimental_user") else ""
    stamp_app_user(eng, who)
except Exception:
    pass

# Ensure table exists where this app connects
with eng.begin() as cx:
    exists_tbl = cx.execute(text("select to_regclass('public.clutch_instances')")).scalar()
if not exists_tbl:
    st.error("Table public.clutch_instances not found in this DB.")
    st.stop()

# ───────────────────── Conceptual overview + realized instances ─────────────────────
st.markdown("## 🔍 Clutches — Conceptual overview with instance counts")

today = _dt.date.today()
d_from = st.date_input("From", value=today - _dt.timedelta(days=14), key="ci_from")
d_to = st.date_input("To", value=today, key="ci_to")
if d_from and d_to and d_from > d_to:
    d_from, d_to = d_to, d_from

# Load concepts in window
with eng.begin() as cx:
    concept_df = pd.read_sql(
        text("""
            select
              conceptual_cross_code as clutch_code,
              name as clutch_name,
              nickname as clutch_nickname,
              mom_code, dad_code, mom_code_tank, dad_code_tank,
              created_at
            from public.v_cross_concepts_overview
            where (:d1 is null or created_at::date >= :d1)
              and (:d2 is null or created_at::date <= :d2)
            order by created_at desc nulls last, clutch_code
            limit 2000
        """),
        cx,
        params={"d1": str(d_from) if d_from else None, "d2": str(d_to) if d_to else None},
    )

# Count realized runs in window (match by mom+dad)
counts = pd.DataFrame(columns=["clutch_code", "n_instances"])
if not concept_df.empty:
    with eng.begin() as cx:
        runs = pd.read_sql(
            text("""
                select cross_run_code, cross_date::date as d, mom_code, dad_code
                from public.vw_cross_runs_overview
                where (:d1 is null or cross_date::date >= :d1)
                  and (:d2 is null or cross_date::date <= :d2)
            """),
            cx,
            params={"d1": str(d_from) if d_from else None, "d2": str(d_to) if d_to else None},
        )
    if not runs.empty:
        merged = concept_df.merge(runs, how="left", on=["mom_code", "dad_code"])
        counts = (
            merged.groupby("clutch_code", dropna=False)["cross_run_code"]
            .count()
            .rename("n_instances")
            .reset_index()
        )
concept_df = concept_df.merge(counts, how="left", on="clutch_code").fillna({"n_instances": 0})
concept_df = concept_df.astype({"n_instances": int})

# Selection model
sel_key = "_concept_table"
if sel_key not in st.session_state:
    t = concept_df.copy()
    t.insert(0, "✓ Select", False)
    st.session_state[sel_key] = t
else:
    base = st.session_state[sel_key].set_index("clutch_code")
    now = concept_df.set_index("clutch_code")
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
    base = base.loc[now.index]
    st.session_state[sel_key] = base.reset_index()

st.markdown("### Conceptual clutches")
view_cols = [
    "✓ Select", "clutch_code", "clutch_name", "clutch_nickname",
    "mom_code", "dad_code", "mom_code_tank", "dad_code_tank",
    "created_at", "n_instances",
]
present = [c for c in view_cols if c in st.session_state[sel_key].columns]
edited_concepts = st.data_editor(
    st.session_state[sel_key][present],
    hide_index=True,
    use_container_width=True,
    column_order=present,
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_code": st.column_config.TextColumn("clutch_code", disabled=True),
        "clutch_name": st.column_config.TextColumn("clutch_name", disabled=True),
        "clutch_nickname": st.column_config.TextColumn("clutch_nickname", disabled=True),
        "mom_code": st.column_config.TextColumn("mom_code", disabled=True),
        "dad_code": st.column_config.TextColumn("dad_code", disabled=True),
        "mom_code_tank": st.column_config.TextColumn("mom tank", disabled=True),
        "dad_code_tank": st.column_config.TextColumn("dad tank", disabled=True),
        "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
        "n_instances": st.column_config.NumberColumn("instances", disabled=True),
    },
    key="ci_concept_editor",
)
st.session_state[sel_key].loc[edited_concepts.index, "✓ Select"] = edited_concepts["✓ Select"]
selected_codes = edited_concepts.loc[edited_concepts["✓ Select"], "clutch_code"].astype(str).tolist()

# ───────────────────────── Realized instances in window for selected concepts ─────────────────────────
st.markdown("### Realized instances for selection")

if not selected_codes:
    st.info("No realized clutch instances yet.")
else:
    # 1) Fetch mom/dad for the selected concepts (use canonical view)
    with eng.begin() as cx:
        sel_mom_dad = pd.read_sql(
            text("""
                select conceptual_cross_code as clutch_code, mom_code, dad_code
                from public.v_cross_concepts_overview
                where conceptual_cross_code = any(:codes)
            """),
            cx, params={"codes": selected_codes}
        )
        # 2) Fetch runs in the window (enriched view, has cross_instance_id)
        runs = pd.read_sql(
            text("""
                select
                  cross_instance_id,
                  cross_run_code,
                  cross_date::date as cross_date,
                  mom_code, dad_code,
                  mother_tank_label, father_tank_label,
                  run_created_by, run_created_at, run_note
                from public.vw_cross_runs_overview
                where (:d1 is null or cross_date::date >= :d1)
                  and (:d2 is null or cross_date::date <= :d2)
            """),
            cx, params={"d1": str(d_from) if d_from else None, "d2": str(d_to) if d_to else None}
        )

    if sel_mom_dad.empty or runs.empty:
        st.info("No realized clutch instances yet.")
    else:
        # 3) Join runs to the selected concepts by mom+dad
        det = sel_mom_dad.merge(runs, how="inner", on=["mom_code", "dad_code"])
        det = det.sort_values(["run_created_at", "cross_date"], ascending=[False, False])

        # 4) Show a selectable grid (✓ Add) so user can seed clutch_instances from these runs
        cols = [
            "clutch_code", "cross_run_code", "cross_date",
            "mom_code", "dad_code", "mother_tank_label", "father_tank_label",
            "run_created_by", "run_created_at", "run_note", "cross_instance_id"
        ]
        present = [c for c in cols if c in det.columns]
        grid = det[present].copy()
        grid.insert(0, "✓ Add", False)

        edited_seed = st.data_editor(
            grid,
            hide_index=True,
            use_container_width=True,
            column_order=["✓ Add"] + present,
            column_config={"✓ Add": st.column_config.CheckboxColumn("✓", default=False)},
            key="ci_seed_editor",
        )

        # 5) Actions: create clutch instances from selected runs + CSV download for runs
        c1, c2 = st.columns([1, 3])
        with c1:
            create_clicked = st.button("➕ Create clutch instance(s)")
        with c2:
            st.download_button(
                "⬇️ Download runs (CSV)",
                det[present].to_csv(index=False),
                "runs.csv",
                "text/csv"
            )

        if create_clicked:
            rows = edited_seed[edited_seed["✓ Add"] == True]
            if rows.empty:
                st.warning("No runs selected.")
            else:
                created = 0
                with eng.begin() as cx:
                    for _, r in rows.iterrows():
                        xid = str(r.get("cross_instance_id") or "").strip()
                        if not xid:
                            continue  # nothing to link
                        # helpful default label: "<CL> / <XR>"
                        ccode   = str(r.get("clutch_code") or "").strip()
                        runcode = str(r.get("cross_run_code") or "").strip()
                        label   = " / ".join([s for s in (ccode, runcode) if s]) or "clutch"
                        cx.execute(
                            text("""
                                insert into public.clutch_instances (cross_instance_id, label, created_at)
                                select :xid, :label, now()
                                where not exists (
                                  select 1 from public.clutch_instances where cross_instance_id = :xid
                                )
                            """),
                            {"xid": xid, "label": label}
                        )
                        created += 1
                st.success(f"Created {created} clutch instance(s).")
                st.rerun()

        # optionally keep the selected concepts in session for downstream filters
        st.session_state["_concept_selection"] = selected_codes

# ───────────────────────── Annotation grid (red/green + legacy) ───────────────────
with eng.begin() as cx:
    df = pd.read_sql(text("""
        select
          id::text as id,
          coalesce(label,'') as label,
          coalesce(phenotype,'') as phenotype,
          coalesce(notes,'') as notes,
          coalesce(red_selected,false) as red_selected,
          coalesce(red_intensity,'') as red_intensity,
          coalesce(red_note,'') as red_note,
          coalesce(green_selected,false) as green_selected,
          coalesce(green_intensity,'') as green_intensity,
          coalesce(green_note,'') as green_note,
          coalesce(annotated_by,'') as annotated_by,
          annotated_at, created_at
        from public.clutch_instances
        order by coalesce(annotated_at, created_at) desc nulls last
        limit 2000
    """), cx)

st.caption(f"{len(df)} clutch instance(s)")
if df.empty:
    st.info("No clutch instances yet.")
    st.stop()

# Optional: filter annotation grid to selected concepts and window, if your label carries the run code
sel_codes = st.session_state.get("_concept_selection", [])
if sel_codes:
    with eng.begin() as cx:
        runs_sel = pd.read_sql(
            text("""
                with concepts as (
                    select clutch_code, mom_code, dad_code
                    from public.v_cross_concepts_overview
                    where clutch_code = any(:codes)
                )
                select r.cross_run_code
                from public.vw_cross_runs_overview r
                join concepts c on r.mom_code=c.mom_code and r.dad_code=c.dad_code
                where (:d1 is null or r.cross_date::date >= :d1)
                  and (:d2 is null or r.cross_date::date <= :d2)
            """),
            cx, params={"codes": sel_codes, "d1": str(d_from) if d_from else None, "d2": str(d_to) if d_to else None}
        )
    if not runs_sel.empty:
        run_codes = set(runs_sel["cross_run_code"].astype(str))
        df = df[df["label"].astype(str).apply(lambda s: any(rc in s for rc in run_codes))]

# Build session model
key = "_ci_table"
if key not in st.session_state:
    t = df.copy()
    t.insert(0, "✓ Select", False)
    st.session_state[key] = t
else:
    base = st.session_state[key].set_index("id")
    now = df.set_index("id")
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
    base = base.loc[now.index]
    st.session_state[key] = base.reset_index()

# Filters and bulk apply
existing = [x for x in df["phenotype"].dropna().unique().tolist() if str(x).strip()]
common = ["normal", "abnormal", "lethal", "mosaic", "wildtype", "tg_positive", "tg_negative"]
presets = list(dict.fromkeys(existing + common))

c1, c2, c3 = st.columns([2, 2, 2])
with c1:
    q = st.text_input("Search (id/label/phenotype/notes/red*/green*)", "")
with c2:
    legacy_preset = st.selectbox("Legacy phenotype preset", ["(none)"] + presets, index=0)
with c3:
    legacy_quick_note = st.text_input("Legacy quick note (optional)", "")

st.subheader("Bulk apply — color selections")
col_a, col_b = st.columns([1, 1])
with col_a:
    color = st.radio("Color", options=["red", "green"], horizontal=True)
with col_b:
    set_selected = st.checkbox("Set selected", value=True)

col1, col2 = st.columns([1, 2])
with col1:
    intensity_val = st.text_input("Intensity", value="")
with col2:
    note_val = st.text_input("Note", value="")

view = st.session_state[key].copy()
if q:
    ql = q.lower()
    mask = view.apply(lambda r: ql in (" ".join([str(x) for x in r.values])).lower(), axis=1)
    view = view[mask]

bsa, bcl, _ = st.columns([1, 1, 2])
with bsa:
    if st.button("Select all (filtered)", key="btn_select_all_filtered"):
        st.session_state[key].loc[view.index, "✓ Select"] = True
with bcl:
    if st.button("Clear selection", key="btn_clear_all"):
        st.session_state[key]["✓ Select"] = False

if st.button("Apply legacy preset/notes → selected"):
    rows = st.session_state[key].index[st.session_state[key]["✓ Select"] == True]
    if len(rows) == 0:
        st.warning("No rows selected.")
    else:
        if legacy_preset != "(none)":
            st.session_state[key].loc[rows, "phenotype"] = legacy_preset
        if legacy_quick_note.strip():
            def _append(old: str) -> str:
                old = (old or "").strip()
                return (old + ("; " if old else "") + legacy_quick_note.strip())
            st.session_state[key].loc[rows, "notes"] = \
                st.session_state[key].loc[rows, "notes"].apply(_append)
        st.success(f"Applied legacy fields to {len(rows)} row(s).")

if st.button(f"Apply {color} selection → selected"):
    rows = st.session_state[key].index[st.session_state[key]["✓ Select"] == True]
    if len(rows) == 0:
        st.warning("No rows selected.")
    else:
        sel_col = f"{color}_selected"
        inten_col = f"{color}_intensity"
        note_col = f"{color}_note"
        st.session_state[key].loc[rows, sel_col] = bool(set_selected)
        st.session_state[key].loc[rows, inten_col] = intensity_val
        st.session_state[key].loc[rows, note_col] = note_val
        st.success(f"Applied {color} selection to {len(rows)} row(s).")

display_cols = [
    "✓ Select", "id", "label",
    "phenotype", "notes",
    "red_selected", "red_intensity", "red_note",
    "green_selected", "green_intensity", "green_note",
    "annotated_by", "annotated_at", "created_at",
]
present_cols = [c for c in display_cols if c in view.columns]

edited = st.data_editor(
    view[present_cols],
    hide_index=True,
    use_container_width=True,
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "id": st.column_config.TextColumn("id", disabled=True),
        "label": st.column_config.TextColumn("label", disabled=True),
        "phenotype": st.column_config.TextColumn("phenotype"),
        "notes": st.column_config.TextColumn("notes"),
        "red_selected": st.column_config.CheckboxColumn("red_selected", default=False),
        "red_intensity": st.column_config.TextColumn("red_intensity"),
        "red_note": st.column_config.TextColumn("red_note"),
        "green_selected": st.column_config.CheckboxColumn("green_selected", default=False),
        "green_intensity": st.column_config.TextColumn("green_intensity"),
        "green_note": st.column_config.TextColumn("green_note"),
        "annotated_by": st.column_config.TextColumn("annotated_by", disabled=True),
        "annotated_at": st.column_config.DatetimeColumn("annotated_at", disabled=True),
        "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
    },
    key="ci_editor",
)

# Only-mine toggle and CSV export for editor snapshot
only_mine = st.toggle("Only mine", value=False, help="Show rows you annotated")
if only_mine:
    view = view[view["annotated_by"].astype(str).str.len() > 0]

# Persist edits back to session master for the currently visible rows
st.session_state[key].loc[edited.index, [c for c in present_cols if c not in ("id", "label")]] = \
    edited[present_cols].drop(columns=["id", "label"], errors="ignore")

# Diff and save
base = df.set_index("id")
cur = st.session_state[key].set_index("id")
save_cols = [
    "phenotype", "notes",
    "red_selected", "red_intensity", "red_note",
    "green_selected", "green_intensity", "green_note",
]
joined = cur[save_cols].join(base[save_cols], how="left", lsuffix="_new", rsuffix="_old")
changed_mask = False
for c in save_cols:
    joined[f"chg_{c}"] = (joined[f"{c}_new"] != joined[f"{c}_old"])
    changed_mask = joined[f"chg_{c}"] | changed_mask
changes = joined[changed_mask].reset_index()

if st.button("💾 Save changes", type="primary"):
    if changes.empty:
        st.info("No edits to save.")
    else:
        n = 0
        with eng.begin() as cx:
            for _, r in changes.iterrows():
                cx.execute(text("""
                    update public.clutch_instances
                       set
                         phenotype        = nullif(:phenotype, ''),
                         notes            = nullif(:notes, ''),
                         red_selected     = :red_selected,
                         red_intensity    = nullif(:red_intensity, ''),
                         red_note         = nullif(:red_note, ''),
                         green_selected   = :green_selected,
                         green_intensity  = nullif(:green_intensity, ''),
                         green_note       = nullif(:green_note, ''),
                         annotated_by     = coalesce(current_setting('app.user', true), annotated_by),
                         annotated_at     = now()
                     where id::text = :id
                """), {
                    "id": r["id"],
                    "phenotype": r.get("phenotype_new", None) if pd.notna(r.get("phenotype_new")) else None,
                    "notes": r.get("notes_new", None) if pd.notna(r.get("notes_new")) else None,
                    "red_selected": bool(r.get("red_selected_new", False)),
                    "red_intensity": r.get("red_intensity_new", None) if pd.notna(r.get("red_intensity_new")) else None,
                    "red_note": r.get("red_note_new", None) if pd.notna(r.get("red_note_new")) else None,
                    "green_selected": bool(r.get("green_selected_new", False)),
                    "green_intensity": r.get("green_intensity_new", None) if pd.notna(r.get("green_intensity_new")) else None,
                    "green_note": r.get("green_note_new", None) if pd.notna(r.get("green_note_new")) else None,
                })
                n += 1
        st.success(f"Updated {n} row(s).")
        # CSV export of current editor snapshot
        try:
            export_cols = [c for c in st.session_state[key].columns if c != "✓ Select"]
            st.download_button("⬇️ Download annotations (CSV)", st.session_state[key][export_cols].to_csv(index=False),
                               "clutch_annotations.csv", "text/csv")
        except Exception:
            pass
        # Refresh snapshot and rerun
        with eng.begin() as cx:
            df2 = pd.read_sql(text("""
                select
                  id::text as id, coalesce(label,'') as label,
                  coalesce(phenotype,'') as phenotype, coalesce(notes,'') as notes,
                  coalesce(red_selected,false) as red_selected, coalesce(red_intensity,'') as red_intensity, coalesce(red_note,'') as red_note,
                  coalesce(green_selected,false) as green_selected, coalesce(green_intensity,'') as green_intensity, coalesce(green_note,'') as green_note,
                  coalesce(annotated_by,'') as annotated_by, annotated_at, created_at
                from public.clutch_instances
                order by coalesce(annotated_at, created_at) desc nulls last
            """), cx)
        t = df2.copy()
        t.insert(0, "✓ Select", False)
        st.session_state[key] = t
        st.rerun()