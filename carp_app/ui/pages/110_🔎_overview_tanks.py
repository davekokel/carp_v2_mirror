#110_🔎_overview_tanks.py
from __future__ import annotations

import pathlib
import sys
from typing import Optional, Dict, Any, List

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
from carp_app.ui.lib.page_engine import engine  # core engine hook


# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview: Tanks",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 Overview: Tanks")


# ───────── engine (centralized) ─────────
def _eng() -> Engine:
    """Thin wrapper around the core page_engine hook."""
    return engine()


def _norm(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ════════════════════════════════════════════════════════
# FILTER BAR
# ════════════════════════════════════════════════════════
with st.form("tank_filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([3, 1, 0.7])
    with c1:
        q_raw = st.text_input(
            "Search (tank_code / fish_code / status)",
            "",
        )
    with c2:
        status_choice = st.selectbox(
            "Status",
            ["all", "active", "retired"],
            index=0,
        )
    with c3:
        lim = int(
            st.number_input(
                "Limit",
                min_value=50,
                max_value=5000,
                value=500,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply", key="tanks_apply")

q = _norm(q_raw)
status_filter = status_choice if status_choice != "all" else None

# ════════════════════════════════════════════════════════
# MAIN QUERY: v_tanks_overview
# ════════════════════════════════════════════════════════
where: List[str] = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  tank_code ILIKE :ql"
        " OR fish_code ILIKE :ql"
        " OR COALESCE(status,'') ILIKE :ql"
        ")"
    )

if status_filter:
    params["status"] = status_filter
    where.append("status = :status")

where_sql = " AND ".join(where)

sql = text(
    f"""
    SELECT
      tank_id,
      tank_code,
      fish_code,
      status,
      created_at
    FROM public.v_tanks_overview
    WHERE {where_sql}
    ORDER BY created_at DESC, tank_code
    LIMIT :lim;
    """
)

with _eng().begin() as cx:
    df_tanks = pd.read_sql(sql, cx, params=params)

df_tanks = df_tanks.fillna("")
st.caption(f"{len(df_tanks)} tank(s)")

# ════════════════════════════════════════════════════════
# MAIN TABLE (core tank fields + selection)
# ════════════════════════════════════════════════════════
if df_tanks.empty:
    st.info("No tanks match the current filters.")
    st.stop()

view = df_tanks.copy()
view.insert(0, "✓ Select", False)

grid = st.data_editor(
    view,
    key="tanks_overview_core",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=[
        "✓ Select",
        "tank_code",
        "status",
        "fish_code",
        "created_at",
    ],
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "tank_code": st.column_config.TextColumn("Tank code", disabled=True),
        "status": st.column_config.TextColumn("Status", disabled=True),
        "fish_code": st.column_config.TextColumn("Fish code", disabled=True),
        "created_at": st.column_config.DatetimeColumn("Created at", disabled=True),
    },
)

st.download_button(
    "⬇︎ Download tanks overview (CSV)",
    data=df_tanks.to_csv(index=False).encode("utf-8"),
    file_name="tanks_overview.csv",
    type="secondary",
    mime="text/csv",
)

# ════════════════════════════════════════════════════════
# DRILL-DOWN: FISH IN SELECTED TANK(S)
# ════════════════════════════════════════════════════════
st.divider()
st.subheader("Fish in selected tank(s)")

selected_tanks = grid[grid["✓ Select"]] if not df_tanks.empty else pd.DataFrame()

if selected_tanks.empty:
    st.caption("Select one or more tanks above to see their fish instances.")
else:
    selected_tank_codes = [
        tc for tc in selected_tanks["tank_code"].tolist() if tc
    ]

    if not selected_tank_codes:
        st.info("Selected tanks have no tank_code; nothing to show.")
    else:
        placeholders = ", ".join([f":tc{i}" for i in range(len(selected_tank_codes))])

        sql_fish = text(
            f"""
            SELECT
              fis.fish_code,
              fis.genetic_background,
              fis.genotype_pretty,
              fis.birthday,
              fis.tank_status,
              fis.tank_code,
              fis.line_code,
              fis.group_code,
              fis.line_nickname,
              fis.fluor_codes,
              fis.tag_codes,
              fis.organelle_fluors
            FROM public.v11_fish_instance_star fis
            WHERE fis.tank_code IN ({placeholders})
            ORDER BY fis.tank_code, fis.fish_code;
            """
        )
        params_fish = {f"tc{i}": tc for i, tc in enumerate(selected_tank_codes)}

        with _eng().begin() as cx:
            df_fish = pd.read_sql(sql_fish, cx, params=params_fish)

        if df_fish.empty:
            st.info("No fish instances found in the selected tank(s).")
        else:
            # Core fish fields in tank context:
            # fish_code, genetic_background, genotype_pretty, birthday, status, tank_code
            st.dataframe(
                df_fish[
                    [
                        "tank_code",
                        "tank_status",
                        "fish_code",
                        "genetic_background",
                        "genotype_pretty",
                        "birthday",
                        "line_code",
                        "group_code",
                        "line_nickname",
                        "fluor_codes",
                        "tag_codes",
                        "organelle_fluors",
                    ]
                ],
                use_container_width=True,
            )