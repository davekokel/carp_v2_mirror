from __future__ import annotations

import sys
import pathlib
from typing import Dict, Any

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ───────── repo bootstrap ─────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock() -> None:
        ...
from carp_app.ui.lib.page_engine import engine as _engine  # core hook


# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🔎 Summary dashboard",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 CARP summary dashboard")


def eng() -> Engine:
    return _engine()


def _exists_table(schema: str, name: str) -> bool:
    with eng().begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = :s AND table_name = :n
                LIMIT 1;
                """
            ),
            cx,
            params={"s": schema, "n": name},
        )
    return not df.empty


def _exists_view(schema: str, name: str) -> bool:
    with eng().begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT 1
                FROM information_schema.views
                WHERE table_schema = :s AND table_name = :n
                UNION ALL
                SELECT 1
                FROM pg_catalog.pg_matviews
                WHERE schemaname = :s AND matviewname = :n
                LIMIT 1;
                """
            ),
            cx,
            params={"s": schema, "n": name},
        )
    return not df.empty


@st.cache_data(show_spinner=False)
def load_summary_data() -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    with eng().begin() as cx:
        # 1) n_active tanks per week (past 30 days)
        if _exists_table("public", "tanks"):
            df_tanks = pd.read_sql(
                text(
                    """
                    SELECT
                      date_trunc('week', created_at)::date AS week_start,
                      count(*) FILTER (WHERE lower(trim(status)) = 'active') AS n_active_tanks
                    FROM public.tanks
                    WHERE created_at >= current_date - interval '30 days'
                    GROUP BY 1
                    ORDER BY 1;
                    """
                ),
                cx,
            )
            out["tanks_week"] = df_tanks
        else:
            out["tanks_week"] = pd.DataFrame(columns=["week_start", "n_active_tanks"])

        # 2–5) total plasmids, fluors, tags, fusions
        def _count_if_exists(table: str) -> int:
            if not _exists_table("public", table):
                return 0
            return int(
                pd.read_sql(
                    text(f"SELECT count(*) AS n FROM public.{table};"),
                    cx,
                )["n"][0]
            )

        out["n_plasmids"] = _count_if_exists("plasmids")
        out["n_fluors"] = _count_if_exists("fluors")
        out["n_tags"] = _count_if_exists("tags")
        out["n_fusions"] = _count_if_exists("fusions")

        # 6) n_total plates per week (past 30 days)
        if _exists_table("public", "imaging_plates"):
            df_plates = pd.read_sql(
                text(
                    """
                    SELECT
                      date_trunc('week', experiment_date)::date AS week_start,
                      count(*) AS n_plates
                    FROM public.imaging_plates
                    WHERE experiment_date >= current_date - interval '30 days'
                    GROUP BY 1
                    ORDER BY 1;
                    """
                ),
                cx,
            )
            out["plates_week"] = df_plates
        else:
            out["plates_week"] = pd.DataFrame(columns=["week_start", "n_plates"])

        # 7) n_total rois per week (past 30 days) via v_roi_overview if present
        if _exists_view("public", "v_roi_overview"):
            df_rois = pd.read_sql(
                text(
                    """
                    SELECT
                      date_trunc('week', experiment_date)::date AS week_start,
                      count(*) AS n_rois
                    FROM public.v_roi_overview
                    WHERE experiment_date >= current_date - interval '30 days'
                    GROUP BY 1
                    ORDER BY 1;
                    """
                ),
                cx,
            )
            out["rois_week"] = df_rois
        else:
            out["rois_week"] = pd.DataFrame(columns=["week_start", "n_rois"])

    return out


data = load_summary_data()

# ───────── headline metrics ─────────
st.subheader("Headlines", anchor=False)
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    latest_tanks = data["tanks_week"]["n_active_tanks"].iloc[-1] if not data["tanks_week"].empty else 0
    st.metric("Active tanks (last week)", latest_tanks)

with c2:
    st.metric("Total plasmids", data["n_plasmids"])

with c3:
    st.metric("Total fluors", data["n_fluors"])

with c4:
    st.metric("Total tags", data["n_tags"])

with c5:
    st.metric("Total fusions", data["n_fusions"])

st.markdown("---")

# ───────── sparklines / small charts ─────────
st.subheader("Past 30 days — trends", anchor=False)

row1 = st.columns(3)
row2 = st.columns(2)

# 1) tanks per week
with row1[0]:
    st.caption("Active tanks per week")
    df_t = data["tanks_week"]
    if df_t.empty:
        st.info("No tank data for the last 30 days.")
    else:
        df_plot = df_t.set_index("week_start")[["n_active_tanks"]]
        st.line_chart(df_plot)

# 6) plates per week
with row1[1]:
    st.caption("Imaging plates per week")
    df_p = data["plates_week"]
    if df_p.empty:
        st.info("No imaging plates in the last 30 days.")
    else:
        df_plot = df_p.set_index("week_start")[["n_plates"]]
        st.line_chart(df_plot)

# 7) rois per week
with row1[2]:
    st.caption("ROIs per week")
    df_r = data["rois_week"]
    if df_r.empty:
        st.info("No ROIs in the last 30 days.")
    else:
        df_plot = df_r.set_index("week_start")[["n_rois"]]
        st.line_chart(df_plot)

# Optional: static totals as tiny sparklines (plasmids/fluors/tags/fusions don’t change weekly here,
# but we can show them as single-point charts if desired; for now, just leave them as metrics.)

# Could add extra space for future trends
with row2[0]:
    st.caption("Reserved for future metric")
with row2[1]:
    st.caption("Reserved for future metric")