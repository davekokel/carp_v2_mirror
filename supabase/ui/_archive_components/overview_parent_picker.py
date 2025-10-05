from __future__ import annotations
# supabase/ui/components/overview_parent_picker.py
import pandas as pd
import streamlit as st
# Usage:
#   from supabase.ui/components/overview_parent_picker import render_parent_picker
#
#   # With selection (New Cross page):
#   selected_ids = render_parent_picker(engine, load_overview_df, enable_selection=True, max_select=2, key="parent_picker_nc")
#
#   # Without selection (Overview page, just a viewer):
#   render_parent_picker(engine, load_overview_df, enable_selection=False, key="overview_grid")
#
# You pass in:
#   - engine (kept for parity; not directly used here)
#   - load_overview_df: callable(engine) -> DataFrame (same source as Overview page)
#
# Handled/expected columns (component will normalize if some are missing):
#   id (uuid/str), fish_code, name (or fish_name or nickname), created_at
#   transgene_base_code_filled, allele_code_filled
# Optional filter columns (auto-detected if present):
#   batch_label, line_building_stage, created_by, date_of_birth
def _normalize_overview_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # ID as string for Streamlit/pyarrow
    if "id" not in df.columns:
        raise ValueError("Overview DF must include 'id' column")
    df["id"] = df["id"].astype(str)
    # Normalize name
    if "name" not in df.columns:
        for cand in ("fish_name", "nickname"):
            if cand in df.columns:
                df.rename(columns={cand: "name"}, inplace=True)
                break
    if "name" not in df.columns:
        df["name"] = None
    # Genotype summaries
    if "transgene_base_code_filled" not in df.columns:
        df["transgene_base_code_filled"] = None
    if "allele_code_filled" not in df.columns:
        df["allele_code_filled"] = df.get("allele_name_filled", None)
    # Created timestamp
    if "created_at" not in df.columns:
        df["created_at"] = pd.Timestamp.utcnow()
    # Clean display of empties
    for col in ("name", "transgene_base_code_filled", "allele_code_filled"):
        if col in df.columns:
            df[col] = df[col].astype("string").fillna("")
    return df
def render_parent_picker(
    engine,
    load_overview_df,
    *,
    enable_selection: bool = True,
    max_select: int | None = 2,
    key: str = "parent_picker",
) -> list[str] | None:
    """
    Renders a search+filters + grid. If enable_selection=True, returns a list[str] of selected ids.
    If enable_selection=False, returns None (viewer mode).
    """
    # Load
    df = load_overview_df(engine)
    if isinstance(df, tuple):
        df = df[0]
    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info("No fish found. Upload CSV on the Overview/Upload page first.")
        return [] if enable_selection else None

    df = _normalize_overview_df(df)

    # ---------------------- Search + Filters ----------------------
    # Text search columns
    search_cols = [c for c in [
        "fish_code", "name", "transgene_base_code_filled", "allele_code_filled",
        "line_building_stage", "created_by", "batch_label"
    ] if c in df.columns]

    st.subheader("Overview")
    q = st.text_input("Search", placeholder="name, nickname, strain, genotype, RNA/plasmid notes…").strip()

    with st.expander("Filters", expanded=False):
        selected_batches = []
        selected_stages = []
        selected_creators = []
        dob_from = dob_to = None

        if "batch_label" in df.columns:
            batches = sorted([b for b in df["batch_label"].dropna().unique().tolist() if b != ""])
            selected_batches = st.multiselect("Batch label", batches, default=[])

        if "line_building_stage" in df.columns:
            stages = sorted([s for s in df["line_building_stage"].dropna().unique().tolist() if s != ""])
            selected_stages = st.multiselect("Line building stage", stages, default=[])

        if "created_by" in df.columns:
            creators = sorted([u for u in df["created_by"].dropna().unique().tolist() if u != ""])
            selected_creators = st.multiselect("Created by", creators, default=[])

        if "date_of_birth" in df.columns:
            col1, col2 = st.columns(2)
            dob_from = col1.date_input("DOB from", value=None)
            dob_to   = col2.date_input("DOB to",   value=None)

        if st.button("Reset results"):
            st.session_state.pop(key, None)
            st.rerun()

    # Apply search
    fdf = df
    if q and search_cols:
        qlower = q.lower()
        mask = False
        for col in search_cols:
            mask = mask | fdf[col].astype(str).str.lower().str.contains(qlower, na=False)
        fdf = fdf[mask]

    # Apply filters
    if "batch_label" in fdf.columns and selected_batches:
        fdf = fdf[fdf["batch_label"].isin(selected_batches)]
    if "line_building_stage" in fdf.columns and selected_stages:
        fdf = fdf[fdf["line_building_stage"].isin(selected_stages)]
    if "created_by" in fdf.columns and selected_creators:
        fdf = fdf[fdf["created_by"].isin(selected_creators)]
    if "date_of_birth" in fdf.columns and (dob_from or dob_to):
        if dob_from:
            fdf = fdf[pd.to_datetime(fdf["date_of_birth"], errors="coerce") >= pd.to_datetime(dob_from)]
        if dob_to:
            fdf = fdf[pd.to_datetime(fdf["date_of_birth"], errors="coerce") <= pd.to_datetime(dob_to)]

    # ---------------------- Grid ----------------------
    pick_cols = [c for c in [
        "fish_code", "name",
        "transgene_base_code_filled", "allele_code_filled",
        "line_building_stage", "created_by", "date_of_birth",
        "created_at",
    ] if c in fdf.columns]

    table = fdf[pick_cols].copy()

    if enable_selection:
        table.insert(0, "select", False)  # checkbox first
        table.index = fdf["id"]           # hide id as index
        st.markdown("#### Pick exactly two parents below (check the boxes):")
        edited = st.data_editor(
            table,
            key=key,
            use_container_width=True,
            hide_index=True,
            column_config={
                "select": st.column_config.CheckboxColumn("Select", help="Check to choose this fish"),
                "fish_code": st.column_config.TextColumn("Fish code"),
                "name": st.column_config.TextColumn("Name"),
                "transgene_base_code_filled": st.column_config.TextColumn("Transgene base codes"),
                "allele_code_filled": st.column_config.TextColumn("Allele numbers"),
                "line_building_stage": st.column_config.TextColumn("Stage"),
                "created_by": st.column_config.TextColumn("Created by"),
                "date_of_birth": st.column_config.DateColumn("Date of birth"),
                "created_at": st.column_config.DatetimeColumn("Created"),
            },
        )
        selected_ids = [str(i) for i, val in edited["select"].items() if val]
        if max_select and len(selected_ids) > max_select:
            st.warning(f"Please select at most {max_select} rows.")
        return selected_ids

    # Viewer mode (no selection)
    table.index = fdf["id"]
    st.dataframe(
        table,
        use_container_width=True,
    )
    return None