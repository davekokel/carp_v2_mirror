from __future__ import annotations

import sys
import pathlib

import pandas as pd
import streamlit as st
from sqlalchemy import text

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

from carp_app.ui.lib.page_engine import engine

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Link imaging ROIs to fish",
    page_icon="🧬",
    layout="wide",
)

st.title("🧬 Link imaging ROIs to fish")

with engine().begin() as cx:
    label_rows = cx.execute(
        text(
            """
            SELECT
              ir.dataset,
              ir.fish_label,
              count(*) AS n_rois,
              bool_or(ir.fish_id IS NOT NULL) AS has_fish_id
            FROM public.imaging_rois ir
            GROUP BY ir.dataset, ir.fish_label
            ORDER BY ir.dataset, ir.fish_label
            """
        )
    ).mappings().all()

if not label_rows:
    st.info("No imaging ROIs found.")
    st.stop()

labels_df = pd.DataFrame(label_rows)

st.subheader("Distinct (dataset, fish_label) combinations")
st.dataframe(labels_df, use_container_width=True)

st.sidebar.header("Mapping controls")

datasets = ["(all)"] + sorted(labels_df["dataset"].dropna().unique().tolist())
dataset_choice = st.sidebar.selectbox("Filter by dataset", datasets)

only_unmapped = st.sidebar.checkbox("Show only labels with no fish_id", value=True)

df_filtered = labels_df.copy()
if dataset_choice != "(all)":
    df_filtered = df_filtered[df_filtered["dataset"] == dataset_choice]
if only_unmapped:
    df_filtered = df_filtered[~df_filtered["has_fish_id"]]

st.subheader("Labels to map")
st.dataframe(df_filtered, use_container_width=True)

st.markdown("---")

st.subheader("Assign a fish to a label")

sel_dataset = st.text_input("Dataset", value=(dataset_choice if dataset_choice != "(all)" else ""))
sel_label = st.text_input("Fish label (from imaging)", "")

fish_search = st.text_input("Search fish by code / nickname", "")

candidate_fish = []
if fish_search.strip():
    with engine().begin() as cx:
        candidate_fish = cx.execute(
            text(
                """
                SELECT
                  id,
                  fish_code,
                  COALESCE(nickname, '') AS nickname,
                  COALESCE(genetic_background, '') AS genetic_background
                FROM public.fish
                WHERE fish_code ILIKE :q
                   OR nickname ILIKE :q
                ORDER BY fish_code
                LIMIT 50
                """
            ),
            {"q": f"%{fish_search.strip()}%"},
        ).mappings().all()

if candidate_fish:
    cand_df = pd.DataFrame(candidate_fish)
    st.write("Candidate fish:")
    st.dataframe(cand_df, use_container_width=True)
else:
    if fish_search.strip():
        st.info("No fish matched that search string.")

fish_code_choice = st.text_input("Fish code to assign", "")

if st.button("Link this (dataset, fish_label) to fish_code"):
    if not sel_dataset or not sel_label:
        st.error("Please fill in Dataset and Fish label.")
    elif not fish_code_choice:
        st.error("Please enter a fish_code to assign.")
    else:
        with engine().begin() as cx:
            fish_row = cx.execute(
                text(
                    """
                    SELECT id
                    FROM public.fish
                    WHERE fish_code = :fish_code
                    """
                ),
                {"fish_code": fish_code_choice},
            ).mappings().first()

            if not fish_row:
                st.error(f"No fish found with fish_code='{fish_code_choice}'.")
            else:
                fish_id = fish_row["id"]
                result = cx.execute(
                    text(
                        """
                        UPDATE public.imaging_rois
                        SET fish_id = :fish_id
                        WHERE dataset = :dataset
                          AND fish_label = :fish_label
                        """
                    ),
                    {
                        "fish_id": fish_id,
                        "dataset": sel_dataset,
                        "fish_label": sel_label,
                    },
                )
                st.success(
                    f"Updated {result.rowcount} imaging ROIs "
                    f"for dataset='{sel_dataset}', fish_label='{sel_label}' "
                    f"to fish_id corresponding to fish_code='{fish_code_choice}'."
                )