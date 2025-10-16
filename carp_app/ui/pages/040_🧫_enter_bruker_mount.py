from __future__ import annotations
from carp_app.lib.config import engine as get_engine
# carp_app/ui/pages/040_🧫_enter_bruker_mount.py

import os
import sys
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from carp_app.lib.db import get_engine
from sqlalchemy import text
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp

# ────────────────────────── Auth (respects AUTH_MODE wrapper) ──────────────────────────
sb, session, user = require_auth()
require_email_otp()  # no-op if AUTH_MODE in {off, passcode}

# ────────────────────────── Path bootstrap ──────────────────────────
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ────────────────────────── App constants ───────────────────────────
APP_TZ = os.getenv("APP_TZ", "America/Los_Angeles")
LA_TODAY = dt.datetime.now(ZoneInfo(APP_TZ)).date()

st.set_page_config(page_title="Enter Bruker Mount", page_icon="🧪", layout="wide")
st.title("🧪 Enter Bruker Mount")

# ────────────────────────── DB / engine ─────────────────────────────
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set")
    st.stop()
eng = get_engine()

# Badge + user stamping
from sqlalchemy import text as _text  # only for the badge
_ui_user = ""
try:
    url = getattr(eng, "url", None)
    host = (getattr(url, "host", None) or os.getenv("PGHOST", "") or "(unknown)")
    with eng.begin() as cx:
        role = cx.execute(_text("select current_setting('role', true)")).scalar()
        who = cx.execute(_text("select current_user")).scalar()
    _ui_user = who or ""
    st.caption(f"DB: {host} • role={role or 'default'} • user={_ui_user}")
except Exception:
    pass

try:
    from carp_app.ui.lib.app_ctx import stamp_app_user
    who_ui = getattr(st, "experimental_user", None)
    if who_ui and getattr(who_ui, "email", ""):
        _ui_user = who_ui.email
    stamp_app_user(eng, _ui_user)
except Exception:
    pass

# ────────────────────────── Helpers ─────────────────────────────────
def _one_checked(df: pd.DataFrame, check_col: str) -> pd.Series | None:
    if check_col not in df.columns:
        return None
    checked = df.index[df[check_col] == True].tolist()
    return df.loc[checked[0]] if len(checked) == 1 else None


def _col_is_uuid(cx, schema: str, table: str, col: str) -> bool:
    row = cx.execute(
        text(
            """
            select data_type, udt_name
            from information_schema.columns
            where table_schema=:s and table_name=:t and column_name=:c
            """
        ),
        {"s": schema, "t": table, "c": col},
    ).first()
    if not row:  # missing column ⇒ assume not uuid
        return False
    data_type, udt_name = (row[0] or ""), (row[1] or "")
    return data_type.lower() == "uuid" or udt_name.lower() == "uuid"


# ────────────────────────── Step 1 — Concept ────────────────────────
st.markdown("### 1) Choose clutch concept")

c1, c2 = st.columns([3, 1])
with c1:
    q = st.text_input(
        "Filter concepts (code/name/mom/dad)",
        "",
        placeholder="e.g., CL-25 or MGCO or FSH-250001",
    )
with c2:
    show_n = st.number_input("Show up to", 50, 2000, 500, step=50)

with eng.begin() as cx:
    concepts = pd.read_sql(
        text(
            """
            select
              conceptual_cross_code as clutch_code,
              name                  as clutch_name,
              nickname              as clutch_nickname,
              mom_code, dad_code,
              created_at
            from public.v_cross_concepts_overview
            order by created_at desc nulls last, clutch_code
            limit 2000
            """
        ),
        cx,
    )

if q.strip():
    ql = q.lower()
    concepts = concepts[
        concepts.apply(
            lambda r: any(
                ql in str(r[c]).lower()
                for c in [
                    "clutch_code",
                    "clutch_name",
                    "clutch_nickname",
                    "mom_code",
                    "dad_code",
                ]
            ),
            axis=1,
        )
    ]
concepts = concepts.head(int(show_n)).reset_index(drop=True)

key_concepts = "_bruker_concept_grid"
if key_concepts not in st.session_state:
    t = concepts.copy()
    t.insert(0, "✓ Concept", False)
    st.session_state[key_concepts] = t
else:
    base = st.session_state[key_concepts].set_index("clutch_code")
    now = concepts.set_index("clutch_code")
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
    base = base.loc[now.index]
    st.session_state[key_concepts] = base.reset_index()

concept_cols = [
    "✓ Concept",
    "clutch_code",
    "clutch_name",
    "clutch_nickname",
    "mom_code",
    "dad_code",
    "created_at",
]
concept_cols = [c for c in concept_cols if c in st.session_state[key_concepts].columns]

concept_edit = st.data_editor(
    st.session_state[key_concepts][concept_cols],
    hide_index=True,
    use_container_width=True,
    column_order=concept_cols,
    column_config={"✓ Concept": st.column_config.CheckboxColumn("✓", default=False)},
    key="bruker_concept_editor",
)
st.session_state[key_concepts].loc[concept_edit.index, "✓ Concept"] = concept_edit[
    "✓ Concept"
]
concept_row = _one_checked(st.session_state[key_concepts], "✓ Concept")
if concept_row is None:
    st.info("Tick exactly one concept to continue.")
    st.stop()

concept_code = str(concept_row["clutch_code"])
mom_code = str(concept_row["mom_code"])
dad_code = str(concept_row["dad_code"])

# ────────────────────────── Step 2 — Run for concept ────────────────
st.markdown("### 2) Choose cross instance (run) for the concept")

with eng.begin() as cx:
    runs = pd.read_sql(
        text(
            """
            select
              cross_instance_id,
              cross_run_code,
              cross_date::date as cross_date,
              mother_tank_label,
              father_tank_label
            from public.vw_cross_runs_overview
            where mom_code=:m and dad_code=:d
            order by cross_date desc, cross_run_code desc
            """
        ),
        cx,
        params={"m": mom_code, "d": dad_code},
    )
    sel_rollup = pd.read_sql(
        text(
            """
            select
              cross_instance_id,
              string_agg(
                nullif(
                  trim(
                    concat_ws(' ',
                      case when coalesce(red_intensity,'')   <> '' then 'red='   || red_intensity   end,
                      case when coalesce(green_intensity,'') <> '' then 'green=' || green_intensity end,
                      case when coalesce(notes,'')           <> '' then 'note='  || notes          end
                    )
                  ),
                  ''
                ),
                ' | ' order by created_at
              ) as selections_rollup
            from public.clutch_instances
            group by cross_instance_id
            """
        ),
        cx,
    )

runs = runs.merge(sel_rollup, how="left", on="cross_instance_id").fillna(
    {"selections_rollup": ""}
)

key_runs = "_bruker_run_grid"
if key_runs not in st.session_state:
    t = runs.copy()
    t.insert(0, "✓ Run", False)
    st.session_state[key_runs] = t
else:
    base = st.session_state[key_runs].set_index("cross_run_code")
    now = runs.set_index("cross_run_code")
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
    base = base.loc[now.index]
    st.session_state[key_runs] = base.reset_index()

run_cols = [
    "✓ Run",
    "cross_run_code",
    "cross_date",
    "mother_tank_label",
    "father_tank_label",
    "selections_rollup",
]
run_cols = [c for c in run_cols if c in st.session_state[key_runs].columns]

run_edit = st.data_editor(
    st.session_state[key_runs][run_cols],
    hide_index=True,
    use_container_width=True,
    column_order=run_cols,
    column_config={
        "✓ Run": st.column_config.CheckboxColumn("✓", default=False),
        "selections_rollup": st.column_config.TextColumn(
            "selections_rollup", disabled=True
        ),
    },
    key="bruker_run_editor",
)
st.session_state[key_runs].loc[run_edit.index, "✓ Run"] = run_edit["✓ Run"]
run_row = _one_checked(st.session_state[key_runs], "✓ Run")
if run_row is None:
    st.info("Tick exactly one run to continue.")
    st.stop()

cross_instance_id = str(run_row["cross_instance_id"])
cross_run_code = str(run_row["cross_run_code"])
cross_date = str(run_row["cross_date"])

# ────────────────────────── Step 3 — Selection on that run ──────────
st.markdown("### 3) Choose selection for the run")

with eng.begin() as cx:
    # Prefer normalized view if present
    has_view = bool(
        cx.execute(
            text(
                """
                select 1
                from pg_class c
                join pg_namespace n on n.oid = c.relnamespace
                where n.nspname = 'public'
                  and c.relkind in ('v','m')
                  and c.relname = 'v_clutch_instance_selections'
                limit 1
                """
            )
        ).first()
    )

    if has_view:
        sql = text(
            """
            select
              selection_id::text        as selection_id,
              cross_instance_id::text   as cross_instance_id,
              selection_created_at      as selection_created_at,
              selection_annotated_at    as selection_annotated_at,
              red_intensity, green_intensity, notes,
              annotated_by, label
            from public.v_clutch_instance_selections
            where cross_instance_id = cast(:xid as uuid)
            order by coalesce(selection_annotated_at, selection_created_at) desc,
                     selection_created_at desc
            """
        )
        selections = pd.read_sql(sql, cx, params={"xid": cross_instance_id})
    else:
        # Fall back to clutch_instances, auto-detect id column
        row = cx.execute(
            text(
                """
                select 1
                from information_schema.columns
                where table_schema='public'
                  and table_name='clutch_instances'
                  and column_name='id'
                limit 1
                """
            )
        ).first()
        id_col = "id" if row else "id_uuid"
        sql = text(
            f"""
            select
              {id_col}::text             as selection_id,
              cross_instance_id::text    as cross_instance_id,
              created_at                 as selection_created_at,
              annotated_at               as selection_annotated_at,
              red_intensity, green_intensity, notes,
              annotated_by, label
            from public.clutch_instances
            where cross_instance_id = cast(:xid as uuid)
            order by coalesce(annotated_at, created_at) desc,
                     created_at desc
            """
        )
        selections = pd.read_sql(sql, cx, params={"xid": cross_instance_id})

if selections.empty:
    st.caption(
        "No selections for this run yet. Use the ‘Annotate Clutch Instances’ page to add one, then return."
    )
    st.stop()

key_sel = "_bruker_selection_grid"
if key_sel not in st.session_state:
    t = selections.copy()
    t.insert(0, "✓ Selection", False)
    st.session_state[key_sel] = t
else:
    base = st.session_state[key_sel].set_index("selection_id")
    now = selections.set_index("selection_id")
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
    base = base.loc[now.index]
    st.session_state[key_sel] = base.reset_index()

sel_cols = [
    "✓ Selection",
    "label",
    "selection_created_at",
    "selection_annotated_at",
    "red_intensity",
    "green_intensity",
    "notes",
    "annotated_by",
]
sel_cols = [c for c in sel_cols if c in st.session_state[key_sel].columns]

sel_edit = st.data_editor(
    st.session_state[key_sel][sel_cols],
    hide_index=True,
    use_container_width=True,
    column_order=sel_cols,
    column_config={"✓ Selection": st.column_config.CheckboxColumn("✓", default=False)},
    key="bruker_selection_editor",
)
st.session_state[key_sel].loc[sel_edit.index, "✓ Selection"] = sel_edit[
    "✓ Selection"
]
sel_row = _one_checked(st.session_state[key_sel], "✓ Selection")
if sel_row is None:
    st.info("Tick exactly one selection to continue.")
    st.stop()

selection_id = str(sel_row["selection_id"])
selection_label = str(sel_row.get("label") or "")

st.caption(
    f"Context • concept={concept_code} • run={cross_run_code} ({cross_date}) • selection_label={selection_label}"
)

# ────────────────────────── Step 4 — Mount details ──────────────────
st.markdown("### 4) Mount details")

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    d_val = st.date_input("Date", value=LA_TODAY)
with c2:
    t_val = st.time_input(
        "Time mounted", value=dt.datetime.now().time().replace(microsecond=0)
    )
with c3:
    orientation = st.selectbox(
        "Orientation", ["dorsal", "ventral", "lateral", "other"], index=0
    )

c4, c5 = st.columns([1, 1])
with c4:
    n_top = int(st.number_input("n_top", min_value=0, value=4, step=1))
with c5:
    n_bottom = int(st.number_input("n_bottom", min_value=0, value=2, step=1))

save = st.button("Save mount", type="primary")
if save:
    try:
        with eng.begin() as cx:
            sel_is_uuid = _col_is_uuid(cx, "public", "bruker_mounts", "selection_id")

            if sel_is_uuid:
                cx.execute(
                    text(
                        """
                        insert into public.bruker_mounts (
                          selection_id, mount_date, mount_time, orientation, n_top, n_bottom,
                          created_at, created_by
                        )
                        values (
                          cast(:sid as uuid), :md, :mt, :orient, :nt, :nb,
                          now(), coalesce(current_setting('app.user', true), current_user)
                        )
                        """
                    ),
                    {
                        "sid": selection_id,
                        "md": d_val,
                        "mt": t_val,
                        "orient": orientation,
                        "nt": n_top,
                        "nb": n_bottom,
                    },
                )
            else:
                cx.execute(
                    text(
                        """
                        insert into public.bruker_mounts (
                          selection_id, mount_date, mount_time, orientation, n_top, n_bottom,
                          created_at, created_by
                        )
                        values (
                          :sid, :md, :mt, :orient, :nt, :nb,
                          now(), coalesce(current_setting('app.user', true), current_user)
                        )
                        """
                    ),
                    {
                        "sid": selection_id,
                        "md": d_val,
                        "mt": t_val,
                        "orient": orientation,
                        "nt": n_top,
                        "nb": n_bottom,
                    },
                )

        st.success("Bruker mount saved.")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to save mount: {e}")

# ────────────────────────── Recent mounts for this selection ────────
st.markdown("### Recent mounts for this selection")

with eng.begin() as cx:
    recent = pd.read_sql(
        text(
            """
            select
              mount_code,
              mount_date, mount_time,
              n_top, n_bottom, orientation,
              created_at, created_by
            from public.vw_bruker_mounts_enriched
            where selection_id = cast(:sid as uuid)
            order by created_at desc
            limit 50
            """
        ),
        cx,
        params={"sid": str(selection_id)},
    )

if recent.empty:
    st.caption("No mounts yet for this selection.")
else:
    cols = [
        "mount_code",
        "mount_date",
        "mount_time",
        "n_top",
        "n_bottom",
        "orientation",
        "created_at",
        "created_by",
    ]
    st.dataframe(
        recent[[c for c in cols if c in recent.columns]],
        hide_index=True,
        use_container_width=True,
    )