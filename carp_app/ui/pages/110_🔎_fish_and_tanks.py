from __future__ import annotations

import sys
import pathlib
from typing import Any, Dict, List, Optional

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

from carp_app.ui.lib.page_engine import engine as _engine

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


def eng() -> Engine:
    return _engine()


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


def load_tanks() -> pd.DataFrame:
    """
    Tank overview with fish + line + genotype + treatment labels.
    """
    sql = text(
        """
        SELECT
          t.tank_code,
          t.status,
          fi.fish_code,
          fi.nickname          AS fish_nickname,
          fi.instance_stage,
          fi.birthday,
          fi.genetic_background,
          fl.line_code,
          fl.nickname          AS line_nickname,
          fl.line_building_stage,
          fis.genotype_pretty,
          fis.genotype_tg_style,
          fis.genotype_fluortag_style,
          fis.genotype_fluororganelle_style,
          fis.treatment_codes,
          fis.treatment_label_tg_style,
          fis.treatment_label_fluortag_style,
          fis.treatment_label_fluororganelle_style,
          t.created_at
        FROM public.tanks t
        JOIN public.fish_instances_v10 fi
          ON fi.id = t.fish_instance_id
        JOIN public.fish_lines fl
          ON fl.id = fi.line_id
        LEFT JOIN public.v11_fish_instance_star_labels fis
          ON fis.fish_instance_id = fi.id
        ORDER BY t.tank_code, fi.fish_code;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx)

    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df.fillna("")


tanks_df = load_tanks()

# ───────── filters ─────────
with st.form("tank_filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        search = st.text_input(
            "Search (tank_code / fish nickname / line / genotype / status / treatment)",
            "",
            key="tank_search_text",
        )
    with c2:
        status_filter = st.selectbox(
            "Status",
            options=["all", "active", "retired"],
            index=0,
            key="tank_status_filter",
        )
    with c3:
        lim = int(
            st.number_input(
                "Limit",
                min_value=50,
                max_value=5000,
                value=500,
                step=50,
                key="tank_limit",
            )
        )
    _ = st.form_submit_button("Apply", use_container_width=True)

df = tanks_df.copy()

if status_filter != "all":
    df = df[df["status"] == status_filter]

if search.strip():
    q = search.strip().lower()
    mask = (
        df["tank_code"].str.lower().str.contains(q, na=False)
        | df["fish_code"].str.lower().str.contains(q, na=False)
        | df["fish_nickname"].str.lower().str.contains(q, na=False)
        | df["line_code"].str.lower().str.contains(q, na=False)
        | df["line_nickname"].str.lower().str.contains(q, na=False)
        | df["genotype_pretty"].str.lower().str.contains(q, na=False)
        | df["genotype_tg_style"].str.lower().str.contains(q, na=False)
        | df["treatment_codes"].str.lower().str.contains(q, na=False)
        | df["treatment_label_tg_style"].str.lower().str.contains(q, na=False)
        | df["status"].str.lower().str.contains(q, na=False)
    )
    df = df[mask]

if df.empty:
    st.info("No tanks match these filters.")
else:
    df = df.head(lim)
    st.caption(f"{len(df)} tank(s)")

    view = df[
        [
            "tank_code",
            "status",
            "fish_code",
            "fish_nickname",
            "line_code",
            "line_nickname",
            "genetic_background",
            "instance_stage",
            "line_building_stage",
            "birthday",
            "genotype_tg_style",
            "treatment_codes",
            "treatment_label_tg_style",
            "created_at",
        ]
    ].copy()

    view.insert(0, "✓", False)

    grid = st.data_editor(
        view,
        key="tanks_overview_v11",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "✓": st.column_config.CheckboxColumn("Select", width=60),
            "tank_code": st.column_config.TextColumn("Tank code", disabled=True),
            "status": st.column_config.TextColumn("Status", disabled=True),
            "fish_code": st.column_config.TextColumn("FSH code", disabled=True),
            "fish_nickname": st.column_config.TextColumn(
                "Fish nickname", disabled=True
            ),
            "line_code": st.column_config.TextColumn("Line code", disabled=True),
            "line_nickname": st.column_config.TextColumn(
                "Line nickname", disabled=True, width="large"
            ),
            "genetic_background": st.column_config.TextColumn(
                "Background", disabled=True
            ),
            "instance_stage": st.column_config.TextColumn("Stage", disabled=True),
            "line_building_stage": st.column_config.TextColumn(
                "Line type", disabled=True
            ),
            "birthday": st.column_config.DateColumn("Birthday", disabled=True),
            "genotype_tg_style": st.column_config.TextColumn(
                "Genotype (tg-style)", disabled=True, width="large"
            ),
            "treatment_codes": st.column_config.TextColumn(
                "Treatment code(s)", disabled=True, width="large"
            ),
            "treatment_label_tg_style": st.column_config.TextColumn(
                "Treatment • genotype", disabled=True, width="large"
            ),
            "created_at": st.column_config.DatetimeColumn(
                "Created at", disabled=True
            ),
        },
    )

    st.download_button(
        "⬇︎ Download tanks overview (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="tanks_overview_v11.csv",
        type="secondary",
        mime="text/csv",
    )

st.markdown("---")
st.subheader("Fish in selected tank(s)")

st.caption("Select one or more tanks above to see their instances.")