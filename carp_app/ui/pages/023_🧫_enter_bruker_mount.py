# =============================================================================
# 023_🧫_enter_bruker_mount.py
# Enter mounts for a selected clutch + annotate 8 mount slots (broadcast/override)
# - Reads clutches from public.v_clutch_instances
# - Inserts mounts adapting to available columns in public.mounts
# - Annotates slot values (red_intensity, green_intensity, orientation, notes)
# - Orientation writes are guaranteed (default to dorsal_head_top if blank)
# - Final table sorted: top 1 → top 4 → bottom 1 → bottom 4
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
from typing import Optional, Dict, Set
import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.lib.db import get_engine
from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()
from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

# -----------------------------------------------------------------------------
# Page config
# -----------------------------------------------------------------------------
st.set_page_config(page_title="🧫 Enter Mounts", page_icon="🧫", layout="wide")
st.title("🧫 Enter Mounts")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set")
    st.stop()
eng = get_engine()

MOUNT_ORIENTATION_OPTIONS = ["dorsal_head_top","lateral_head_right","lateral_head_left"]
MOUNT_ORIENTATION_DEFAULT = "dorsal_head_top"

# -----------------------------------------------------------------------------
# Helpers: schema introspection (mounts) + clutch list loader
# -----------------------------------------------------------------------------
def _ensure_kind(kind_code: str, label: str, value_type: str) -> None:
    with eng.begin() as cx:
        got = pd.read_sql(text("SELECT 1 FROM public.annotations WHERE kind_code=:k LIMIT 1"),
                          cx, params={"k": kind_code})
        if got.empty:
            cx.execute(text("""
                INSERT INTO public.annotations (kind_code, label, value_type)
                VALUES (:k, :label, :vt)
                ON CONFLICT (kind_code) DO NOTHING
            """), {"k": kind_code, "label": label, "vt": value_type})

def _mounts_cols() -> Set[str]:
    with eng.begin() as cx:
        cols = pd.read_sql(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='mounts'
        """), cx)
    return set(cols["column_name"].tolist())

def _load_clutches_filtered(d1: date, d2: date, who: str, q: str, most_recent: bool) -> pd.DataFrame:
    where, p = [], {}
    if not most_recent:
        where.append("v.created_at_instance::date BETWEEN :d1 AND :d2")
        p.update({"d1": d1, "d2": d2})
    if who.strip():
        where.append("COALESCE(v.created_by_instance,'') ILIKE :by")
        p["by"] = f"%{who.strip()}%"
    if q.strip():
        p["q"] = f"%{q.strip()}%"
        where.append("""(
          COALESCE(v.clutch_code,'')                         ILIKE :q OR
          COALESCE(v.cross_name_pretty,'')                   ILIKE :q OR
          COALESCE(v.clutch_name,'')                         ILIKE :q OR
          COALESCE(v.clutch_genotype_pretty,'')              ILIKE :q OR
          COALESCE(v.treatments_pretty_effective,'')         ILIKE :q OR
          COALESCE(v.genotype_treatment_rollup_effective,'') ILIKE :q
        )""")
    wsql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = text(f"""
      SELECT
        v.clutch_code,
        v.cross_name_pretty,
        v.clutch_name,
        v.clutch_genotype_pretty,
        v.genotype_treatment_rollup_effective,
        v.treatments_count_effective,
        v.treatments_pretty_effective,
        v.clutch_birthday,
        v.created_by_instance,
        v.created_at_instance
      FROM public.v_clutch_instances v
      {wsql}
      ORDER BY v.created_at_instance DESC NULLS LAST, v.clutch_code
      LIMIT 500
    """)
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params=p)
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    if "treatments_count_effective" in df.columns:
        df["treatments_count_effective"] = pd.to_numeric(df["treatments_count_effective"], errors="coerce").fillna(0).astype(int)
    return df

# -----------------------------------------------------------------------------
# Helpers: clutch_instance_id resolver + mount code preview + mount insert/load
# -----------------------------------------------------------------------------
def _resolve_ci_id(code: str) -> Optional[str]:
    if not code:
        return None
    with eng.begin() as cx:
        df = pd.read_sql(text("""
            SELECT id::text AS clutch_instance_id
            FROM public.clutch_instances
            WHERE clutch_instance_code = :c
            LIMIT 1
        """), cx, params={"c": code})
        if not df.empty:
            return df["clutch_instance_id"].iloc[0]
        df = pd.read_sql(text("""
            SELECT id::text AS clutch_instance_id
            FROM public.clutch_instances
            WHERE upper(regexp_replace(COALESCE(clutch_instance_code,''), '-[0-9]{2}$','')) =
                  upper(regexp_replace(:c, '^CI-',''))
            LIMIT 1
        """), cx, params={"c": code})
        if not df.empty:
            return df["clutch_instance_id"].iloc[0]
        df = pd.read_sql(text("""
            SELECT ci.id::text AS clutch_instance_id
            FROM public.clutch_instances ci
            JOIN public.cross_instances x ON x.id = ci.cross_instance_id
            WHERE upper(regexp_replace(x.cross_run_code, '-[0-9]{2}$','')) =
                  upper(regexp_replace(:c, '^CI-',''))
            ORDER BY ci.created_at DESC NULLS LAST
            LIMIT 1
        """), cx, params={"c": code})
        if not df.empty:
            return df["clutch_instance_id"].iloc[0]
    return None

def _preview_next_mount_code() -> str:
    with eng.begin() as cx:
        df = pd.read_sql(text("""
            WITH today AS (
              SELECT to_char((now() AT TIME ZONE 'UTC'),'YYYYMMDD') AS ymd
            ),
            nextn AS (
              SELECT COALESCE(MAX(((regexp_match(mount_code, '^MT-(\\d{8})-(\\d+)$'))[2])::int),0) + 1 AS n
              FROM public.mounts, today
              WHERE mount_code LIKE ('MT-'||(SELECT ymd FROM today)||'-%')
            )
            SELECT 'MT-'||(SELECT ymd FROM today)||'-'||(SELECT n FROM nextn) AS code
        """), cx)
        return df["code"].iloc[0] if not df.empty else ""

def _insert_mount(cid: str, ori: str, n_top: int, n_bottom: int, notes: str) -> pd.DataFrame:
    cols = _mounts_cols()
    has_time = ("time_mounted" in cols)
    has_ntop = ("n_top" in cols)
    has_nbot = ("n_bottom" in cols)
    has_notes = ("notes" in cols)
    has_ori = ("mounting_orientation" in cols)

    cols_sql = ["clutch_instance_id", "mount_code"]
    vals_sql = [":cid", ":code"]
    params: Dict[str, object] = {"cid": cid, "code": _preview_next_mount_code()}

    if has_ori:
        cols_sql.append("mounting_orientation")
        vals_sql.append(":ori")
        params["ori"] = ori
    if has_time:
        cols_sql.append("time_mounted")
        vals_sql.append("now()")
    if has_ntop:
        cols_sql.append("n_top")
        vals_sql.append(":n_top")
        params["n_top"] = int(n_top or 0)
    if has_nbot:
        cols_sql.append("n_bottom")
        vals_sql.append(":n_bottom")
        params["n_bottom"] = int(n_bottom or 0)
    if has_notes:
        cols_sql.append("notes")
        vals_sql.append("NULLIF(:notes,'')")
        params["notes"] = notes or ""

    sql = text(f"""
        INSERT INTO public.mounts ({", ".join(cols_sql)})
        VALUES ({", ".join(vals_sql)})
        RETURNING mount_code
    """)
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return df

def _load_latest_mount(cid: str) -> pd.DataFrame:
    cols = _mounts_cols()
    order_expr = "created_at" if "created_at" in cols else ("time_mounted" if "time_mounted" in cols else "id")
    select_cols = ["mount_code"]
    for c in ("mounting_orientation","n_top","n_bottom","time_mounted","notes"):
        if c in cols:
            select_cols.append(c)
    sql = text(f"""
        SELECT {", ".join(select_cols)}
        FROM public.mounts
        WHERE clutch_instance_id = CAST(:cid AS uuid)
        ORDER BY {order_expr} DESC NULLS LAST
        LIMIT 1
    """)
    with eng.begin() as cx:
        return pd.read_sql(sql, cx, params={"cid": cid})

# -----------------------------------------------------------------------------
# Filters form (clutch list)
# -----------------------------------------------------------------------------
with st.form("enter_mounts_filters", clear_on_submit=False):
    today = date.today()
    c1,c2,c3,c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=120))
    with c2: d2 = st.date_input("To",   value=today + timedelta(days=14))
    with c3: who  = st.text_input("Created by (plan/instance)", value="")
    with c4: qtxt = st.text_input("Search (code/cross/genotype)", value="")
    r1, r2 = st.columns([1,3])
    with r1: most_recent = st.checkbox("Most recent (ignore dates)", value=False)
    with r2: st.form_submit_button("Apply", width="stretch")

df = _load_clutches_filtered(d1, d2, who, qtxt, most_recent)
st.caption(f"{len(df)} clutch(es)")
if df.empty:
    st.info("No clutches found with the current filters.")
    st.stop()

cols = [
    "clutch_code","cross_name_pretty","clutch_name",
    "clutch_genotype_pretty","genotype_treatment_rollup_effective",
    "treatments_count_effective","treatments_pretty_effective",
    "clutch_birthday","created_by_instance",
]
dfv = df[cols].copy()
dfv.insert(0, "✓ Select", False)
last_ci = st.session_state.get("__enter_mounts_last_ci")
if last_ci:
    dfv.loc[dfv["clutch_code"] == last_ci, "✓ Select"] = True

picker = st.data_editor(
    dfv, hide_index=True, width="stretch", num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True),
    },
    column_order=["✓ Select"] + cols,
    key="enter_mounts_ci_picker_v7",
)
sel = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False)
picked = dfv[sel].reset_index(drop=True)
if picked.empty:
    st.info("Select a clutch instance row to enter its mount.")
    st.stop()

ci_code = str(picked.iloc[0]["clutch_code"])
st.session_state["__enter_mounts_last_ci"] = ci_code
cid = _resolve_ci_id(ci_code)
if not cid:
    st.error("Could not resolve clutch_instance_id from this code.")
    st.stop()

# -----------------------------------------------------------------------------
# Enter mount for selected clutch
# -----------------------------------------------------------------------------
st.subheader("Enter mount for this clutch instance")

cols_mount = _mounts_cols()
try:
    default_idx = MOUNT_ORIENTATION_OPTIONS.index(MOUNT_ORIENTATION_DEFAULT)
except ValueError:
    default_idx = 0
if "mounting_orientation" in cols_mount:
    ori = st.selectbox("mount orientation", options=MOUNT_ORIENTATION_OPTIONS, index=default_idx)
else:
    ori = MOUNT_ORIENTATION_DEFAULT
notes_in = st.text_input("notes", value="") if "notes" in cols_mount else ""

_preview = st.empty()
def _refresh_preview():
    _preview.caption(f"Next auto code (preview): **{_preview_next_mount_code() or 'MT-YYYYMMDD-1'}**")
_refresh_preview()

c1,c2 = st.columns(2)
with c1:
    n_top = st.number_input("n_top", min_value=0, step=1, value=0) if "n_top" in cols_mount else 0
with c2:
    n_bottom = st.number_input("n_bottom", min_value=0, step=1, value=0) if "n_bottom" in cols_mount else 0

st.subheader("Updated mount (latest)")
latest = _load_latest_mount(cid)
if latest.empty:
    st.info("No mount rows yet for this clutch instance.")
else:
    st.dataframe(latest, width="stretch", hide_index=True)

# -----------------------------------------------------------------------------
# Annotate 8 slots: broadcast defaults, per-slot override (all fields)
# -----------------------------------------------------------------------------
st.divider()
st.subheader("Annotate slots (8 per mount)")

with eng.begin() as cx:
    slots = pd.read_sql(text("""
        WITH m AS (
          SELECT id, mount_code
          FROM public.mounts
          WHERE clutch_instance_id = CAST(:cid AS uuid)
          ORDER BY id DESC
          LIMIT 1
        )
        SELECT
          m.mount_code,
          s.id::text AS mount_slot_id,
          s.well,
          s.subwell
        FROM public.mount_slots s
        JOIN m ON s.mount_id = m.id
        ORDER BY s.well, s.subwell
    """), cx, params={"cid": cid})

if slots.empty:
    st.info("No slots found for the latest mount of this clutch.")
    st.stop()

mount_code = slots["mount_code"].iloc[0]
st.caption(f"Mount: {mount_code}")

# --- defaults to broadcast to all 8 slots ---
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    red_val = st.number_input("red_intensity", min_value=0.0, max_value=1.0, step=0.05, value=0.0, key="ms_red")
with c2:
    green_val = st.number_input("green_intensity", min_value=0.0, max_value=1.0, step=0.05, value=0.0, key="ms_green")
with c3:
    note_txt = st.text_input("notes", value="", key="ms_note")

orientation = st.selectbox(
    "orientation",
    ["dorsal_head_top", "lateral_head_right", "lateral_head_left"],
    index=0,
    key="ms_ori"
)

def _broadcast_to_all_slots():
    who = getattr(user, "email", "") or ""

    _ensure_kind("red_intensity", "Red intensity", "number")
    _ensure_kind("green_intensity", "Green intensity", "number")
    _ensure_kind("orientation", "Orientation", "text")
    _ensure_kind("notes", "Notes", "text")

    with eng.begin() as cx:
        base_cte = """
            WITH m AS (
              SELECT id FROM public.mounts WHERE mount_code = :code LIMIT 1
            ),
            targets AS (
              SELECT s.id AS mount_slot_id FROM public.mount_slots s JOIN m ON s.mount_id = m.id
            )
        """

        # red_intensity
        cx.execute(text(base_cte + """
            , k AS (SELECT id FROM public.annotations WHERE kind_code='red_intensity')
            INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_num, created_by)
            SELECT 'mount_slot', t.mount_slot_id, k.id, CAST(:v AS numeric), :who
            FROM targets t CROSS JOIN k
        """), {"code": mount_code, "v": float(red_val), "who": who})

        # green_intensity
        cx.execute(text(base_cte + """
            , k AS (SELECT id FROM public.annotations WHERE kind_code='green_intensity')
            INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_num, created_by)
            SELECT 'mount_slot', t.mount_slot_id, k.id, CAST(:v AS numeric), :who
            FROM targets t CROSS JOIN k
        """), {"code": mount_code, "v": float(green_val), "who": who})

        # orientation (guaranteed; default if blank)
        cx.execute(text(base_cte + """
            , k AS (SELECT id FROM public.annotations WHERE kind_code='orientation')
            INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_text, created_by)
            SELECT 'mount_slot', t.mount_slot_id, k.id, :v, :who
            FROM targets t CROSS JOIN k
        """), {"code": mount_code, "v": (str(orientation).strip() or "dorsal_head_top"), "who": who})

        # notes (optional)
        if (note_txt or "").strip():
            cx.execute(text(base_cte + """
                , k AS (SELECT id FROM public.annotations WHERE kind_code='notes')
                INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_text, created_by)
                SELECT 'mount_slot', t.mount_slot_id, k.id, :v, :who
                FROM targets t CROSS JOIN k
            """), {"code": mount_code, "v": note_txt.strip(), "who": who})

def _save_slot_override_all(well: str, subwell: int, red: float, green: float, orientation_text: str, notes_text: str) -> bool:
    who = getattr(user, "email", "") or ""

    _ensure_kind("red_intensity", "Red intensity", "number")
    _ensure_kind("green_intensity", "Green intensity", "number")
    _ensure_kind("orientation", "Orientation", "text")
    _ensure_kind("notes", "Notes", "text")

    with eng.begin() as cx:
        slot = pd.read_sql(text("""
            SELECT s.id::text AS mount_slot_id
            FROM public.mount_slots s
            JOIN public.mounts m ON m.id = s.mount_id
            WHERE m.mount_code = :code AND s.well = :well AND s.subwell = :subwell
            LIMIT 1
        """), cx, params={"code": mount_code, "well": well, "subwell": int(subwell)})
        if slot.empty:
            return False
        msid = slot["mount_slot_id"].iloc[0]

        # red + green
        cx.execute(text("""
            WITH k AS (
              SELECT kind_code, id
              FROM public.annotations
              WHERE kind_code IN ('red_intensity','green_intensity')
            )
            INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_num, created_by)
            SELECT 'mount_slot', CAST(:msid AS uuid),
                   (SELECT id FROM k WHERE kind_code='red_intensity'),
                   CAST(:red AS numeric), :who
            UNION ALL
            SELECT 'mount_slot', CAST(:msid AS uuid),
                   (SELECT id FROM k WHERE kind_code='green_intensity'),
                   CAST(:green AS numeric), :who
        """), {"msid": msid, "red": float(red), "green": float(green), "who": who})

        # orientation (guaranteed; default if blank)
        cx.execute(text("""
            WITH k AS (SELECT id FROM public.annotations WHERE kind_code='orientation')
            INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_text, created_by)
            SELECT 'mount_slot', CAST(:msid AS uuid), (SELECT id FROM k), :ori, :who
        """), {"msid": msid, "ori": (str(orientation_text).strip() or "dorsal_head_top"), "who": who})

        # notes (optional)
        if (notes_text or "").strip():
            cx.execute(text("""
                WITH k AS (SELECT id FROM public.annotations WHERE kind_code='notes')
                INSERT INTO public.join_annotations (target_type, target_id, annotation_id, value_text, created_by)
                SELECT 'mount_slot', CAST(:msid AS uuid), (SELECT id FROM k), :note, :who
            """), {"msid": msid, "note": notes_text.strip(), "who": who})

        return True

if st.button("Apply defaults to all 8 slots", use_container_width=True):
    _broadcast_to_all_slots()
    st.success("Defaults applied to all 8 slots.")

# --- override one slot (all fields) ---
st.markdown("— Or override one slot —")
c_ov1, c_ov2 = st.columns([1, 1])
with c_ov1:
    ov_well = st.selectbox("well (override)", ["top", "bottom"], index=0, key="ov_well2")
with c_ov2:
    ov_subwell = st.number_input("subwell (override)", min_value=1, max_value=4, step=1, value=1, key="ov_subwell2")

c_ov3, c_ov4, c_ov5 = st.columns([1, 1, 2])
with c_ov3:
    ov_red = st.number_input("red_intensity (override)", min_value=0.0, max_value=1.0, step=0.05, value=0.0, key="ov_red2")
with c_ov4:
    ov_green = st.number_input("green_intensity (override)", min_value=0.0, max_value=1.0, step=0.05, value=0.0, key="ov_green2")
with c_ov5:
    ov_notes = st.text_input("notes (override)", value="", key="ov_notes2")

ov_orientation = st.selectbox(
    "orientation (override)",
    ["dorsal_head_top","lateral_head_right","lateral_head_left"],
    index=0,
    key="ov_ori2"
)

if st.button("Save per-slot override (all fields)", use_container_width=True):
    ok = _save_slot_override_all(
        ov_well, int(ov_subwell),
        ov_red, ov_green,
        ov_orientation, ov_notes
    )
    if ok:
        st.success(f"Saved override for {ov_well} {int(ov_subwell)}.")
        st.rerun()
    else:
        st.error("Slot not found for selected well/subwell.")

# --- final table (sorted: top→bottom; subwell asc) ---
with eng.begin() as cx:
    view = pd.read_sql(text("""
        SELECT mount_code, well, subwell,
               red_intensity, green_intensity,
               orientation, notes, annotations_last_at
        FROM public.v_mount_slot_annotations_pivot
        WHERE mount_code = :code
        ORDER BY
          CASE WHEN well='top' THEN 0 ELSE 1 END,
          subwell ASC
    """), cx, params={"code": mount_code})
st.dataframe(view, hide_index=True, use_container_width=True)

# -----------------------------------------------------------------------------
# Finalize (place the mount insert button at the end)
# -----------------------------------------------------------------------------
st.divider()
st.subheader("Finalize")
nonce = st.session_state.get("__enter_mounts_nonce", 0)
msg = st.session_state.pop("__enter_mounts_msg", None)
if msg:
    st.success(msg)

if st.button("Save mount", use_container_width=True, key=f"save_mount_btn_{nonce}"):
    saved = _insert_mount(cid, ori, n_top, n_bottom, notes_in)
    code = saved.iloc[0]["mount_code"] if not saved.empty else ""
    st.session_state["__enter_mounts_msg"] = f"Mount saved as **{code or '(created)'}**."
    st.session_state["__enter_mounts_nonce"] = nonce + 1
    st.rerun()