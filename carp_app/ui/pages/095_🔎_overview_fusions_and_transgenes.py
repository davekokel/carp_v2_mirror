from __future__ import annotations

import sys
import pathlib
from typing import Dict, Any, List, Optional

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
    def require_app_unlock() -> None:
        ...

# Centralized engine component
from carp_app.ui.lib.page_engine import engine
# from carp_app.lib.time import utc_now  # import when we need "now"

# ───────── auth & page ─────────
st.set_page_config(
    page_title="CARP — Overview fusions & transgenes",
    page_icon="🔎",
    layout="wide",
)

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.title("🔎 Overview fusions & transgenes")


def _eng() -> Engine:
    """Centralized engine accessor (thin wrapper around page_engine.engine)."""
    return engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ───────── tabs ─────────
tab_fusions, tab_transgenes = st.tabs(["Fusions", "Transgenes"])


# ════════════════════════════════════════════════════════
# TAB 1 — FUSIONS
# ════════════════════════════════════════════════════════
with tab_fusions:
    st.subheader("Fusions")

    # ── Filters ─────────────────────────────────────────
    with st.form("fusion_filters", clear_on_submit=False):
        c1, c2 = st.columns([3, 1])
        with c1:
            q_raw = st.text_input(
                "Search (supports fluor:, tag:, pos:, name:, -negation)",
                "",
            )
        with c2:
            lim_fusions = int(
                st.number_input(
                    "Limit (fusions)",
                    min_value=50,
                    max_value=5000,
                    value=1500,
                    step=100,
                    key="fusions_limit",
                )
            )
        _ = st.form_submit_button("Apply", key="fusions_apply")

    q = _norm(q_raw) or ""

    # ── Build query (ported from legacy, but centralized) ───────────────────
    import shlex

    def _build_fusion_query(q: str, limit: int) -> tuple[str, Dict[str, Any]]:
        tokens = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]
        params: Dict[str, Any] = {"lim": int(limit)}
        where: List[str] = []

        # canonical column names from v_fusions_overview
        c_fluor = "fluor"
        c_tag = "tag"
        c_pos = "tag_pos"
        c_name = "fusion_name"

        field_map = {"fluor": c_fluor, "tag": c_tag, "pos": c_pos, "name": c_name}
        haystack = f"concat_ws(' ', {c_fluor}, {c_tag}, {c_pos}, {c_name})"

        for i, tok in enumerate(tokens):
            neg = tok.startswith("-")
            core = tok[1:] if neg else tok
            if ":" in core:
                k, v = core.split(":", 1)
                k = k.lower().strip()
                v = v.strip().strip('"')
                if k in field_map:
                    key = f"p{i}"
                    params[key] = f"%{v}%"
                    where.append(
                        f"{'NOT ' if neg else ''}{field_map[k]} ILIKE :{key}"
                    )
                    continue
            key = f"p{i}"
            params[key] = f"%{core}%"
            where.append(f"{'NOT ' if neg else ''}{haystack} ILIKE :{key}")

        where_sql = "WHERE " + " AND ".join(where) if where else ""

        sql = f"""
        SELECT
          id,
          fusion_name,
          fluor,
          tag,
          tag_pos,
          n_constructs,
          created_at
        FROM public.v_fusions_overview
        {where_sql}
        ORDER BY
          n_constructs DESC,
          fluor,
          tag     NULLS FIRST,
          tag_pos NULLS FIRST,
          created_at DESC
        LIMIT :lim;
        """

        return sql, params

    # ── Load fusions via centralized engine ─────────────────────────────────
    def _load_fusions(q: str, lim: int) -> pd.DataFrame:
        sql, params = _build_fusion_query(q, lim)
        with _eng().begin() as cx:
            df = pd.read_sql(text(sql), cx, params=params)
        for c in df.select_dtypes(include=["object", "string"]).columns:
            df[c] = df[c].astype("string").fillna("")
        return df

    try:
        df_fusions = _load_fusions(q, lim_fusions)
    except Exception as e:
        st.error(f"Query error while loading fusions: {type(e).__name__}: {e}")
        st.stop()

    st.caption(f"{len(df_fusions)} fusion(s)")

    # ── Main table (core fields + selection) ────────────────────────────────
    view_fusions = df_fusions.copy()
    view_fusions.insert(0, "✓ Select", False)

    grid_fusions = st.data_editor(
        view_fusions,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        key="fusions_overview_core",
        column_order=[
            "✓ Select",
            "fusion_name",
            "fluor",
            "tag",
            "tag_pos",
            "n_constructs",
            "created_at",
        ],
        column_config={
            "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
            "fusion_name": st.column_config.TextColumn("Fusion", disabled=True),
            "fluor": st.column_config.TextColumn("Fluor", disabled=True),
            "tag": st.column_config.TextColumn("Tag", disabled=True),
            "tag_pos": st.column_config.TextColumn("Pos", disabled=True),
            "n_constructs": st.column_config.NumberColumn(
                "Constructs", disabled=True
            ),
            "created_at": st.column_config.DatetimeColumn(
                "Created", disabled=True
            ),
        },
    )

    st.divider()
    st.subheader("Fusion drill-down")

    # ── Construct preview for selected fusion ───────────────────────────────
    selected_ids: List[str] = []
    fusion_names: Dict[str, str] = {}

    if isinstance(grid_fusions, pd.DataFrame) and "✓ Select" in grid_fusions.columns:
        sel = grid_fusions.loc[grid_fusions["✓ Select"] == True]
        if not sel.empty and "id" in sel.columns:
            selected_ids = sel["id"].astype(str).tolist()
            fusion_names = dict(zip(sel["id"].astype(str), sel["fusion_name"]))

    if len(selected_ids) == 1:
        fusion_id = selected_ids[0]
        fusion_label = fusion_names.get(fusion_id, fusion_id)

        with _eng().begin() as cx:
            constructs_df = pd.read_sql(
                text(
                    """
                    SELECT
                      c.base_code,
                      c.construct_code,
                      c.construct_name,
                      c.construct_kind,
                      c.nickname,
                      c.created_at
                    FROM public.construct_fusions cf
                    JOIN public.constructs c
                      ON c.id = cf.construct_id
                    WHERE cf.fusion_id = :fid
                    ORDER BY c.created_at DESC NULLS LAST, c.construct_code
                    """
                ),
                cx,
                params={"fid": fusion_id},
            )

        st.subheader(f"Constructs containing: {fusion_label}")
        if constructs_df.empty:
            st.info("No constructs linked to this fusion.")
        else:
            st.dataframe(
                constructs_df[
                    [
                        "base_code",
                        "construct_code",
                        "construct_name",
                        "construct_kind",
                        "nickname",
                        "created_at",
                    ]
                ],
                hide_index=True,
                use_container_width=True,
            )
            st.download_button(
                "⬇︎ Download constructs (CSV)",
                data=constructs_df.to_csv(index=False).encode("utf-8"),
                file_name=f"constructs_for_fusion_{fusion_label}.csv",
                type="secondary",
            )
    elif len(selected_ids) > 1:
        st.info("Select exactly one fusion to preview its constructs.")
    else:
        st.caption("Tip: check a fusion row above to preview its constructs.")

    # ── Export full fusion table ────────────────────────────────────────────
    st.download_button(
        "⬇︎ Download full fusion table (CSV)",
        data=df_fusions.to_csv(index=False).encode("utf-8"),
        file_name="fusions_overview.csv",
        type="secondary",
        mime="text/csv",
    )


# ════════════════════════════════════════════════════════
# TAB 2 — TRANSGENES
# ════════════════════════════════════════════════════════
with tab_transgenes:
    st.subheader("Transgene summary")

    # ---- summary: v_transgenes_overview -----------------
    summary_sql = text(
        """
        SELECT
          transgene_base_code,
          transgene_name,
          n_alleles,
          n_fluors,
          all_fluor_tag_rollup,
          all_organelle_fluor_rollup
        FROM public.v_transgenes_overview
        ORDER BY transgene_base_code;
        """
    )

    try:
        with _eng().begin() as cx:
            summary_rows = pd.read_sql(summary_sql, cx)
    except Exception as e:
        st.error("Error querying transgenes / alleles summary.")
        st.exception(e)
        st.stop()

    if summary_rows.empty:
        st.info("No transgenes found in this database (transgene_alleles may be empty).")
        selected_base_code: Optional[str] = None
    else:
        summary_df = summary_rows.copy()
        if "✓ Select" not in summary_df.columns:
            summary_df.insert(0, "✓ Select", False)

        summary_edited = st.data_editor(
            summary_df,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
                "transgene_base_code": st.column_config.TextColumn(
                    "transgene_base_code", disabled=True
                ),
                "transgene_name": st.column_config.TextColumn(
                    "transgene_name", disabled=True, width="large"
                ),
                "n_alleles": st.column_config.NumberColumn(
                    "n_alleles", disabled=True, format="%d"
                ),
                "n_fluors": st.column_config.NumberColumn(
                    "n_fluors", disabled=True, format="%d"
                ),
                "all_fluor_tag_rollup": st.column_config.TextColumn(
                    "all_fluor_tag_rollup (fluor::tag(pos))",
                    disabled=True,
                    width="large",
                ),
                "all_organelle_fluor_rollup": st.column_config.TextColumn(
                    "all_organelle_fluor_rollup (organelle-fluor)",
                    disabled=True,
                    width="large",
                ),
            },
            key="transgene_summary_editor_v11",
        )

        # selection mask
        if (
            isinstance(summary_edited, pd.DataFrame)
            and "✓ Select" in summary_edited.columns
        ):
            sel_series = summary_edited["✓ Select"]
            if not isinstance(sel_series, pd.Series):
                sel_series = pd.Series(sel_series, index=summary_edited.index)
        else:
            sel_series = pd.Series(False, index=summary_rows.index)

        sel_mask = sel_series.fillna(False).astype(bool)
        selected_rows = summary_edited.loc[sel_mask]

        if not selected_rows.empty:
            selected_base_code = (
                str(selected_rows.iloc[0]["transgene_base_code"]).strip() or None
            )
            st.caption(
                f"Drill-down: showing alleles for **{selected_base_code}** below."
            )
        else:
            selected_base_code = None
            st.caption("Tip: check a row above to drill down into its alleles.")

    # ---- sidebar filters for alleles --------------------
    st.subheader("Transgene alleles")
    st.sidebar.header("Transgene allele filters")

    base_code_filter = st.sidebar.text_input(
        "Transgene base code contains",
        "",
        key="tg_base_code_filter",
    )
    allele_number_filter = st.sidebar.text_input(
        "Allele number equals (optional, integer)",
        "",
        key="tg_allele_number_filter",
    )

    limit_alleles = st.sidebar.number_input(
        "Max allele rows",
        min_value=100,
        max_value=5000,
        value=1000,
        step=100,
        key="tg_allele_limit",
    )

    # ---- build WHERE for v_transgene_alleles_overview --
    where_clauses: List[str] = ["1=1"]
    params_alleles: Dict[str, Any] = {"limit": int(limit_alleles)}

    bc = (base_code_filter or "").strip()
    if selected_base_code:
        where_clauses.append("transgene_base_code = :selected_base_code")
        params_alleles["selected_base_code"] = selected_base_code
    elif bc:
        where_clauses.append("transgene_base_code ILIKE :base_code")
        params_alleles["base_code"] = f"%{bc}%"

    allele_txt = (allele_number_filter or "").strip()
    if allele_txt:
        try:
            params_alleles["allele_number"] = int(allele_txt)
            where_clauses.append("allele_number = :allele_number")
        except ValueError:
            st.warning("Allele number filter must be an integer.")
            st.stop()

    where_sql = " AND ".join(where_clauses)

    query_sql = text(
        f"""
        SELECT
          transgene_base_code,
          transgene_name,
          allele_number,
          allele_name,
          allele_nickname,
          n_fluors,
          all_fluor_tag_rollup,
          all_organelle_fluor_rollup
        FROM public.v_transgene_alleles_overview
        WHERE {where_sql}
        ORDER BY transgene_base_code, allele_number
        LIMIT :limit;
        """
    )

    try:
        with _eng().begin() as cx:
            rows = pd.read_sql(query_sql, cx, params=params_alleles)
    except Exception as e:
        st.error("Error loading transgene alleles.")
        st.exception(e)
        st.stop()

    if rows.empty:
        if selected_base_code:
            st.info(f"No alleles found for transgene **{selected_base_code}**.")
        else:
            st.info("No alleles matched the current filters.")
    else:
        alleles_df = rows.fillna("")

        st.dataframe(
            alleles_df[
                [
                    "transgene_base_code",
                    "transgene_name",
                    "allele_number",
                    "allele_name",
                    "allele_nickname",
                    "n_fluors",
                    "all_fluor_tag_rollup",
                    "all_organelle_fluor_rollup",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        csv_bytes = alleles_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇︎ Download transgene alleles (CSV)",
            data=csv_bytes,
            file_name="transgenes_overview_filtered.csv",
            mime="text/csv",
            type="secondary",
        )