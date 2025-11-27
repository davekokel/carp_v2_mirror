from __future__ import annotations

import os
import pathlib
import sys
from typing import Optional, Dict, Any

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
    def require_app_unlock():
        ...
from carp_app.ui.lib.app_ctx import get_engine


# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — v10 Fish Lines Overview",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 v10 Fish Lines Overview")


# ───────── engine (cached) ─────────
@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL")
    if not url:
        st.error("DB_URL is not set")
        st.stop()
    return get_engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ───────── filters ─────────
with st.form("fish_lines_filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 0.8])
    with c1:
        q_raw = st.text_input(
            "Search (line_code / nickname / genotype)",
            "",
        )
    with c2:
        bg_raw = st.text_input(
            "Background contains (optional)",
            "",
        )
    with c3:
        stage_choice = st.selectbox(
            "Stage",
            ["(any)", "P0", "F1", "F2", "founder", "stable"],
            index=0,
        )
    with c4:
        lim = int(
            st.number_input(
                "Limit",
                min_value=50,
                max_value=5000,
                value=1000,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply")

q = _norm(q_raw)
bg = _norm(bg_raw)
stage_filter = stage_choice if stage_choice != "(any)" else None

# ───────── query v10_fish_lines_overview + n_fish_instances ─────────
where = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  line_code         ILIKE :ql"
        " OR nickname        ILIKE :ql"
        " OR genotype_pretty ILIKE :ql"
        ")"
    )

if bg:
    params["bg"] = f"%{bg}%"
    where.append("genetic_background ILIKE :bg")

if stage_filter:
    params["stage"] = stage_filter
    where.append("line_building_stage = :stage")

where_sql = " AND ".join(where)

sql = text(f"""
    SELECT
      v.line_code,
      v.nickname,
      v.genetic_background,
      v.line_building_stage,
      v.genotype_pretty,
      v.created_at,
      (
        SELECT COUNT(*)
        FROM public.fish_instances_v10 fi
        JOIN public.fish_lines fl ON fl.id = fi.line_id
        WHERE fl.line_code = v.line_code
      ) AS n_fish_instances
    FROM public.v10_fish_lines_overview v
    WHERE {where_sql}
    ORDER BY v.created_at DESC NULLS LAST, v.line_code
    LIMIT :lim
""")

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

df = df.fillna("")
st.caption(f"{len(df)} line(s)")

# ───────── table ─────────
view = df.copy()
view.insert(0, "✓ Select", False)

grid = st.data_editor(
    view,
    key="v10_fish_lines_overview_grid",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=[
        "✓ Select",
        "line_code",
        "nickname",
        "genetic_background",
        "line_building_stage",
        "genotype_pretty",
        "n_fish_instances",
        "created_at",
    ],
    column_config={
        "✓ Select":            st.column_config.CheckboxColumn("✓", default=False),
        "line_code":           st.column_config.TextColumn("Line code", disabled=True),
        "nickname":            st.column_config.TextColumn("Nickname", disabled=True, width="large"),
        "genetic_background":  st.column_config.TextColumn("Background", disabled=True),
        "line_building_stage": st.column_config.TextColumn("Stage", disabled=True),
        "genotype_pretty":     st.column_config.TextColumn("Genotype", disabled=True, width="large"),
        "n_fish_instances":    st.column_config.NumberColumn("n fish instances", disabled=True),
        "created_at":          st.column_config.DatetimeColumn("Created", disabled=True),
    },
)

st.download_button(
    "⬇︎ Download v10 fish lines (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="v10_fish_lines_overview.csv",
    type="secondary",
    mime="text/csv",
)

# ───────── linked instances section ─────────
selected = grid[grid["✓ Select"]]

if not selected.empty:
    selected_line_codes = selected["line_code"].tolist()

    placeholders = ", ".join([f":lc{i}" for i in range(len(selected_line_codes))])
    sql_instances = text(
        f"""
        SELECT
            fl.line_code,
            fl.nickname AS line_nickname,
            fl.genetic_background,
            fl.line_building_stage,
            fi.fish_code,
            fi.line_instance_code,
            fi.birthday,
            fi.created_at
        FROM public.fish_instances_v10 fi
        JOIN public.fish_lines fl
          ON fl.id = fi.line_id
        WHERE fl.line_code IN ({placeholders})
        ORDER BY fl.line_code, fi.fish_code
        """
    )
    params_instances = {f"lc{i}": lc for i, lc in enumerate(selected_line_codes)}

    with _eng().begin() as cx:
        df_inst = pd.read_sql(sql_instances, cx, params=params_instances)

    st.subheader("Linked fish instances")
    if df_inst.empty:
        st.info("No instances found for the selected line(s).")
    else:
        st.dataframe(
            df_inst,
            use_container_width=True,
        )
else:
    st.caption("Select one or more lines above to see their linked fish instances.")