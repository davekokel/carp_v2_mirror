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
    Tank overview with fish + line + genotype + treatment labels via v_tanks_overview.
    """
    sql = text(
        """
        SELECT
          tank_id,
          tank_code,
          status,
          fish_code,
          fish_nickname,
          instance_stage,
          birthday,
          genetic_background,
          line_code,
          line_nickname,
          line_building_stage,
          genotype_tg_style,
          genotype_fluortag_style,
          genotype_fluororganelle_style,
          treatment_codes,
          treatment_label_tg_style,
          treatment_label_fluortag_style,
          treatment_label_fluororganelle_style,
          treatment_or_genotype_tg_style,
          treatment_or_genotype_fluortag_style,
          treatment_or_genotype_fluororganelle_style,
          created_at
        FROM public.v_tanks_overview
        ORDER BY created_at DESC NULLS LAST, tank_code;
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
    _ = st.form_submit_button("Apply")

df = tanks_df.copy()

# status filter
if status_filter != "all" and "status" in df.columns:
    df = df[df["status"] == status_filter]

# search filter
if search.strip():
    q = search.strip().lower()
    mask_parts: List[pd.Series] = []

    def add_mask(col: str) -> None:
        if col in df.columns:
            mask_parts.append(df[col].str.lower().str.contains(q, na=False))

    add_mask("tank_code")
    add_mask("fish_code")
    add_mask("fish_nickname")
    add_mask("line_code")
    add_mask("line_nickname")
    add_mask("genetic_background")
    add_mask("genotype_tg_style")
    add_mask("genotype_fluortag_style")
    add_mask("genotype_fluororganelle_style")
    add_mask("treatment_codes")
    add_mask("treatment_label_tg_style")
    add_mask("treatment_label_fluortag_style")
    add_mask("treatment_label_fluororganelle_style")
    add_mask("treatment_or_genotype_tg_style")
    add_mask("treatment_or_genotype_fluortag_style")
    add_mask("treatment_or_genotype_fluororganelle_style")
    add_mask("status")

    if mask_parts:
        mask = mask_parts[0]
        for m in mask_parts[1:]:
            mask = mask | m
        df = df[mask]

if df.empty:
    st.info("No tanks match these filters.")
else:
    df = df.head(lim)
    st.caption(f"{len(df)} tank(s)")

    # Show genotype-only, treatment-only, and combined label columns
    desired_cols = [
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
        # genotype-only
        "genotype_tg_style",
        "genotype_fluortag_style",
        "genotype_fluororganelle_style",
        # treatment-only
        "treatment_codes",
        "treatment_label_tg_style",
        "treatment_label_fluortag_style",
        "treatment_label_fluororganelle_style",
        # combined “treatment > genotype”
        "treatment_or_genotype_tg_style",
        "treatment_or_genotype_fluortag_style",
        "treatment_or_genotype_fluororganelle_style",
        "created_at",
    ]

    present_cols = [c for c in desired_cols if c in df.columns]
    view = df[present_cols].copy()
    view.insert(0, "✓", False)

    column_config: Dict[str, Any] = {
        "✓": st.column_config.CheckboxColumn("Select", width=60),
    }

    if "tank_code" in view.columns:
        column_config["tank_code"] = st.column_config.TextColumn(
            "Tank code", disabled=True
        )
    if "status" in view.columns:
        column_config["status"] = st.column_config.TextColumn("Status", disabled=True)
    if "fish_code" in view.columns:
        column_config["fish_code"] = st.column_config.TextColumn(
            "FSH code", disabled=True
        )
    if "fish_nickname" in view.columns:
        column_config["fish_nickname"] = st.column_config.TextColumn(
            "Fish nickname", disabled=True
        )
    if "line_code" in view.columns:
        column_config["line_code"] = st.column_config.TextColumn(
            "Line code", disabled=True
        )
    if "line_nickname" in view.columns:
        column_config["line_nickname"] = st.column_config.TextColumn(
            "Line nickname", disabled=True, width="large"
        )
    if "genetic_background" in view.columns:
        column_config["genetic_background"] = st.column_config.TextColumn(
            "Background", disabled=True
        )
    if "instance_stage" in view.columns:
        column_config["instance_stage"] = st.column_config.TextColumn(
            "Stage", disabled=True
        )
    if "line_building_stage" in view.columns:
        column_config["line_building_stage"] = st.column_config.TextColumn(
            "Line type", disabled=True
        )
    if "birthday" in view.columns:
        column_config["birthday"] = st.column_config.DateColumn(
            "Birthday", disabled=True
        )

    # genotype-only labels
    if "genotype_tg_style" in view.columns:
        column_config["genotype_tg_style"] = st.column_config.TextColumn(
            "Genotype (tg-style)", disabled=True, width="large"
        )
    if "genotype_fluortag_style" in view.columns:
        column_config["genotype_fluortag_style"] = st.column_config.TextColumn(
            "Genotype (fluor-tag)", disabled=True, width="large"
        )
    if "genotype_fluororganelle_style" in view.columns:
        column_config["genotype_fluororganelle_style"] = st.column_config.TextColumn(
            "Genotype (organelle)", disabled=True, width="large"
        )

    # treatment-only labels
    if "treatment_codes" in view.columns:
        column_config["treatment_codes"] = st.column_config.TextColumn(
            "Treatment code(s)", disabled=True, width="large"
        )
    if "treatment_label_tg_style" in view.columns:
        column_config["treatment_label_tg_style"] = st.column_config.TextColumn(
            "Treatment (tg-style)", disabled=True, width="large"
        )
    if "treatment_label_fluortag_style" in view.columns:
        column_config["treatment_label_fluortag_style"] = st.column_config.TextColumn(
            "Treatment (fluor-tag)", disabled=True, width="large"
        )
    if "treatment_label_fluororganelle_style" in view.columns:
        column_config["treatment_label_fluororganelle_style"] = (
            st.column_config.TextColumn(
                "Treatment (organelle)", disabled=True, width="large"
            )
        )

    # combined labels
    if "treatment_or_genotype_tg_style" in view.columns:
        column_config["treatment_or_genotype_tg_style"] = st.column_config.TextColumn(
            "Treatment • genotype (tg)", disabled=True, width="large"
        )
    if "treatment_or_genotype_fluortag_style" in view.columns:
        column_config["treatment_or_genotype_fluortag_style"] = (
            st.column_config.TextColumn(
                "Treatment • genotype (fluor-tag)", disabled=True, width="large"
            )
        )
    if "treatment_or_genotype_fluororganelle_style" in view.columns:
        column_config["treatment_or_genotype_fluororganelle_style"] = (
            st.column_config.TextColumn(
                "Treatment • genotype (organelle)", disabled=True, width="large"
            )
        )

    if "created_at" in view.columns:
        column_config["created_at"] = st.column_config.DatetimeColumn(
            "Created at", disabled=True
        )

    grid = st.data_editor(
        view,
        key="tanks_overview_v11",
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        column_config=column_config,
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