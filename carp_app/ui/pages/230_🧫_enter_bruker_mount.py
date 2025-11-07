# =============================================================================
# 023_🧫_enter_bruker_mount.py
# Enter mounts for a selected clutch + stage per-slot annotations, then save.
# Flow:
# 1) Select clutch
# 2) Choose slots (top/bottom × 1..4)
# 3) Apply staged defaults and/or per-slot override (staged only)
# 4) Save mount (create + seed slots + write to selected slots)
# 5) Show success table
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
from typing import Optional, Dict, Set, List, Tuple
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
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

MOUNT_ORIENTATION_OPTIONS = ["dorsal_head_top","lateral_head_right","lateral_head_left"]
MOUNT_ORIENTATION_DEFAULT = "dorsal_head_top"

# -----------------------------------------------------------------------------
# Helpers: schema introspection (mounts) + clutch list loader
# -----------------------------------------------------------------------------
def _ensure_kind(kind_code: str, label: str, value_type: str) -> None:
    with eng.begin() as cx:
        got = pd.read_sql(text("SELECT 1 FROM public.annotations WHERE kind_code=:k LIMIT 1"), cx, params={"k": kind_code})
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
        where.append("v.created_at_instance::date BETWEEN :d1 AND :d2"); p.update({"d1": d1, "d2": d2})
    if who.strip():
        where.append("COALESCE(v.created_by_instance,'') ILIKE :by"); p["by"] = f"%{who.strip()}%"
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
# Helpers: clutch_instance_id resolver + mount code preview + mount insert
# -----------------------------------------------------------------------------
def _resolve_ci_id(code: str) -> Optional[str]:
    if not code: return None
    with eng.begin() as cx:
        df = pd.read_sql(text("""
            SELECT id::text AS clutch_instance_id
            FROM public.clutch_instances
            WHERE clutch_instance_code = :c
            LIMIT 1
        """), cx, params={"c": code})
        if not df.empty: return df["clutch_instance_id"].iloc[0]
        df = pd.read_sql(text("""
            SELECT id::text AS clutch_instance_id
            FROM public.clutch_instances
            WHERE upper(regexp_replace(COALESCE(clutch_instance_code,''), '-[0-9]{2}$','')) =
                  upper(regexp_replace(:c, '^CI-',''))
            LIMIT 1
        """), cx, params={"c": code})
        if not df.empty: return df["clutch_instance_id"].iloc[0]
        df = pd.read_sql(text("""
            SELECT ci.id::text AS clutch_instance_id
            FROM public.clutch_instances ci
            JOIN public.cross_instances x ON x.id = ci.cross_instance_id
            WHERE upper(regexp_replace(x.cross_run_code, '-[0-9]{2}$','')) =
                  upper(regexp_replace(:c, '^CI-',''))
            ORDER BY ci.created_at DESC NULLS LAST
            LIMIT 1
        """), cx, params={"c": code})
        if not df.empty: return df["clutch_instance_id"].iloc[0]
    return None

def _preview_next_mount_code() -> str:
    with eng.begin() as cx:
        df = pd.read_sql(text("""
            WITH today AS (SELECT to_char((now() AT TIME ZONE 'UTC'),'YYYYMMDD') AS ymd),
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
    if has_ori:   cols_sql.append("mounting_orientation"); vals_sql.append(":ori"); params["ori"] = ori
    if has_time:  cols_sql.append("time_mounted");         vals_sql.append("now()")
    if has_ntop:  cols_sql.append("n_top");                 vals_sql.append(":n_top");    params["n_top"] = int(n_top or 0)
    if has_nbot:  cols_sql.append("n_bottom");              vals_sql.append(":n_bottom"); params["n_bottom"] = int(n_bottom or 0)
    if has_notes: cols_sql.append("notes");                 vals_sql.append("NULLIF(:notes,'')"); params["notes"] = notes or ""
    sql = text(f"""
        INSERT INTO public.mounts ({", ".join(cols_sql)})
        VALUES ({", ".join(vals_sql)})
        RETURNING mount_code
    """)
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return df

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
    st.info("No clutches found with the current filters."); st.stop()

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

# --- clutch picker (single-select + auto-unlock) ---
picker = st.data_editor(
    dfv, hide_index=True, width="stretch", num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False, help="Select one clutch to continue"),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True),
    },
    column_order=["✓ Select"] + cols,
    key="enter_mounts_ci_picker_v7",
)

sel_series = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False)
if sel_series.any():
    first_idx = int(sel_series[sel_series].index[0])
    sel_series[:] = False
    sel_series.iloc[first_idx] = True
    dfv.loc[:, "✓ Select"] = False
    dfv.iloc[first_idx, dfv.columns.get_loc("✓ Select")] = True

selected_rows = dfv[sel_series].reset_index(drop=True)
picked = selected_rows

st.markdown(
    f"""
    <div style="margin:.75rem 0 .25rem 0; font-weight:600;">
      <span style="padding:.2rem .5rem; border-radius:.5rem; background:#e6ffed; color:#03643b;">Step 1: Select clutch ✓</span>
      <span style="padding:.2rem .5rem; border-radius:.5rem; background:{('#e6ffed' if not picked.empty else '#f2f2f2')}; color:{('#03643b' if not picked.empty else '#888')}; margin-left:.5rem;">
        Step 2: Stage annotations
      </span>
      <span style="padding:.2rem .5rem; border-radius:.5rem; background:{('#e6ffed' if not picked.empty else '#f2f2f2')}; color:{('#03643b' if not picked.empty else '#888')}; margin-left:.5rem;">
        Step 3: Save mount
      </span>
    </div>
    """,
    unsafe_allow_html=True,
)

prev = st.session_state.get("__enter_mounts_last_ci")
if picked.empty:
    st.info("Select a clutch above to continue."); st.stop()
else:
    current = str(picked.iloc[0]["clutch_code"])
    if current != prev:
        st.session_state["__enter_mounts_last_ci"] = current
        st.rerun()

ci_code = str(picked.iloc[0]["clutch_code"])
cid = _resolve_ci_id(ci_code)
if not cid:
    st.error("Could not resolve clutch_instance_id from this code."); st.stop()

# -----------------------------------------------------------------------------
# Stage per-slot annotations (no DB writes yet)
# -----------------------------------------------------------------------------
st.subheader("Stage per-slot annotations")

SLOTS = [("top", i) for i in range(1,5)] + [("bottom", i) for i in range(1,5)]
def _slot_key(w: str, n: int) -> str: return f"{w}-{n}"

def _idx_to_key(idx: int) -> str:
    # 1..4 → top 1..4 ; 5..8 → bottom 1..4
    if 1 <= idx <= 4:  return _slot_key("top", idx)
    if 5 <= idx <= 8:  return _slot_key("bottom", idx-4)
    return ""

def _parse_slots(expr: str) -> list[str]:
    out: set[str] = set()
    if not expr.strip(): return []
    for tok in [t.strip() for t in expr.replace(" ", "").split(",") if t.strip()]:
        if "-" in tok:
            a,b = tok.split("-",1)
            try:
                a_i = int(a); b_i = int(b)
            except ValueError:
                continue
            lo, hi = (a_i, b_i) if a_i <= b_i else (b_i, a_i)
            for v in range(lo, hi+1):
                k = _idx_to_key(v)
                if k: out.add(k)
        else:
            try:
                v = int(tok)
            except ValueError:
                continue
            k = _idx_to_key(v)
            if k: out.add(k)
    # keep canonical top1..4, bottom1..4 order
    order = [_slot_key("top",i) for i in range(1,5)] + [_slot_key("bottom",i) for i in range(1,5)]
    return [k for k in order if k in out]

# Session state for staged plan { "top-1": {"red":..,"green":..,"ori":..,"notes":..}, ... }
if "__slot_plan" not in st.session_state:
    st.session_state["__slot_plan"] = {}
plan = st.session_state["__slot_plan"]

# --- Slot selector via single field ---
st.caption("Enter slot indexes (1–8), ranges and commas OK. 1–4 = top 1–4, 5–8 = bottom 1–4. Examples: `1-3, 5` → top(1–3) and bottom(1). `1-8` → all slots.")
slot_expr = st.text_input("Selected slots", value=st.session_state.get("__slot_expr",""), placeholder="e.g. 1-3, 5")
# Preset checkboxes (combinable)
top_row = st.columns([1,1,1])
with top_row[0]:
    pre_top14 = st.checkbox("Top (1–4)", value=st.session_state.get("__pre_top14", False), key="__pre_top14")
with top_row[1]:
    pre_top13 = st.checkbox("Top (1–3)", value=st.session_state.get("__pre_top13", False), key="__pre_top13")
with top_row[2]:
    pre_top12 = st.checkbox("Top (1–2)", value=st.session_state.get("__pre_top12", False), key="__pre_top12")

bot_row = st.columns([1,1])
with bot_row[0]:
    pre_bot12 = st.checkbox("Bottom (1–2)", value=st.session_state.get("__pre_bot12", False), key="__pre_bot12")
with bot_row[1]:
    pre_bot1  = st.checkbox("Bottom (1)",    value=st.session_state.get("__pre_bot1",  False), key="__pre_bot1")

# Build selected set from text expression + presets
_selected = set(_parse_slots(slot_expr))

if pre_top14: _selected.update([_slot_key("top",i) for i in range(1,5)])
if pre_top13: _selected.update([_slot_key("top",i) for i in range(1,4)])
if pre_top12: _selected.update([_slot_key("top",i) for i in range(1,3)])
if pre_bot12: _selected.update([_slot_key("bottom",i) for i in range(1,3)])
if pre_bot1:  _selected.update([_slot_key("bottom",1)])

# Keep canonical order
_order = [_slot_key("top",i) for i in range(1,5)] + [_slot_key("bottom",i) for i in range(1,5)]
selected_keys = [k for k in _order if k in _selected]

# Preserve the raw text the user typed
st.session_state["__slot_expr"] = slot_expr

if not selected_keys:
    st.info("Pick at least one slot (e.g. `1-3, 5`) to stage annotations.")
else:
    # Brief preview of which human-readable slots are in play
    pretty = [k.replace("-", " ") for k in selected_keys]
    st.success(f"Selected: {', '.join(pretty)}")

# --- Defaults for selected slots (staged only) ---
st.markdown("**Defaults to stage for selected slots**")
c1,c2,c3 = st.columns([1,1,2])
with c1: def_red   = st.number_input("red_intensity",   min_value=0.0, max_value=1.0, step=0.05, value=1.0)
with c2: def_green = st.number_input("green_intensity", min_value=0.0, max_value=1.0, step=0.05, value=1.0)
with c3: def_notes = st.text_input("notes", value="", placeholder="optional")
def_ori = st.selectbox("orientation", MOUNT_ORIENTATION_OPTIONS, index=0)

def _apply_defaults_to_selected():
    for k in selected_keys:
        plan[k] = {
            "red": float(def_red),
            "green": float(def_green),
            "ori": (def_ori or MOUNT_ORIENTATION_DEFAULT),
            "notes": (def_notes or "").strip(),
        }

if st.button("Apply defaults to selected slots", use_container_width=True, disabled=not selected_keys):
    _apply_defaults_to_selected()
    st.success("Defaults staged.")

# --- Per-slot override (staged only) ---
st.markdown("— Or override one slot (staged) —")
c_ov1,c_ov2 = st.columns([1,1])
with c_ov1:
    ov_idx = st.number_input("slot index (1–8)", min_value=1, max_value=8, step=1, value=1, key="ov_idx")
with c_ov2:
    ov_slot_text = st.text_input("slot (read-only)", value=_idx_to_key(int(ov_idx)).replace("-", " "), disabled=True)

c3,c4,c5 = st.columns([1,1,2])
with c3: ov_red   = st.number_input("red_intensity (override)",   min_value=0.0, max_value=1.0, step=0.05, value=def_red,   key="ov_red_stage")
with c4: ov_green = st.number_input("green_intensity (override)", min_value=0.0, max_value=1.0, step=0.05, value=def_green, key="ov_green_stage")
with c5: ov_notes = st.text_input("notes (override)", value="", key="ov_notes_stage")
ov_ori = st.selectbox("orientation (override)", MOUNT_ORIENTATION_OPTIONS, index=0, key="ov_ori_stage")

def _apply_override_one() -> bool:
    k = _idx_to_key(int(ov_idx))
    if not k or k not in selected_keys:
        return False
    plan[k] = {
        "red": float(ov_red),
        "green": float(ov_green),
        "ori": (ov_ori or MOUNT_ORIENTATION_DEFAULT),
        "notes": (ov_notes or "").strip(),
    }
    return True

if st.button("Save staged override for selected slot", use_container_width=True):
    if _apply_override_one():
        st.success(f"Staged override for {ov_slot_text}.")
    else:
        st.warning("That slot isn’t in the selected set. Include it in the Selected slots field first.")

# --- Preview staged plan ---
if plan:
    _rows = []
    order = [_slot_key("top",i) for i in range(1,5)] + [_slot_key("bottom",i) for i in range(1,5)]
    for k in order:
        s = plan.get(k)
        if not s: continue
        _rows.append({
            "slot": k.replace("-", " "),
            "red": s["red"], "green": s["green"],
            "orientation": s["ori"], "notes": s["notes"],
        })
    st.caption("Staged plan (will be written on Save mount):")
    st.dataframe(pd.DataFrame(_rows), hide_index=True, use_container_width=True)

# -----------------------------------------------------------------------------
# Save mount → create + seed + write plan to selected slots → success table
# -----------------------------------------------------------------------------
st.divider()
st.subheader("Save mount")

# Show prior success (persisted across rerun) with Dismiss
if "__last_success" in st.session_state:
    suc = st.session_state["__last_success"]
    st.success(f"Mount **{suc['mount_code']}** created; {len(suc['rows'])} slot(s) annotated.")
    st.dataframe(pd.DataFrame(suc["rows"]), hide_index=True, use_container_width=True)
    if st.button("Dismiss", key="dismiss_success"):
        del st.session_state["__last_success"]
        st.rerun()

def _write_plan_after_mount(mount_code: str):
    # Resolve slot IDs (well/subwell → id)
    with eng.begin() as cx:
        df_map = pd.read_sql(text("""
            SELECT s.id::text AS slot_id, s.well, s.subwell
            FROM public.mount_slots s
            JOIN public.mounts m ON m.id = s.mount_id
            WHERE m.mount_code = :code
        """), cx, params={"code": mount_code})
    key_to_id = { _slot_key(r["well"], int(r["subwell"])): r["slot_id"] for _,r in df_map.iterrows() }

    # Ensure kinds exist
    _ensure_kind("red_intensity","Red intensity","number")
    _ensure_kind("green_intensity","Green intensity","number")
    _ensure_kind("orientation","Orientation","text")
    _ensure_kind("notes","Notes","text")

    who = getattr(user, "email", "") or ""
    rows_written = []
    with eng.begin() as cx:
        for k in selected_keys:
            s = plan.get(k)
            if not s: continue
            sid = key_to_id.get(k)
            if not sid: continue
            # red
            cx.execute(text("""
                INSERT INTO public.join_annotations (target_type,target_id,annotation_id,value_num,created_by)
                SELECT 'mount_slot', CAST(:sid AS uuid), a.id, CAST(:v AS numeric), :who
                FROM public.annotations a WHERE a.kind_code='red_intensity'
            """), {"sid": sid, "v": s["red"], "who": who})
            # green
            cx.execute(text("""
                INSERT INTO public.join_annotations (target_type,target_id,annotation_id,value_num,created_by)
                SELECT 'mount_slot', CAST(:sid AS uuid), a.id, CAST(:v AS numeric), :who
                FROM public.annotations a WHERE a.kind_code='green_intensity'
            """), {"sid": sid, "v": s["green"], "who": who})
            # orientation (always)
            cx.execute(text("""
                INSERT INTO public.join_annotations (target_type,target_id,annotation_id,value_text,created_by)
                SELECT 'mount_slot', CAST(:sid AS uuid), a.id, :v, :who
                FROM public.annotations a WHERE a.kind_code='orientation'
            """), {"sid": sid, "v": (s["ori"] or MOUNT_ORIENTATION_DEFAULT), "who": who})
            # notes (optional)
            if (s["notes"] or "").strip():
                cx.execute(text("""
                    INSERT INTO public.join_annotations (target_type,target_id,annotation_id,value_text,created_by)
                    SELECT 'mount_slot', CAST(:sid AS uuid), a.id, :v, :who
                    FROM public.annotations a WHERE a.kind_code='notes'
                """), {"sid": sid, "v": s["notes"].strip(), "who": who})
            rows_written.append({
                "mount_code": mount_code,
                "slot": k.replace("-", " "),
                "red": s["red"], "green": s["green"],
                "orientation": s["ori"], "notes": s["notes"],
            })
    return rows_written

if st.button("Save mount", use_container_width=True, disabled=not selected_keys):
    # Create mount (minimal mount fields; adapt as your schema allows)
    saved = _insert_mount(cid, MOUNT_ORIENTATION_DEFAULT, 0, 0, "")
    mount_code = saved.iloc[0]["mount_code"] if not saved.empty else None
    if not mount_code:
        st.error("Failed to create mount."); st.stop()

    # Slots are auto-seeded by trigger; now write staged plan for selected slots
    rows = _write_plan_after_mount(mount_code)

    # Persist success across rerun (so it doesn't flash away)
    st.session_state["__last_success"] = {"mount_code": mount_code, "rows": rows}

    # Clear staged plan for next run and rerun
    st.session_state["__slot_plan"] = {}
    st.session_state["__slot_expr"] = ""
    st.rerun()