# carp_app/ui/pages/115_🔎_overview_fish_groups.py
from __future__ import annotations

import os
import sys
import pathlib
from typing import Optional

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
    def require_app_unlock():
        ...


from carp_app.ui.lib.app_ctx import get_engine as _create_engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview Fish Groups",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 v10 Fish Groups Overview")


def get_engine() -> Engine:
    return _create_engine()


# ───────── queries (use the view for groups) ─────────
GROUPS_SQL = text(
    """
    SELECT
      fish_group_id,
      group_code,
      genotype_key,
      basecode_genotype,
      fluor_tag,
      organelle_fluor,
      n_lines,
      n_instances,
      first_birthday,
      last_birthday
    FROM public.v_fish_groups_overview
    ORDER BY group_code
    """
)

LINES_SQL = text(
    """
    SELECT
      fl.id::text AS line_id,
      fl.line_code,
      fl.nickname,
      fl.genetic_background,
      fl.line_building_stage,
      fl.group_instance_code,
      COUNT(DISTINCT fi.id) AS n_instances,
      MIN(fi.birthday) AS first_birthday,
      MAX(fi.birthday) AS last_birthday
    FROM public.fish_lines fl
    LEFT JOIN public.fish_instances_v10 fi
      ON fi.line_id = fl.id
    WHERE fl.fish_group_id = :fish_group_id
    GROUP BY
      fl.id,
      fl.line_code,
      fl.nickname,
      fl.genetic_background,
      fl.line_building_stage,
      fl.group_instance_code
    ORDER BY fl.line_code
    """
)

INSTANCES_SQL = text(
    """
    SELECT
      fi.id::text AS instance_id,
      fi.line_instance_code,
      fi.fish_code,
      fi.birthday,
      fi.created_at
    FROM public.fish_instances_v10 fi
    WHERE fi.line_id = :line_id
    ORDER BY fi.birthday, fi.line_instance_code
    """
)


@st.cache_data(show_spinner=False)
def load_groups() -> pd.DataFrame:
    with get_engine().begin() as cx:
        df = pd.read_sql(GROUPS_SQL, cx)
    return df


@st.cache_data(show_spinner=False)
def load_lines_for_group(fish_group_id: str) -> pd.DataFrame:
    with get_engine().begin() as cx:
        df = pd.read_sql(LINES_SQL, cx, params={"fish_group_id": fish_group_id})
    return df


@st.cache_data(show_spinner=False)
def load_instances_for_line(line_id: str) -> pd.DataFrame:
    with get_engine().begin() as cx:
        df = pd.read_sql(INSTANCES_SQL, cx, params={"line_id": line_id})
    return df


# ───────── filters (lines-overview style) ─────────
groups_df = load_groups()
if groups_df.empty:
    st.info("No fish groups found.")
    st.stop()

with st.form("group_filters"):
    c1, c2, c3 = st.columns([3, 1, 1])

    with c1:
        search_text = st.text_input(
            "Search (group_code / genotype / fluor / organelle)",
            value="",
            key="group_search_text",
        )

    with c2:
        min_instances = st.number_input(
            "Min instances (optional)",
            min_value=0,
            value=0,
            step=1,
        )

    with c3:
        st.write("")
        submitted = st.form_submit_button("Apply")

filtered = groups_df.copy()

if search_text.strip():
    q = search_text.strip().lower()
    mask = (
        filtered["group_code"].str.lower().str.contains(q, na=False)
        | filtered["genotype_key"].str.lower().str.contains(q, na=False)
        | filtered["basecode_genotype"].str.lower().str.contains(q, na=False)
        | filtered["fluor_tag"].fillna("").str.lower().str.contains(q, na=False)
        | filtered["organelle_fluor"].fillna("").str.lower().str.contains(q, na=False)
    )
    filtered = filtered[mask]

if min_instances > 0:
    filtered = filtered[filtered["n_instances"] >= min_instances]

if filtered.empty:
    st.warning("No groups match the current filters.")
    st.stop()

st.write(f"{len(filtered)} group(s)")

# ───────── groups table with checkbox column ─────────
groups_display = filtered[
    [
        "fish_group_id",
        "basecode_genotype",  # genotype first
        "fluor_tag",          # fluor::tag(tag_pos)
        "organelle_fluor",    # organelle-fluor
        "group_code",
        "n_lines",
        "n_instances",
        "first_birthday",
        "last_birthday",
        "genotype_key",       # raw key for debugging
    ]
].copy()

groups_display.insert(0, "✓", False)

edited_groups = st.data_editor(
    groups_display,
    use_container_width=True,
    num_rows="fixed",
    key="groups_editor",
    column_config={
        "✓": st.column_config.CheckboxColumn("Select", width=60),
        "fish_group_id": st.column_config.Column("fish_group_id", width=0, disabled=True),
        "basecode_genotype": st.column_config.Column("Genotype (basecode set)"),
        "fluor_tag": st.column_config.Column("fluor::tag(tag_pos)"),
        "organelle_fluor": st.column_config.Column("organelle-fluor"),
    },
    hide_index=True,
)

selected_group_rows = edited_groups[edited_groups["✓"]]
if not selected_group_rows.empty:
    selected_group_id = selected_group_rows.iloc[0]["fish_group_id"]
else:
    selected_group_id = groups_display.iloc[0]["fish_group_id"]

st.markdown(
    "Select one group above to see its linked lines and linked instances."
)

csv_groups = groups_display.drop(columns=["✓", "fish_group_id"]).to_csv(index=False)
st.download_button(
    "📥 Download v10 fish groups (CSV)",
    data=csv_groups,
    file_name="v10_fish_groups.csv",
    mime="text/csv",
)

st.markdown("---")

# ───────── linked lines for selected group ─────────
st.subheader("Linked lines in selected group")

lines_df = load_lines_for_group(selected_group_id)
if lines_df.empty:
    st.caption("No lines found for this group.")
    st.stop()

lines_display = lines_df[
    [
        "line_id",
        "line_code",
        "nickname",
        "genetic_background",
        "line_building_stage",
        "group_instance_code",
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
    key=f"lines_editor_{selected_group_id}",
    column_config={
        "✓": st.column_config.CheckboxColumn("Select", width=60),
        "line_id": st.column_config.Column("line_id", width=0, disabled=True),
    },
    hide_index=True,
)

selected_line_rows = edited_lines[edited_lines["✓"]]
if not selected_line_rows.empty:
    selected_line_id = selected_line_rows.iloc[0]["line_id"]
else:
    selected_line_id = lines_display.iloc[0]["line_id"]

st.markdown("Select one line above to see its linked instances.")

st.markdown("---")

# ───────── linked instances for selected line ─────────
st.subheader("Linked instances for selected line")

instances_df = load_instances_for_line(selected_line_id)
if instances_df.empty:
    st.caption("No instances found for this line.")
else:
    st.dataframe(
        instances_df[
            [
                "line_instance_code",
                "fish_code",
                "birthday",
                "created_at",
            ]
        ],
        use_container_width=True,
    )