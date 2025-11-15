# carp_app/ui/pages/210_🧪_annotate_treated_clutch_groups.py
from __future__ import annotations

import sys, pathlib, os
from datetime import date, timedelta
from typing import Any, Dict

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

# --- project wiring -----------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...

from carp_app.ui.lib.page_engine import engine
eng = engine()

# --- auth / page --------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🐣 Annotate Treated Clutch Groups",
    page_icon="🐣",
    layout="wide",
)
st.title("🐣 Annotate Treated Clutch Groups")

with engine().begin() as cx:
    dbg = pd.read_sql(
        text("select current_database() db, inet_server_addr() host, current_user u"),
        cx,
    )
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# --- objects we use -----------------------------------------------------------
V_TCL_OV   = "public.v_treated_clutches_overview"  # one row per treated group
T_TCL      = "public.treated_clutches"
T_JANN     = "public.join_annotations"
T_ANN      = "public.annotations"
V_LATEST_G = "public.v_annotations_latest_group"   # optional convenience view

# --- helpers ------------------------------------------------------------------
def _exists_view(qualified: str) -> bool:
    sch, name = qualified.split(".", 1)
    q = text(
        "SELECT 1 FROM information_schema.views WHERE table_schema=:s AND table_name=:n "
        "UNION ALL SELECT 1 FROM pg_catalog.pg_matviews WHERE schemaname=:s AND matviewname=:n "
        "LIMIT 1"
    )
    with engine().begin() as cx:
        return cx.execute(q, {"s": sch, "n": name}).first() is not None

def _exists_table(qualified: str) -> bool:
    sch, name = qualified.split(".", 1)
    q = text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema=:s AND table_name=:n LIMIT 1"
    )
    with engine().begin() as cx:
        return cx.execute(q, {"s": sch, "n": name}).first() is not None

def _safe(cx, q: str | TextClause, p: Dict[str, Any] | None = None) -> pd.DataFrame:
    q = q if isinstance(q, TextClause) else text(q)
    return pd.read_sql(q, cx, params=p or {})

# --- filters ------------------------------------------------------------------
today = date.today()
with st.form("filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        d_from = st.date_input("From", value=today - timedelta(days=120))
    with c2:
        d_to = st.date_input("To", value=today + timedelta(days=14))
    with c3:
        qtxt = st.text_input(
            "Search (group/clutch/cross/genotype/treatments/parents)", value=""
        )
    r1, r2 = st.columns([1, 3])
    with r1:
        most_recent = st.checkbox("Most recent (ignore dates)", value=False)
    with r2:
        st.form_submit_button("Apply", use_container_width=True)

# --- load treated groups (thin: select from the view) -------------------------
def _require_objects():
    miss = []
    if not _exists_view(V_TCL_OV):
        miss.append(V_TCL_OV)
    for t in (T_TCL, T_JANN, T_ANN):
        if not _exists_table(t):
            miss.append(t)
    if miss:
        st.error("Required object not found: " + ", ".join(miss))
        st.stop()

def _load_groups_filtered(
    d1: date, d2: date, q: str, most_recent: bool
) -> pd.DataFrame:
    _require_objects()
    where, p = [], {}
    if not most_recent:
        where.append("group_created_at::date BETWEEN :d1 AND :d2")
        p.update({"d1": d1, "d2": d2})
    if q.strip():
        p["q"] = f"%{q.strip()}%"
        # UPDATED: use new rollup column names from v_treated_clutches_overview
        where.append(
            """(
              treated_clutch_code           ILIKE :q OR
              clutch_code                   ILIKE :q OR
              cross_code                    ILIKE :q OR
              COALESCE(clutch_genotype,'')          ILIKE :q OR
              COALESCE(treatment_codes_rollup,'')   ILIKE :q OR
              COALESCE(treatment_names_rollup,'')   ILIKE :q
            )"""
        )
    wsql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = text(
        f"""
        SELECT *
        FROM {V_TCL_OV}
        {wsql}
        ORDER BY clutch_code, group_created_at
        LIMIT 500
        """
    )
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params=p)

    # trust the view's clutch_birthday / clutch_genotype_pretty
    if "cross_name_pretty" not in df.columns:
        df["cross_name_pretty"] = df["cross_code"].astype("string")

    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")

    return df

df = _load_groups_filtered(d_from, d_to, qtxt, most_recent)
st.caption(f"{len(df)} treated clutch group(s)")
if df.empty:
    st.info("No groups found with the current filters.")
    st.stop()

# --- picker -------------------------------------------------------------------
cols = [
    "treated_clutch_code",
    "group_created_at",
    "treatments_count_group",
    # UPDATED: use new names from view
    "treatment_codes_rollup",
    "treatment_names_rollup",
    "clutch_code",
    "clutch_birthday",
    "cross_name_pretty",
    "clutch_genotype_pretty",
]
dfv = df[cols].copy()
dfv.insert(0, "✓ Select", False)
last_group = st.session_state.get("__annot_last_group")
if last_group:
    dfv.loc[dfv["treated_clutch_code"] == last_group, "✓ Select"] = True

picker = st.data_editor(
    dfv,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "group_created_at": st.column_config.DatetimeColumn(
            "created_at", disabled=True
        ),
        "clutch_birthday": st.column_config.DateColumn(
            "clutch_birthday", disabled=True, format="YYYY-MM-DD"
        ),
        "treatments_count_group": st.column_config.NumberColumn(
            "# tx", disabled=True, format="%d"
        ),
    },
    key="annot_group_picker",
)
sel = (
    picker.get("✓ Select", pd.Series(False, index=picker.index))
    .fillna(False)
    .astype(bool)
)
picked = dfv[sel].reset_index(drop=True)
if picked.empty:
    st.info("Select a treated clutch group to annotate it.")
    st.stop()

group_code = str(picked.iloc[0]["treated_clutch_code"])
st.session_state["__annot_last_group"] = group_code

# --- resolve treated_clutch_id + clutch_instance_id --------------------------
def _resolve_ids_from_group(group_code: str) -> tuple[str | None, str | None]:
    sql = text(
        """
      SELECT tc.id::text AS treated_clutch_id,
             tc.clutch_instance_id::text AS clutch_instance_id
      FROM public.treated_clutches tc
      WHERE tc.treated_clutch_code = :g
      LIMIT 1
    """
    )
    with engine().begin() as cx:
        row = pd.read_sql(sql, cx, params={"g": group_code})
    if row.empty:
        return None, None
    return row.iloc[0]["treated_clutch_id"], row.iloc[0]["clutch_instance_id"]

treated_clutch_id, clutch_instance_id = _resolve_ids_from_group(group_code)
if not treated_clutch_id:
    st.error("Could not resolve treated_clutch_id for this group.")
    st.stop()

# --- load current (latest) annotation values ---------------------------------
def _load_group_latest(group_code: str, treated_clutch_id: str) -> Dict[str, Any]:
    if _exists_view(V_LATEST_G):
        sql = text(
            f"""
          SELECT kind_code, value_num, value_text
          FROM {V_LATEST_G}
          WHERE treated_clutch_code = :g
        """
        )
        with eng.begin() as cx:
            df = pd.read_sql(sql, cx, params={"g": group_code})
    else:
        sql = text(
            """
          WITH ranked AS (
            SELECT
              ja.kind_code, ja.value_num, ja.value_text, ja.created_at,
              ROW_NUMBER() OVER (
                PARTITION BY ja.kind_code
                ORDER BY ja.created_at DESC NULLS LAST
              ) rn
            FROM public.join_annotations ja
            WHERE ja.target_kind = 'treated_clutch'
              AND ja.target_id   = CAST(:tid AS uuid)
          )
          SELECT kind_code, value_num, value_text
          FROM ranked WHERE rn = 1
        """
        )
        with eng.begin() as cx:
            df = pd.read_sql(sql, cx, params={"tid": treated_clutch_id})

    out: Dict[str, Any] = {}
    for _, r in df.iterrows():
        k = str(r["kind_code"])
        if k == "notes":
            out[k] = r.get("value_text")
        else:
            out[k] = r.get("value_num")
    return out

current = _load_group_latest(group_code, treated_clutch_id)

# --- inputs (1–100 scale for intensities/frequencies) ------------------------
st.subheader("Annotate this treated clutch group")
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    red_val = st.number_input(
        "red_intensity (1–100)",
        min_value=1,
        max_value=100,
        step=1,
        value=int(round(float(current.get("red_intensity") or 0) or 1)),
    )
with c2:
    green_val = st.number_input(
        "green_intensity (1–100)",
        min_value=1,
        max_value=100,
        step=1,
        value=int(round(float(current.get("green_intensity") or 0) or 1)),
    )
with c3:
    note_txt = st.text_input(
        "notes", value=str(current.get("notes") or ""), placeholder="optional"
    )

c4, c5, c6 = st.columns([1, 1, 1])
with c4:
    gfreq_val = st.number_input(
        "green_frequency (1–100)",
        min_value=1,
        max_value=100,
        step=1,
        value=int(round(float(current.get("green_frequency") or 0) or 1)),
    )
with c5:
    rfreq_val = st.number_input(
        "red_frequency (1–100)",
        min_value=1,
        max_value=100,
        step=1,
        value=int(round(float(current.get("red_frequency") or 0) or 1)),
    )
with c6:
    n_val = st.number_input(
        "n_animals (integer ≥ 0)",
        min_value=0,
        step=1,
        value=int(current.get("n_animals") or 0),
    )

# --- save to join_annotations -------------------------------------------------
def _save_annotation_num(tid: str, kind: str, val: int, who: str):
    with eng.begin() as cx:
        cx.execute(
            text(
                """
          INSERT INTO public.join_annotations
            (target_kind, target_id, kind_code, value_num, created_at)
          VALUES ('treated_clutch', CAST(:tid AS uuid), :k, :v, now())
        """
            ),
            {"tid": tid, "k": kind, "v": val},
        )

def _save_annotation_text(tid: str, kind: str, txt: str, who: str):
    if not (txt or "").strip():
        return
    with eng.begin() as cx:
        cx.execute(
            text(
                """
          INSERT INTO public.join_annotations
            (target_kind, target_id, kind_code, value_text, created_at)
          VALUES ('treated_clutch', CAST(:tid AS uuid), :k, NULLIF(:v,''), now())
        """
            ),
            {"tid": tid, "k": kind, "v": txt},
        )

if st.button("💾 Save", use_container_width=True):
    who = (
        getattr(user, "email", None)
        or os.getenv("USER")
        or os.getenv("USERNAME")
        or "system"
    )
    _save_annotation_num(treated_clutch_id, "red_intensity", int(red_val), who)
    _save_annotation_num(treated_clutch_id, "green_intensity", int(green_val), who)
    _save_annotation_num(treated_clutch_id, "green_frequency", int(gfreq_val), who)
    _save_annotation_num(treated_clutch_id, "red_frequency", int(rfreq_val), who)
    _save_annotation_num(treated_clutch_id, "n_animals", int(n_val), who)
    _save_annotation_text(treated_clutch_id, "notes", note_txt, who)
    st.success("Annotation saved.")
    st.rerun()

# --- show current after save --------------------------------------------------
st.subheader("Current annotation (latest values)")
latest = _load_group_latest(group_code, treated_clutch_id)
if latest:
    show = {
        "red_intensity": latest.get("red_intensity"),
        "green_intensity": latest.get("green_intensity"),
        "green_frequency": latest.get("green_frequency"),
        "red_frequency": latest.get("red_frequency"),
        "n_animals": latest.get("n_animals"),
        "notes": latest.get("notes"),
    }
    df_show = pd.DataFrame([show])
    st.dataframe(df_show, hide_index=True, use_container_width=True)
else:
    st.caption("No annotations recorded yet for this group.")