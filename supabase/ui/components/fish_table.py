import streamlit as st
import pandas as pd


def render_select_table(df: pd.DataFrame, key: str = "fish_table"):
    df = df.copy()
    if "select" not in df.columns:
        df.insert(0, "select", False)

    view_cols = [
        "select",
        "fish_name",
        "auto_fish_code",
        "line_building_stage",
        "tank",
        "status",
        "transgenes",
        "alleles",
    ]
    view_cols = [c for c in view_cols if c in df.columns]

    edited = st.data_editor(
        df[view_cols],
        hide_index=True,
        use_container_width=True,
        disabled=[c for c in view_cols if c != "select"],
        column_config={"select": st.column_config.CheckboxColumn("✓")},
        key=key,
    )
    mask = edited["select"].to_numpy() if "select" in edited else []
    selected_ids = df.loc[mask, "id"].tolist() if len(df) else []
    return selected_ids, edited
