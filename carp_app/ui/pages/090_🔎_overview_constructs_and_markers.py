from __future__ import annotations

import pathlib
import sys
from typing import Dict, List, Optional

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
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine  # ← core engine hook
# from carp_app.lib.time import utc_now  # import when needed

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview: Constructs & Markers",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 Overview: Constructs & Markers")


# ───────── engine (centralized) ─────────
def _eng() -> Engine:
    """Thin wrapper around the core page_engine hook."""
    return engine()


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


# ───────── tabs ─────────
tab_constructs, tab_fluors, tab_tags, tab_dyes = st.tabs(
    ["Constructs", "Fluors", "Tags", "Dyes"]
)

# ════════════════════════════════════════════════════════
# TAB 1 — CONSTRUCTS
# ════════════════════════════════════════════════════════
with tab_constructs:
    st.subheader("Constructs")

    with st.form("construct_filters", clear_on_submit=False):
        c1, c2, c3 = st.columns([3, 1.3, 0.8])
        with c1:
            q_raw = st.text_input(
                "Search (code / name / kind / resistance / description / fusions / organelles)",
                "",
            )
        with c2:
            kind_choice = st.selectbox(
                "Kind contains…",
                ["(any)", "plasmid", "rna", "crispr"],
                index=0,
            )
        with c3:
            lim_constructs = int(
                st.number_input(
                    "Limit",
                    min_value=50,
                    max_value=5000,
                    value=1000,
                    step=50,
                    key="constructs_limit",
                )
            )
        _ = st.form_submit_button("Apply")

    q = _norm(q_raw)
    kind_token = kind_choice if kind_choice != "(any)" else None

    where = ["1=1"]
    params: Dict[str, object] = {"lim": lim_constructs}

    if q:
        params["ql"] = f"%{q}%"
        where.append(
            "("
            "  construct_code ILIKE :ql"
            " OR construct_name ILIKE :ql"
            " OR COALESCE(construct_kind,'') ILIKE :ql"
            " OR COALESCE(resistance,'') ILIKE :ql"
            " OR COALESCE(description,'') ILIKE :ql"
            " OR COALESCE(fusion_pretty,'') ILIKE :ql"
            " OR COALESCE(organelle_fluors,'') ILIKE :ql"
            ")"
        )

    if kind_token:
        params["kind_like"] = f"%{kind_token}%"
        where.append("construct_kind ILIKE :kind_like")

    where_sql = " AND ".join(where)

    sql_constructs = text(
        f"""
        SELECT
          construct_code,
          construct_kind,
          construct_name,
          resistance,
          description,
          0::int                             AS n_fusions,
          ''::text                           AS fusion_pretty,
          ''::text                           AS organelle_fluors,
          created_at
        FROM public.constructs
        WHERE {where_sql}
        ORDER BY created_at DESC NULLS LAST, construct_code
        LIMIT :lim;
        """
    )

    with _eng().begin() as cx:
        df_constructs = pd.read_sql(sql_constructs, cx, params=params)

    if df_constructs.empty:
        st.info("No constructs match these filters.")
    else:
        for col in df_constructs.select_dtypes(include="object").columns:
            df_constructs[col] = df_constructs[col].fillna("")

        st.caption(f"{len(df_constructs)} construct(s)")

        # Canonical "construct/marker" identity block
        view_constructs = pd.DataFrame(
            {
                "code": df_constructs["construct_code"],
                "name": df_constructs["construct_name"],
                "type": df_constructs["construct_kind"],
                "base_code": df_constructs["construct_code"],
                "resistance": df_constructs["resistance"],
                "description": df_constructs["description"],
                "linked_markers": df_constructs["fusion_pretty"],
                "organelle_fluors": df_constructs["organelle_fluors"],
                "n_fusions": df_constructs["n_fusions"],
                "created_at": df_constructs["created_at"],
            }
        )

        view_constructs.insert(0, "✓ Select", False)

        grid_constructs = st.data_editor(
            view_constructs,
            key="constructs_overview_v10core",
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
                "code": st.column_config.TextColumn("code", disabled=True),
                "name": st.column_config.TextColumn(
                    "name", disabled=True, width="large"
                ),
                "type": st.column_config.TextColumn("kind", disabled=True),
                "base_code": st.column_config.TextColumn("base_code", disabled=True),
                "resistance": st.column_config.TextColumn(
                    "resistance", disabled=True
                ),
                "description": st.column_config.TextColumn(
                    "description", disabled=True, width="large"
                ),
                "linked_markers": st.column_config.TextColumn(
                    "fusions fluor::tag(tag_pos)", disabled=True, width="large"
                ),
                "organelle_fluors": st.column_config.TextColumn(
                    "organelle-fluors", disabled=True, width="large"
                ),
                "n_fusions": st.column_config.NumberColumn(
                    "n_fusions", disabled=True
                ),
                "created_at": st.column_config.DatetimeColumn(
                    "created_at", disabled=True
                ),
            },
        )

        st.divider()
        st.subheader("Construct details")

        selected_idxs: List[int] = []
        if "✓ Select" in grid_constructs.columns:
            selected_idxs = (
                grid_constructs.index[grid_constructs["✓ Select"] == True]
                .to_series()
                .tolist()
            )

        if not selected_idxs:
            st.info("Select one or more constructs above to see details.")
        elif len(selected_idxs) == 1:
            row = grid_constructs.loc[selected_idxs[0]]

            tab1, tab2 = st.tabs(["Overview", "Markers"])
            with tab1:
                st.write(
                    {
                        "code": row["code"],
                        "name": row["name"],
                        "type": row["type"],
                        "base_code": row["base_code"],
                        "resistance": row["resistance"],
                        "description": row["description"],
                    }
                )
            with tab2:
                st.write(
                    {
                        "linked_markers": row["linked_markers"],
                        "organelle_fluors": row["organelle_fluors"],
                    }
                )
        else:
            subset = grid_constructs.loc[selected_idxs].reset_index(drop=True)
            st.write("Summary for selected constructs:")
            st.dataframe(subset[["type", "code", "name", "n_fusions"]])

            if st.checkbox("Show constructs by kind", key="constructs_pivot_kind"):
                pt = (
                    subset.pivot_table(
                        index="type",
                        values="code",
                        aggfunc="count",
                    )
                    .rename(columns={"code": "n_constructs"})
                    .reset_index()
                )
                st.dataframe(pt, use_container_width=True)

        st.download_button(
            "⬇︎ Download constructs (CSV)",
            data=df_constructs.to_csv(index=False).encode("utf-8"),
            file_name="v_constructs_overview.csv",
            type="secondary",
            mime="text/csv",
        )

# ════════════════════════════════════════════════════════
# TAB 2 — FLUORS
# ════════════════════════════════════════════════════════
with tab_fluors:
    st.subheader("Fluors")

    with st.form("fluor_filters", clear_on_submit=False):
        c1, c2 = st.columns([3, 1])
        with c1:
            q_raw_f = st.text_input(
                "Search (code / name / alt_names / notes)",
                "",
                key="fluors_search",
            )
        with c2:
            lim_f = int(
                st.number_input(
                    "Limit (fluors)",
                    min_value=50,
                    max_value=5000,
                    value=1000,
                    step=50,
                    key="fluors_limit",
                )
            )
        _ = st.form_submit_button("Apply", key="fluors_apply")

    q_f = _norm(q_raw_f)
    q_f_param = q_f or None

    sql_fluors = text(
        """
        SELECT
          id::text                        AS id,
          COALESCE(fluor_code,'')         AS code,
          COALESCE(fluor_name,'')         AS name,
          COALESCE(excitation_nm,0)::int  AS excitation_nm,
          COALESCE(emission_nm,0)::int    AS emission_nm,
          COALESCE(
            CASE
              WHEN pg_typeof(alt_names)::text = 'text[]'
                THEN array_to_string(alt_names, ', ')
              ELSE alt_names::text
            END, ''
          )                                AS alt_names,
          COALESCE(notes,'')               AS notes
        FROM public.fluors
        WHERE (
          :q IS NULL
          OR COALESCE(fluor_code,'') ILIKE :ql
          OR COALESCE(fluor_name,'') ILIKE :ql
          OR COALESCE(notes,'')      ILIKE :ql
          OR COALESCE(
               CASE
                 WHEN pg_typeof(alt_names)::text = 'text[]'
                   THEN array_to_string(alt_names, ',')
                 ELSE alt_names::text
               END,''
             ) ILIKE :ql
        )
        ORDER BY fluor_name, fluor_code
        LIMIT :lim;
        """
    )

    params_f = {
        "q": q_f_param,
        "ql": f"%{q_f}%" if q_f else None,
        "lim": lim_f,
    }

    with _eng().begin() as cx:
        df_f = pd.read_sql(sql_fluors, cx, params=params_f)

    if df_f.empty:
        st.info("No fluors match these filters.")
    else:
        df_f = df_f.fillna("")
        st.caption(f"{len(df_f)} fluor(s)")

        view_f = pd.DataFrame(
            {
                "code": df_f["code"],
                "name": df_f["name"],
                "type": ["fluor"] * len(df_f),
                "base_code": df_f["code"],
                "excitation_nm": df_f["excitation_nm"],
                "emission_nm": df_f["emission_nm"],
                "alt_names": df_f["alt_names"],
                "notes": df_f["notes"],
                "id": df_f["id"],
            }
        )
        view_f.insert(0, "✓ Select", False)

        grid_f = st.data_editor(
            view_f,
            key="fluors_overview_v10core",
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
                "code": st.column_config.TextColumn("Code", disabled=True),
                "name": st.column_config.TextColumn("Name", disabled=True),
                "type": st.column_config.TextColumn("Type", disabled=True),
                "base_code": st.column_config.TextColumn("base_code", disabled=True),
                "excitation_nm": st.column_config.NumberColumn(
                    "Excitation (nm)", disabled=True
                ),
                "emission_nm": st.column_config.NumberColumn(
                    "Emission (nm)", disabled=True
                ),
                "alt_names": st.column_config.TextColumn(
                    "Alt names", disabled=True
                ),
                "notes": st.column_config.TextColumn("Notes", disabled=True),
                "id": st.column_config.TextColumn("ID", disabled=True),
            },
        )

        st.divider()
        st.subheader("Fluor details")

        sel_f_idxs: List[int] = []
        if "✓ Select" in grid_f.columns:
            sel_f_idxs = (
                grid_f.index[grid_f["✓ Select"] == True].to_series().tolist()
            )

        if not sel_f_idxs:
            st.info("Select one or more fluors above to see details.")
        elif len(sel_f_idxs) == 1:
            row = grid_f.loc[sel_f_idxs[0]]
            tab1, tab2 = st.tabs(["Overview", "Spectra"])
            with tab1:
                st.write(
                    {
                        "code": row["code"],
                        "name": row["name"],
                        "alt_names": row["alt_names"],
                        "notes": row["notes"],
                    }
                )
            with tab2:
                st.write(
                    {
                        "excitation_nm": row["excitation_nm"],
                        "emission_nm": row["emission_nm"],
                    }
                )
        else:
            subset = grid_f.loc[sel_f_idxs].reset_index(drop=True)
            st.write("Summary for selected fluors:")
            st.dataframe(subset[["code", "name", "excitation_nm", "emission_nm"]])

        st.download_button(
            "⬇︎ Download fluors (CSV)",
            data=df_f.to_csv(index=False).encode("utf-8"),
            file_name="fluors_overview.csv",
            type="secondary",
            mime="text/csv",
        )

# ════════════════════════════════════════════════════════
# TAB 3 — TAGS
# ════════════════════════════════════════════════════════
with tab_tags:
    st.subheader("Tags")

    with st.form("tag_filters", clear_on_submit=False):
        c1, c2 = st.columns([3, 1])
        with c1:
            q_raw_t = st.text_input(
                "Search tag_code / tag_name / localization / notes",
                "",
                key="tags_search",
            )
        with c2:
            lim_t = int(
                st.number_input(
                    "Limit (tags)",
                    min_value=50,
                    max_value=5000,
                    value=1000,
                    step=50,
                    key="tags_limit",
                )
            )
        _ = st.form_submit_button("Apply", key="tags_apply")

    def _normalize_tag(s: str | None) -> Optional[str]:
        s = (s or "").strip()
        return s or None

    q_t = _normalize_tag(q_raw_t)

    sql_tags = text(
        """
        SELECT
          id::text   AS id,
          tag_code,
          tag_name,
          localization,
          notes,
          created_at
        FROM public.tags
        WHERE (
             :q IS NULL
          OR  tag_code     ILIKE :ql
          OR  tag_name     ILIKE :ql
          OR  COALESCE(localization,'') ILIKE :ql
          OR  COALESCE(notes,'')        ILIKE :ql
        )
        ORDER BY tag_code
        LIMIT :limit;
        """
    )

    params_t = {
        "q": q_t,
        "ql": f"%{q_t}%" if q_t else None,
        "limit": lim_t,
    }

    with _eng().begin() as cx:
        df_t = pd.read_sql(sql_tags, cx, params=params_t)

    df_t = df_t.fillna("")
    st.caption(f"{len(df_t)} tag(s)")

    view_t = pd.DataFrame(
        {
            "code": df_t["tag_code"],
            "name": df_t["tag_name"],
            "type": ["tag"] * len(df_t),
            "localization": df_t["localization"],
            "notes": df_t["notes"],
            "created_at": df_t["created_at"],
            "id": df_t["id"],
        }
    )
    view_t.insert(0, "✓ Select", False)

    grid_t = st.data_editor(
        view_t,
        key="tags_overview_v10core",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_order=[
            "✓ Select",
            "code",
            "name",
            "type",
            "localization",
            "notes",
            "created_at",
        ],
        column_config={
            "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
            "code": st.column_config.TextColumn("Tag code", disabled=True),
            "name": st.column_config.TextColumn("Name", disabled=True),
            "type": st.column_config.TextColumn("Type", disabled=True),
            "localization": st.column_config.TextColumn("Localization", disabled=True),
            "notes": st.column_config.TextColumn("Notes", disabled=True),
            "created_at": st.column_config.DatetimeColumn("Created", disabled=True),
            "id": st.column_config.TextColumn("ID", disabled=True),
        },
    )

    sel_t_ids: List[str] = []
    if isinstance(grid_t, pd.DataFrame) and "✓ Select" in grid_t.columns:
        sel_t_ids = grid_t.loc[grid_t["✓ Select"] == True, "id"].astype(str).tolist()

    st.divider()
    st.subheader("Tag details")

    if not sel_t_ids:
        st.info("Select one or more tags above to see details.")
    elif len(sel_t_ids) == 1:
        row = grid_t.loc[grid_t["id"].isin(sel_t_ids)].iloc[0]
        st.write(
            {
                "code": row["code"],
                "name": row["name"],
                "localization": row["localization"],
                "notes": row["notes"],
            }
        )
    else:
        subset = grid_t[grid_t["id"].isin(sel_t_ids)].reset_index(drop=True)
        st.write("Summary for selected tags:")
        st.dataframe(subset[["code", "name", "localization"]])

    st.download_button(
        "⬇︎ Download tags (CSV)",
        data=df_t.to_csv(index=False).encode("utf-8"),
        file_name="tags_overview.csv",
        type="secondary",
        mime="text/csv",
    )

# ════════════════════════════════════════════════════════
# TAB 4 — DYES
# ════════════════════════════════════════════════════════
with tab_dyes:
    st.subheader("Dyes")

    with st.form("dye_filters", clear_on_submit=False):
        c1, c2 = st.columns([3, 1])
        with c1:
            q_raw_dye = st.text_input(
                "Search (base code / name / notes / fluor)",
                "",
                key="dyes_search",
            )
        with c2:
            lim_dyes = int(
                st.number_input(
                    "Limit (dyes)",
                    min_value=50,
                    max_value=5000,
                    value=1000,
                    step=50,
                    key="dyes_limit",
                )
            )
        _ = st.form_submit_button("Apply", key="dyes_apply")

    q_dye = _norm(q_raw_dye)
    q_param = q_dye or None

    sql_dyes = text(
        """
        SELECT
          id,
          dye_base_code,
          name,
          notes,
          created_at,
          fluor_code,
          fluor_name,
          excitation_nm,
          emission_nm
        FROM public.v_dyes_overview
        WHERE (
             :q IS NULL
          OR  dye_base_code ILIKE :ql
          OR  name          ILIKE :ql
          OR  notes         ILIKE :ql
          OR  fluor_code    ILIKE :ql
          OR  fluor_name    ILIKE :ql
        )
        ORDER BY dye_base_code, name
        LIMIT :lim;
        """
    )

    params_dyes = {
        "q": q_param,
        "ql": f"%{q_dye}%" if q_dye else None,
        "lim": lim_dyes,
    }

    with _eng().begin() as cx:
        df_dyes = pd.read_sql(sql_dyes, cx, params=params_dyes)

    if df_dyes.empty:
        st.info("No dyes match these filters.")
    else:
        df_dyes = df_dyes.fillna("")
        st.caption(f"{len(df_dyes)} dye(s)")

        view_dyes = pd.DataFrame(
            {
                "code": df_dyes["dye_base_code"],
                "name": df_dyes["name"],
                "type": ["dye"] * len(df_dyes),
                "base_code": df_dyes["dye_base_code"],
                "linked_markers": df_dyes["fluor_code"],
                "notes": df_dyes["notes"],
                "fluor_name": df_dyes["fluor_name"],
                "excitation_nm": df_dyes["excitation_nm"],
                "emission_nm": df_dyes["emission_nm"],
                "created_at": df_dyes["created_at"],
                "id": df_dyes["id"],
            }
        )

        view_dyes.insert(0, "✓ Select", False)

        grid_dyes = st.data_editor(
            view_dyes,
            key="dyes_overview_v10core",
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
                "code": st.column_config.TextColumn("Base code", disabled=True),
                "name": st.column_config.TextColumn("Name", disabled=True),
                "type": st.column_config.TextColumn("Type", disabled=True),
                "base_code": st.column_config.TextColumn("base_code", disabled=True),
                "linked_markers": st.column_config.TextColumn(
                    "Fluor code", disabled=True
                ),
                "notes": st.column_config.TextColumn("Notes", disabled=True),
                "fluor_name": st.column_config.TextColumn(
                    "Fluor name", disabled=True
                ),
                "excitation_nm": st.column_config.NumberColumn(
                    "Ex (nm)", disabled=True
                ),
                "emission_nm": st.column_config.NumberColumn(
                    "Em (nm)", disabled=True
                ),
                "created_at": st.column_config.DatetimeColumn(
                    "Created", disabled=True
                ),
                "id": st.column_config.TextColumn("ID", disabled=True),
            },
        )

        st.divider()
        st.subheader("Dye details")

        selected_dye_idxs: List[int] = []
        if "✓ Select" in grid_dyes.columns:
            selected_dye_idxs = (
                grid_dyes.index[grid_dyes["✓ Select"] == True]
                .to_series()
                .tolist()
            )

        if not selected_dye_idxs:
            st.info("Select one or more dyes above to see details.")
        elif len(selected_dye_idxs) == 1:
            row = grid_dyes.loc[selected_dye_idxs[0]]

            tab1, tab2 = st.tabs(["Overview", "Spectra"])
            with tab1:
                st.write(
                    {
                        "code": row["code"],
                        "name": row["name"],
                        "type": row["type"],
                        "base_code": row["base_code"],
                        "notes": row["notes"],
                        "linked_fluor": f"{row['linked_markers']} ({row['fluor_name']})",
                    }
                )
            with tab2:
                st.write(
                    {
                        "excitation_nm": row["excitation_nm"],
                        "emission_nm": row["emission_nm"],
                    }
                )
        else:
            subset = grid_dyes.loc[selected_dye_idxs].reset_index(drop=True)
            st.write("Summary for selected dyes:")
            st.dataframe(
                subset[
                    ["code", "name", "linked_markers", "excitation_nm", "emission_nm"]
                ]
            )

        st.download_button(
            "⬇︎ Download dyes (CSV)",
            data=df_dyes.to_csv(index=False).encode("utf-8"),
            file_name="dyes_overview.csv",
            type="secondary",
            mime="text/csv",
        )