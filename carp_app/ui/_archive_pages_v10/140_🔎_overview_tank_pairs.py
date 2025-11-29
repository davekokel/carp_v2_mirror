from __future__ import annotations

import os
import pathlib
import sys
from typing import Optional

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
from carp_app.ui.lib.page_engine import engine as _engine


# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview: Tank pairs",
    page_icon="🔍",
    layout="wide",
)
st.title("🔍 Overview: Tank pairs")


# ───────── helpers ─────────
def _eng() -> Engine:
    return _engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ───────── query: tank pair overview (v11, via star view) ─────────
def load_tank_pairs(q: Optional[str], limit: int) -> pd.DataFrame:
    qn = _norm(q)
    params = {
        "q": qn if qn else None,
        "ql": f"%{qn}%" if qn else None,
        "lim": int(limit),
    }

    sql = text(
        """
        SELECT
          tp.id::text        AS tank_pair_id,
          tp.tank_pair_code,
          tp.created_at,
          tp.active_from,

          mt.tank_code       AS mother_tank_code,
          mf.fish_code       AS mother_fish_code,
          mf.treatments_and_transgenes
                             AS mother_treatments_and_transgenes,
          mf.all_fluor_tag_rollup
                             AS mother_all_fluor_tag_rollup,
          mf.all_organelle_fluor_rollup
                             AS mother_all_organelle_fluor_rollup,

          ft.tank_code       AS father_tank_code,
          ff.fish_code       AS father_fish_code,
          ff.treatments_and_transgenes
                             AS father_treatments_and_transgenes,
          ff.all_fluor_tag_rollup
                             AS father_all_fluor_tag_rollup,
          ff.all_organelle_fluor_rollup
                             AS father_all_organelle_fluor_rollup

        FROM public.tank_pairs tp
        JOIN public.tanks mt
          ON mt.id = tp.mother_tank_id
        JOIN public.tanks ft
          ON ft.id = tp.father_tank_id
        LEFT JOIN public.v11_fish_instance_star mf
          ON mf.tank_id = mt.id
        LEFT JOIN public.v11_fish_instance_star ff
          ON ff.tank_id = ft.id
        WHERE (:q IS NULL)
           OR (
                tp.tank_pair_code ILIKE :ql
             OR mt.tank_code      ILIKE :ql
             OR ft.tank_code      ILIKE :ql
             OR mf.fish_code      ILIKE :ql
             OR ff.fish_code      ILIKE :ql
           )
        ORDER BY tp.created_at DESC NULLS LAST, tp.tank_pair_code
        LIMIT :lim
        """
    )

    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    # normalize string columns
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")

    return df


# ───────── UI ─────────
with st.form("tank_pair_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        q_raw = st.text_input(
            "Search (tank_pair_code / tank_code / fish_code)",
            "",
        )
    with c2:
        lim = int(
            st.number_input(
                "Limit",
                min_value=10,
                max_value=5000,
                value=500,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply")

df = load_tank_pairs(q_raw, lim)

if df.empty:
    st.info("No tank pairs found for current filters.")
else:
    st.caption(f"{len(df)} tank_pair(s)")

    # Column order: IDs, tanks, fish codes, then v11 semantics
    cols = [
        "tank_pair_id",
        "tank_pair_code",
        "created_at",
        "active_from",
        "mother_tank_code",
        "mother_fish_code",
        "father_tank_code",
        "father_fish_code",
        "mother_treatments_and_transgenes",
        "mother_all_fluor_tag_rollup",
        "mother_all_organelle_fluor_rollup",
        "father_treatments_and_transgenes",
        "father_all_fluor_tag_rollup",
        "father_all_organelle_fluor_rollup",
    ]
    cols = [c for c in cols if c in df.columns]
    df_display = df[cols].copy()

    st.data_editor(
        df_display,
        key="tank_pairs_overview_v11",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "tank_pair_id":     st.column_config.TextColumn("ID", disabled=True),
            "tank_pair_code":   st.column_config.TextColumn("Tank pair code", disabled=True),
            "mother_tank_code": st.column_config.TextColumn("Mother tank", disabled=True),
            "mother_fish_code": st.column_config.TextColumn("Mother fish (FSH code)", disabled=True),
            "father_tank_code": st.column_config.TextColumn("Father tank", disabled=True),
            "father_fish_code": st.column_config.TextColumn("Father fish (FSH code)", disabled=True),
            "created_at":       st.column_config.DatetimeColumn("Created at", disabled=True),
            "active_from":      st.column_config.DatetimeColumn("Active from", disabled=True),
        },
    )

    st.download_button(
        "⬇︎ Download tank_pairs overview (CSV)",
        data=df_display.to_csv(index=False).encode("utf-8"),
        file_name="tank_pairs_overview.csv",
        type="secondary",
        mime="text/csv",
    )