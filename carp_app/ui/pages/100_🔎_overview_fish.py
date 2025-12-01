# carp_app/ui/pages/100_🔎_overview_fish.py
from __future__ import annotations

import pathlib
import sys
from typing import Dict, List, Optional, Any

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

from carp_app.ui.lib.page_engine import engine  # central DB engine hook

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview: Fish",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 Overview: Fish (lines → instances)")


# ───────── engine helper ─────────
def _eng() -> Engine:
    return engine()


def _norm(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None


def _maybe(d: Dict[str, Any], row: pd.Series, col: str, label: Optional[str] = None):
    if col in row.index:
        d[label or col] = row[col]


# ════════════════════════════════════════════════════════
# STEP 1 — MODERN LINES (aggregate over v11_fish_instance_star)
# ════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def load_lines() -> pd.DataFrame:
    """
    One row per modern line.

    We aggregate over:
      • v11_fish_instance_star fis  (modern fish instances)
      • fish_instances_v10 fi      (birthday per instance)
      • fish_lines fl              (nickname, background, stage)
    """
    sql = text(
        """
        SELECT
          fis.line_id::text                  AS line_id,
          fis.line_code                      AS line_code,
          MAX(fl.nickname)                   AS line_nickname,
          MAX(fl.genetic_background)         AS genetic_background,
          MAX(fl.line_building_stage)        AS line_building_stage,
          MIN(fi.birthday)                   AS first_birthday,
          MAX(fi.birthday)                   AS last_birthday,
          COUNT(*)                           AS n_instances,
          MAX(fis.genotype_pretty)           AS genotype_pretty
        FROM public.v11_fish_instance_star fis
        JOIN public.fish_instances_v10 fi
          ON fi.id = fis.fish_instance_id
        JOIN public.fish_lines fl
          ON fl.id = fis.line_id
        GROUP BY
          fis.line_id,
          fis.line_code
        ORDER BY
          fis.line_code;
        """
    )
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx)

    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")

    return df.fillna("")


lines_df = load_lines()

st.subheader("Step 1 — Lines")

if lines_df.empty:
    st.info("No modern lines found.")
    st.stop()

with st.form("line_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        search_text = st.text_input(
            "Search (line_code / nickname / background / genotype)",
            value="",
            key="line_search_text",
        )
    with c2:
        min_instances = st.number_input(
            "Min instances per line (optional)",
            min_value=0,
            value=0,
            step=1,
        )
    _ = st.form_submit_button("Apply", use_container_width=True)

filtered = lines_df.copy()

if search_text.strip():
    q = search_text.strip().lower()
    mask = (
        filtered["line_code"].str.lower().str.contains(q, na=False)
        | filtered["line_nickname"].str.lower().str.contains(q, na=False)
        | filtered["genetic_background"].str.lower().str.contains(q, na=False)
        | filtered["genotype_pretty"].str.lower().str.contains(q, na=False)
    )
    filtered = filtered[mask]

if min_instances > 0:
    filtered = filtered[filtered["n_instances"] >= min_instances]

if filtered.empty:
    st.warning("No lines match the current filters.")
    st.stop()

st.caption(f"{len(filtered)} line(s)")

lines_display = filtered[
    [
        "line_id",
        "line_code",
        "line_nickname",
        "genetic_background",
        "line_building_stage",
        "genotype_pretty",
        "n_instances",
        "first_birthday",
        "last_birthday",
    ]
].copy()

lines_display.insert(0, "✓", False)

edited_lines = st.data_editor(
    lines_display,
    use_container_width=True,
    num_rows="fixed",
    key="lines_editor_v11_overview",
    column_config={
        "✓": st.column_config.CheckboxColumn("Select", width=60),
        "line_id": st.column_config.Column("line_id", width=0, disabled=True),
        "line_code": st.column_config.TextColumn("Line code", disabled=True),
        "line_nickname": st.column_config.TextColumn(
            "Nickname", disabled=True, width="large"
        ),
        "genetic_background": st.column_config.TextColumn(
            "Background", disabled=True
        ),
        "line_building_stage": st.column_config.TextColumn(
            "Stage", disabled=True
        ),
        "genotype_pretty": st.column_config.TextColumn(
            "Genotype", disabled=True, width="large"
        ),
        "n_instances": st.column_config.NumberColumn(
            "n instances", disabled=True
        ),
        "first_birthday": st.column_config.DateColumn(
            "First birthday", disabled=True
        ),
        "last_birthday": st.column_config.DateColumn(
            "Last birthday", disabled=True
        ),
    },
    hide_index=True,
)

selected_line_rows = edited_lines[edited_lines["✓"]]
if not selected_line_rows.empty:
    selected_line_id = selected_line_rows.iloc[0]["line_id"]
else:
    selected_line_id = lines_display.iloc[0]["line_id"]

st.caption("Select one line above to see its linked instances.")


# ════════════════════════════════════════════════════════
# STEP 2 — INSTANCES FOR SELECTED LINE
# ════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def load_instances_for_line(line_id: str) -> pd.DataFrame:
    """
    For a given line_id, pull all modern fish instances.

    We join v11_fish_instance_star with fish_instances_v10
    to get birthday (per instance).
    """
    sql = text(
        """
        SELECT
          fis.*,
          fi.birthday
        FROM public.v11_fish_instance_star fis
        JOIN public.fish_instances_v10 fi
          ON fi.id = fis.fish_instance_id
        WHERE fis.line_id = :line_id
        ORDER BY fi.birthday NULLS LAST, fis.fish_code;
        """
    )
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"line_id": line_id})

    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")

    return df.fillna("")


st.markdown("---")
st.subheader("Step 2 — Instances for selected line")

if not selected_line_id:
    st.caption("No line selected or no lines in this group.")
else:
    inst_df = load_instances_for_line(selected_line_id)

    if inst_df.empty:
        st.caption("No instances found for this line.")
    else:
        desired_order = [
            "fish_code",
            "genetic_background",
            "genotype_pretty",
            "birthday",
            "line_instance_code",
            "line_code",
            "fish_group_code",
        ]

        cols_present = [c for c in desired_order if c in inst_df.columns]

        view_inst = inst_df.copy()
        view_inst.insert(0, "✓ Select", False)

        column_order = ["✓ Select"] + cols_present

        cfg: Dict[str, Any] = {
            "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        }
        if "fish_code" in inst_df.columns:
            cfg["fish_code"] = st.column_config.TextColumn(
                "FSH code", disabled=True
            )
        if "genetic_background" in inst_df.columns:
            cfg["genetic_background"] = st.column_config.TextColumn(
                "Background", disabled=True
            )
        if "genotype_pretty" in inst_df.columns:
            cfg["genotype_pretty"] = st.column_config.TextColumn(
                "Genotype", disabled=True, width="large"
            )
        if "birthday" in inst_df.columns:
            cfg["birthday"] = st.column_config.DateColumn(
                "Birthday", disabled=True
            )
        if "line_instance_code" in inst_df.columns:
            cfg["line_instance_code"] = st.column_config.TextColumn(
                "LINE instance code", disabled=True
            )
        if "line_code" in inst_df.columns:
            cfg["line_code"] = st.column_config.TextColumn(
                "LINE code", disabled=True
            )
        if "fish_group_code" in inst_df.columns:
            cfg["fish_group_code"] = st.column_config.TextColumn(
                "Legacy fish_group (if any)", disabled=True
            )

        grid_inst = st.data_editor(
            view_inst[column_order],
            key=f"instances_overview_{selected_line_id}",
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config=cfg,
        )

        st.download_button(
            "⬇︎ Download instances for selected line (CSV)",
            data=inst_df.to_csv(index=False).encode("utf-8"),
            file_name="fish_instances_for_line.csv",
            type="secondary",
            mime="text/csv",
        )

        st.divider()
        st.subheader("Instance details")

        sel_idxs: List[int] = []
        if "✓ Select" in grid_inst.columns:
            sel_idxs = (
                grid_inst.index[grid_inst["✓ Select"] == True]
                .to_series()
                .tolist()
            )

        if not sel_idxs:
            st.caption("Select one or more instances above to see details.")
        elif len(sel_idxs) == 1:
            r = grid_inst.loc[sel_idxs[0]]
            tab1, tab2 = st.tabs(["Overview", "Line / legacy"])

            with tab1:
                d: Dict[str, Any] = {}
                _maybe(d, r, "fish_code")
                _maybe(d, r, "genetic_background", "background")
                _maybe(d, r, "genotype_pretty")
                _maybe(d, r, "birthday")
                st.write(d)

            with tab2:
                d: Dict[str, Any] = {}
                _maybe(d, r, "line_code")
                _maybe(d, r, "line_instance_code")
                _maybe(d, r, "fish_group_code", "legacy fish_group")
                st.write(d)
        else:
            subset = grid_inst.loc[sel_idxs].reset_index(drop=True)
            cols_summary = [
                c
                for c in [
                    "genetic_background",
                    "genotype_pretty",
                ]
                if c in subset.columns
            ]
            st.write("Summary for selected instances:")
            st.dataframe(
                subset[cols_summary],
                use_container_width=True,
            )