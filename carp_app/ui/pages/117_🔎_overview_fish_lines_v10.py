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
    page_title="CARP — Fish Lines Overview",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 Fish Lines Overview")


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

# ───────── query fish_lines + v11_line_allele_rollups + fish_instances_v10 ─────────
where = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  b.line_code        ILIKE :ql"
        " OR b.nickname       ILIKE :ql"
        " OR b.genotype_pretty ILIKE :ql"
        ")"
    )

if bg:
    params["bg"] = f"%{bg}%"
    where.append("b.genetic_background ILIKE :bg")

if stage_filter:
    params["stage"] = stage_filter
    where.append("b.line_building_stage = :stage")

where_sql = " AND ".join(where)

sql = text(f"""
    WITH base AS (
      SELECT
        fl.id                  AS line_id,
        fl.line_code           AS line_code,
        fl.nickname            AS nickname,
        fl.genetic_background  AS genetic_background,
        fl.line_building_stage AS line_building_stage,
        fl.created_at          AS created_at,
        la.allele_label_rollup AS genotype_pretty
      FROM public.fish_lines fl
      LEFT JOIN public.v11_line_allele_rollups la
        ON la.line_id = fl.id
    )
    SELECT
      b.line_code,
      b.nickname,
      b.genetic_background,
      b.line_building_stage,
      b.genotype_pretty,
      b.created_at,
      (
        SELECT COUNT(*)
        FROM public.fish_instances_v10 fi
        WHERE fi.line_id = b.line_id
      ) AS n_fish_instances
    FROM base b
    WHERE {where_sql}
    ORDER BY b.created_at DESC NULLS LAST, b.line_code
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
    key="fish_lines_overview_v11",
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
    "⬇︎ Download fish lines (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="fish_lines_overview.csv",
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