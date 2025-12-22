from __future__ import annotations

import sys
import pathlib
from typing import Dict, Any

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

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

from carp_app.ui.lib.app_ctx import get_engine


sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — 🔎 Summary", page_icon="🔎", layout="wide")
st.title("🔎 Summary dashboard")

_ENGINE: Engine = get_engine()


@st.cache_data(ttl=60, show_spinner=False)
def _exists_view(schema: str, name: str) -> bool:
    with _ENGINE.begin() as cx:
        v = cx.execute(
            text(
                """
                select exists(
                  select 1
                  from information_schema.views
                  where table_schema=:s and table_name=:t
                )
                """
            ),
            {"s": schema, "t": name},
        ).scalar()
    return bool(v)


@st.cache_data(ttl=60, show_spinner=False)
def _exists_table(schema: str, name: str) -> bool:
    with _ENGINE.begin() as cx:
        v = cx.execute(
            text(
                """
                select exists(
                  select 1
                  from information_schema.tables
                  where table_schema=:s and table_name=:t
                )
                """
            ),
            {"s": schema, "t": name},
        ).scalar()
    return bool(v)


@st.cache_data(ttl=60, show_spinner=False)
def load_summary_data() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    with _ENGINE.begin() as cx:
        if _exists_table("public", "tanks"):
            out["tanks_week"] = pd.read_sql(
                text(
                    """
                    SELECT
                      date_trunc('week', created_at)::date AS week_start,
                      count(*) FILTER (WHERE lower(coalesce(status,'')) = 'active') AS n_active_tanks
                    FROM public.tanks
                    WHERE created_at >= now() - interval '30 days'
                    GROUP BY 1
                    ORDER BY 1;
                    """
                ),
                cx,
            )
        else:
            out["tanks_week"] = pd.DataFrame(columns=["week_start", "n_active_tanks"])

        if _exists_table("public", "constructs"):
            out["n_plasmids"] = int(
                cx.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM public.constructs
                        WHERE lower(coalesce(construct_kind,'')) = 'plasmid';
                        """
                    )
                ).scalar()
                or 0
            )
        else:
            out["n_plasmids"] = 0

        if _exists_table("public", "fluors"):
            out["n_fluors"] = int(cx.execute(text("SELECT count(*) FROM public.fluors;")).scalar() or 0)
        else:
            out["n_fluors"] = 0

        if _exists_table("public", "tags"):
            out["n_tags"] = int(cx.execute(text("SELECT count(*) FROM public.tags;")).scalar() or 0)
        else:
            out["n_tags"] = 0

        if _exists_table("public", "fusions"):
            out["n_fusions"] = int(cx.execute(text("SELECT count(*) FROM public.fusions;")).scalar() or 0)
        else:
            out["n_fusions"] = 0

        if _exists_table("public", "imaging_plates"):
            out["plates_week"] = pd.read_sql(
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
        else:
            out["plates_week"] = pd.DataFrame(columns=["week_start", "n_plates"])

        need_roi = all(
            _exists_table("public", t)
            for t in ("imaging_roi_annotations", "imaging_slots", "imaging_plates")
        )
        if need_roi:
            out["rois_week"] = pd.read_sql(
                text(
                    """
                    SELECT
                      date_trunc('week', p.experiment_date)::date AS week_start,
                      count(*) AS n_rois
                    FROM public.imaging_roi_annotations ira
                    JOIN public.imaging_slots s
                      ON s.id = ira.slot_id
                    JOIN public.imaging_plates p
                      ON p.id = s.plate_id
                    WHERE p.experiment_date >= current_date - interval '30 days'
                    GROUP BY 1
                    ORDER BY 1;
                    """
                ),
                cx,
            )
        else:
            out["rois_week"] = pd.DataFrame(columns=["week_start", "n_rois"])

    return out


data = load_summary_data()

st.subheader("Headlines", anchor=False)
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    latest_tanks = data["tanks_week"]["n_active_tanks"].iloc[-1] if not data["tanks_week"].empty else 0
    st.metric("Active tanks (last week)", int(latest_tanks))

with c2:
    st.metric("Total plasmids", int(data["n_plasmids"]))

with c3:
    st.metric("Total fluors", int(data["n_fluors"]))

with c4:
    st.metric("Total tags", int(data["n_tags"]))

with c5:
    st.metric("Total fusions", int(data["n_fusions"]))

st.markdown("---")

st.subheader("Past 30 days — trends", anchor=False)

row1 = st.columns(3)
row2 = st.columns(2)

with row1[0]:
    st.caption("Active tanks per week")
    df_t = data["tanks_week"]
    if df_t.empty:
        st.info("No tank data for the last 30 days.")
    else:
        st.line_chart(df_t.set_index("week_start")[["n_active_tanks"]])

with row1[1]:
    st.caption("Imaging plates per week")
    df_p = data["plates_week"]
    if df_p.empty:
        st.info("No imaging plates in the last 30 days.")
    else:
        st.line_chart(df_p.set_index("week_start")[["n_plates"]])

with row1[2]:
    st.caption("ROIs per week")
    df_r = data["rois_week"]
    if df_r.empty:
        st.info("No ROIs in the last 30 days.")
    else:
        st.line_chart(df_r.set_index("week_start")[["n_rois"]])

with row2[0]:
    st.caption("Reserved for future metric")
with row2[1]:
    st.caption("Reserved for future metric")
