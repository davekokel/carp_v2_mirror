# =============================================================================
# 024_🔎_overview_mounts.py — Drill-down mounts (with clutch lineage/genotype pretties)
# Top grid: mounts + summary metrics + clutch lineage/genotype (display + explicit)
# Bottom grid: per-slot latest annotations (8 rows)
# =============================================================================
from __future__ import annotations

import os, sys, pathlib
from typing import Optional, Set
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ── sys.path prime ────────────────────────────────────────────────────────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── auth gates ────────────────────────────────────────────────────────────────
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

# ── app libs ─────────────────────────────────────────────────────────────────
from carp_app.ui.lib.app_ctx import get_engine as _create_engine
from carp_app.lib.time import utc_today

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="CARP — 🔎 Overview Mounts (drill-down)", page_icon="🔎", layout="wide")
st.title("🔎 Overview Mounts")

# ── engine cache ─────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _eng_cached() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def eng() -> Engine:
    return _eng_cached()

# ── helpers ──────────────────────────────────────────────────────────────────
def _columns(schema: str, name: str) -> Set[str]:
    q = text("""
      select column_name
      from information_schema.columns
      where table_schema=:s and table_name=:n
      order by ordinal_position
    """)
    with eng().begin() as cx:
        df = pd.read_sql(q, cx, params={"s": schema, "n": name})
    return set(df["column_name"].tolist())


def _mounts_summary_for_day(day: Optional[pd.Timestamp]) -> pd.DataFrame:
    """
    One row per mount_code with summary metrics + clutch lineage/genotype pretties.
    Robust to optional mount columns; filters by day using timestamp when present,
    else parses from code.
    """
    cols = _columns("public", "mounts")

    sel_mounting = "m.mounting_orientation" if "mounting_orientation" in cols else "NULL::text"
    sel_n_top    = "m.n_top"                if "n_top"                in cols else "NULL::int"
    sel_n_bottom = "m.n_bottom"             if "n_bottom"             in cols else "NULL::int"
    sel_notes    = "m.notes"                if "notes"                in cols else "NULL::text"

    sel_mounted_at = "m.mounted_at"   if "mounted_at"   in cols else "NULL::timestamptz"
    sel_time_mount = "m.time_mounted" if "time_mounted" in cols else "NULL::timestamptz"
    sel_created_at = "m.created_at"   if "created_at"   in cols else "NULL::timestamptz"

    date_candidates = ["mounted_at", "time_mounted", "created_at", "imaged_at"]
    date_col = next((c for c in date_candidates if c in cols), None)
    day_param = pd.Timestamp(day).date() if day is not None else None

    if day_param and date_col:
        where_day = f"WHERE DATE(m.{date_col}) = :d"
        params = {"d": day_param}
    elif day_param:
        where_day = "WHERE (regexp_match(m.mount_code, '^MT-(\\d{8})-'))[1] = to_char(:d::date,'YYYYMMDD')"
        params = {"d": day_param}
    else:
        where_day, params = "", {}

    sql = text(f"""
    WITH base AS (
      SELECT
        m.id                    AS mount_id,
        m.mount_code,
        ci.clutch_instance_code AS clutch_code,
        {sel_mounting}          AS mounting_orientation,
        {sel_n_top}             AS n_top,
        {sel_n_bottom}          AS n_bottom,
        {sel_notes}             AS notes,
        {sel_mounted_at}        AS mounted_at_raw,
        {sel_time_mount}        AS time_mounted_raw,
        {sel_created_at}        AS created_at_raw,
        COALESCE({sel_mounted_at}, {sel_time_mount}, {sel_created_at}) AS mounted_ts
      FROM public.mounts m
      LEFT JOIN public.clutch_instances ci ON ci.id = m.clutch_instance_id
      {where_day}
    ),
    slots AS (
      SELECT p.mount_code, p.red_intensity, p.green_intensity, p.orientation
      FROM public.v_mount_slot_annotations_pivot p
      INNER JOIN base b ON b.mount_code = p.mount_code
    ),
    orient_mode AS (
      SELECT s.mount_code,
             (SELECT orientation
              FROM (
                SELECT orientation, COUNT(*) AS c
                FROM slots s2
                WHERE s2.mount_code = s.mount_code
                GROUP BY orientation
                ORDER BY c DESC NULLS LAST, orientation ASC
                LIMIT 1
              ) x) AS orientation_mode
      FROM slots s
      GROUP BY s.mount_code
    )
    SELECT
      b.mount_code,
      b.clutch_code,
      b.mounting_orientation,
      b.n_top,
      b.n_bottom,
      b.notes,
      b.mounted_ts AS mounted_at,
      COUNT(s.red_intensity)                    AS slots,
      ROUND(AVG(s.red_intensity)::numeric, 3)   AS red_avg,
      MIN(s.red_intensity)                      AS red_min,
      MAX(s.red_intensity)                      AS red_max,
      ROUND(AVG(s.green_intensity)::numeric, 3) AS green_avg,
      MIN(s.green_intensity)                    AS green_min,
      MAX(s.green_intensity)                    AS green_max,
      om.orientation_mode,
      vci.clutch_genotype_pretty,
      vci.clutch_genotype_fusions,
      vci.clutch_treatments_codes,
      vci.clutch_treatments_names,
      vci.clutch_treatments_fusions,
      vci.clutch_lineage_pretty,
      vci.clutch_lineage_fusions_pretty,
      vci.clutch_lineage_full_fusions_pretty
    FROM base b
    LEFT JOIN slots s        ON s.mount_code = b.mount_code
    LEFT JOIN orient_mode om ON om.mount_code = b.mount_code
    LEFT JOIN public.v_clutch_instances vci ON vci.clutch_code = b.clutch_code
    GROUP BY
      b.mount_code, b.clutch_code, b.mounting_orientation, b.n_top, b.n_bottom, b.notes, b.mounted_ts, om.orientation_mode,
      vci.clutch_genotype_pretty, vci.clutch_genotype_fusions,
      vci.clutch_treatments_codes, vci.clutch_treatments_names, vci.clutch_treatments_fusions,
      vci.clutch_lineage_pretty, vci.clutch_lineage_fusions_pretty, vci.clutch_lineage_full_fusions_pretty
    ORDER BY b.mounted_ts DESC NULLS LAST, b.mount_code;
    """)

    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return df


def _slots_for_mount(mount_code: str) -> pd.DataFrame:
    """Returns per-slot annotations for a given mount."""
    sql = text("""
      SELECT
        mount_code,
        well,
        subwell,
        red_intensity,
        green_intensity,
        orientation,
        notes,
        annotations_last_at
      FROM public.v_mount_slot_annotations_pivot
      WHERE mount_code = :code
      ORDER BY CASE WHEN well='top' THEN 0 ELSE 1 END, subwell ASC
    """)
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"code": mount_code})
    return df


# ── filters ──────────────────────────────────────────────────────────────────
today = utc_today()
with st.form("filters"):
    c1, c2 = st.columns([1, 2])
    with c1:
        day = st.date_input("Day", value=today)
    with c2:
        q = st.text_input("Search (mount/clutch/genotype/treatments contains)", value="")
    submitted = st.form_submit_button("Apply", width="stretch")

# toggles
if hasattr(st, "segmented_control"):
    SHOW_TREATMENTS_AS = st.segmented_control(
        "Lineage display", options=["codes","names","fusions"], default="codes", key="mounts_tx_label_mode"
    )
    SHOW_GENOTYPE_AS = st.segmented_control(
        "Genotype display", options=["codes","fusions"], default="codes", key="mounts_gx_label_mode"
    )
else:
    SHOW_TREATMENTS_AS = st.selectbox(
        "Lineage display", options=["codes","names","fusions"], index=0, key="mounts_tx_label_mode"
    )
    SHOW_GENOTYPE_AS = st.selectbox(
        "Genotype display", options=["codes","fusions"], index=0, key="mounts_gx_label_mode"
    )

# ── main summary ─────────────────────────────────────────────────────────────
summary = _mounts_summary_for_day(day)

if q.strip():
    _q = q.strip().lower()
    summary = summary[
        summary["mount_code"].fillna("").str.lower().str.contains(_q) |
        summary["clutch_code"].fillna("").str.lower().str.contains(_q) |
        summary["clutch_genotype_pretty"].fillna("").str.lower().str.contains(_q) |
        summary["clutch_genotype_fusions"].fillna("").str.lower().str.contains(_q) |
        summary["clutch_treatments_codes"].fillna("").str.lower().str.contains(_q) |
        summary["clutch_treatments_names"].fillna("").str.lower().str.contains(_q) |
        summary["clutch_treatments_fusions"].fillna("").str.lower().str.contains(_q)
    ]

if summary.empty:
    st.info("No mounts found for this filter.")
    st.stop()

# orientation fallback
summary["mounting_orientation"] = summary["mounting_orientation"].fillna(summary.get("orientation_mode"))

# lineage display
if SHOW_TREATMENTS_AS == "codes":
    summary["lineage_display"] = summary["clutch_lineage_pretty"]
elif SHOW_TREATMENTS_AS == "names":
    names = summary["clutch_treatments_names"].fillna("")
    geno  = summary["clutch_genotype_pretty"].fillna("")
    summary["lineage_display"] = names.where(names.eq(""), names + " > ") + geno
else:
    summary["lineage_display"] = summary["clutch_lineage_full_fusions_pretty"].fillna(
        summary["clutch_lineage_fusions_pretty"]
    )

# genotype display
if SHOW_GENOTYPE_AS == "codes":
    summary["genotype_display"] = summary["clutch_genotype_pretty"]
else:
    summary["genotype_display"] = summary["clutch_genotype_fusions"].fillna(summary["clutch_genotype_pretty"])

# columns to display
preferred = [
    "mount_code","clutch_code","mounted_at",
    "orientation_mode","mounting_orientation",
    "red_avg","red_min","red_max","green_avg","green_min","green_max",
    "n_top","n_bottom","notes",
    "genotype_display","clutch_genotype_pretty","clutch_genotype_fusions",
    "lineage_display","clutch_lineage_pretty","clutch_lineage_fusions_pretty",
]

cols_show = [c for c in preferred if c in summary.columns and summary[c].notna().any()]
for key in ["mount_code","clutch_code","mounted_at"]:
    if key in cols_show:
        cols_show.insert(0, cols_show.pop(cols_show.index(key)))

grid = summary[cols_show].copy()

# numeric formatting
for c in ["red_avg","green_avg"]:
    if c in grid.columns:
        grid[c] = pd.to_numeric(grid[c], errors="coerce").round(3)
for c in ["red_min","red_max","green_min","green_max"]:
    if c in grid.columns:
        grid[c] = pd.to_numeric(grid[c], errors="coerce")

# interactive grid
grid.insert(0, "✓ Select", False)
picker = st.data_editor(
    grid,
    hide_index=True,
    width="stretch",
    num_rows="fixed",
    column_config={
        "✓ Select":  st.column_config.CheckboxColumn("✓", default=False),
        "mounted_at": st.column_config.DatetimeColumn("mounted_at", format="YYYY-MM-DD HH:mm"),
        "red_avg":   st.column_config.NumberColumn("red_avg",   format="%.3f"),
        "green_avg": st.column_config.NumberColumn("green_avg", format="%.3f"),
        "genotype_display": st.column_config.TextColumn("Genotype (display)", disabled=True),
        "lineage_display":  st.column_config.TextColumn("Lineage (display)",  disabled=True),
    },
    key="overview_mounts_drill_v3",
)

sel_series = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False)
if sel_series.sum() == 0 and len(grid.index) == 1:
    sel_series.iloc[0] = True
selected = grid[sel_series].reset_index(drop=True)

# ── slot details ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("Per-slot annotations for selected mount")

if selected.empty:
    st.info("Select one row above to view its 8 slots.")
else:
    mount_code = str(selected.iloc[0]["mount_code"])
    slots_df = _slots_for_mount(mount_code)
    if slots_df.empty:
        st.info(f"No slot annotations yet for {mount_code}.")
    else:
        st.caption(f"Mount: **{mount_code}** — {len(slots_df)} slot row(s)")
        st.dataframe(slots_df, hide_index=True, use_container_width=True)