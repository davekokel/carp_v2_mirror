from __future__ import annotations

import pathlib
import sys
from typing import Dict, List, Optional, Any

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

from carp_app.ui.lib.page_engine import engine

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview: Fish",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 Overview: Fish (groups → lines → instances)")


def _eng() -> Engine:
    return engine()


def _norm(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None


def _maybe(d: Dict[str, Any], row: pd.Series, col: str, label: Optional[str] = None):
    if col in row.index:
        d[label or col] = row[col]


@st.cache_data(show_spinner=False)
def load_lines() -> pd.DataFrame:
    sql = text(
        """
        WITH marker_line AS (
          SELECT
            fi.line_id,
            COUNT(DISTINCT mr.fish_instance_id)                      AS n_marker_fish,
            MAX(mr.n_constructs)                                     AS line_n_constructs,
            MAX(mr.n_fluors)                                         AS line_n_fluors,
            COALESCE(
              string_agg(
                DISTINCT NULLIF(mr.fluor_tag_rollup, ''),
                '||'
              ),
              ''
            ) AS line_fluor_tag_rollup,
            COALESCE(
              string_agg(
                DISTINCT NULLIF(mr.organelle_fluor_rollup, ''),
                '||'
              ),
              ''
            ) AS line_organelle_fluor_rollup
          FROM public.v11_fish_marker_rollups mr
          JOIN public.fish_instances_v10 fi
            ON fi.id = mr.fish_instance_id
          GROUP BY fi.line_id
        )
        SELECT
          fi.line_id::text                                  AS line_id,
          fl.line_code                                      AS line_code,
          MAX(fl.nickname)                                  AS line_nickname,
          MAX(fl.genetic_background)                        AS genetic_background,
          MAX(fl.line_building_stage)                       AS line_building_stage,
          MIN(fi.birthday)                                  AS first_birthday,
          MAX(fi.birthday)                                  AS last_birthday,
          COUNT(*)                                          AS n_instances,
          MAX(fis.genotype_pretty)                          AS genotype_pretty,
          COALESCE(MAX(ml.line_n_constructs), 0)            AS n_constructs,
          COALESCE(MAX(ml.line_n_fluors), 0)                AS n_fluors,
          COALESCE(MAX(ml.line_fluor_tag_rollup), '')       AS all_fluor_tag_rollup,
          COALESCE(MAX(ml.line_organelle_fluor_rollup), '') AS all_organelle_fluor_rollup
        FROM public.v11_fish_instance_star fis
        JOIN public.fish_instances_v10 fi
          ON fi.id = fis.fish_instance_id
        JOIN public.fish_lines fl
          ON fl.id = fi.line_id
        LEFT JOIN marker_line ml
          ON ml.line_id = fi.line_id
        GROUP BY
          fi.line_id,
          fl.line_code
        ORDER BY
          fl.line_code;
        """
    )
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx)
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df.fillna("")


@st.cache_data(show_spinner=False)
def load_groups_raw() -> pd.DataFrame:
    sql = text(
        """
        SELECT
          group_transgene_rollup,
          group_line_codes,
          group_line_nicknames,
          group_genetic_backgrounds,
          n_lines,
          n_instances,
          all_fluor_tag_rollup,
          all_organelle_fluor_rollup
        FROM public.v11_fish_group_star
        ORDER BY group_transgene_rollup;
        """
    )
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx)
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df.fillna("")


@st.cache_data(show_spinner=False)
def load_instances_for_line(line_id: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          fis.*,
          mr.n_constructs,
          mr.n_fluors,
          mr.fluor_tag_rollup       AS all_fluor_tag_rollup,
          mr.organelle_fluor_rollup AS all_organelle_fluor_rollup
        FROM public.v11_fish_instance_star fis
        JOIN public.fish_instances_v10 fi
          ON fi.id = fis.fish_instance_id
        LEFT JOIN public.v11_fish_marker_rollups mr
          ON mr.fish_instance_id = fis.fish_instance_id
        WHERE fi.line_id = :line_id
        ORDER BY fis.birthday NULLS LAST, fis.fish_code;
        """
    )
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"line_id": line_id})
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df.fillna("")


lines_df = load_lines()
groups_raw = load_groups_raw().copy()

st.subheader("Step 1 — Groups (fish groups)")

if groups_raw.empty:
    st.info("No fish groups found.")
    st.stop()

with st.form("group_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        group_search = st.text_input(
            "Search (allele/construct rollup / backgrounds / line nicknames / markers)",
            value="",
            key="group_search_text",
        )
    with c2:
        min_group_instances = st.number_input(
            "Min instances per group (optional)",
            min_value=0,
            value=0,
            step=1,
        )
    _ = st.form_submit_button("Apply", use_container_width=True)

groups_filtered = groups_raw.copy()

if group_search.strip():
    qg = group_search.strip().lower()
    mask = (
        groups_filtered["group_transgene_rollup"].str.lower().str.contains(qg, na=False)
        | groups_filtered["group_line_nicknames"].str.lower().str.contains(qg, na=False)
        | groups_filtered["group_genetic_backgrounds"].str.lower().str.contains(qg, na=False)
        | groups_filtered["all_fluor_tag_rollup"].str.lower().str.contains(qg, na=False)
        | groups_filtered["all_organelle_fluor_rollup"].str.lower().str.contains(qg, na=False)
    )
    groups_filtered = groups_filtered[mask]

if min_group_instances > 0:
    groups_filtered = groups_filtered[groups_filtered["n_instances"] >= min_group_instances]

if groups_filtered.empty:
    st.warning("No groups match the current filters.")
    st.stop()

st.caption(f"{len(groups_filtered)} group(s)")

groups_display = groups_filtered[
    [
        "group_transgene_rollup",
        "group_line_nicknames",
        "group_genetic_backgrounds",
        "n_lines",
        "n_instances",
        "all_fluor_tag_rollup",
        "all_organelle_fluor_rollup",
        "group_line_codes",
    ]
].copy()

groups_display.insert(0, "✓", False)

edited_groups = st.data_editor(
    groups_display,
    use_container_width=True,
    num_rows="fixed",
    key="groups_editor_v11_overview",
    column_config={
        "✓": st.column_config.CheckboxColumn("Select", width=60),
        "group_transgene_rollup": st.column_config.TextColumn(
            "Allele/construct rollup", disabled=True, width="large"
        ),
        "group_line_nicknames": st.column_config.TextColumn(
            "Line nicknames", disabled=True, width="large"
        ),
        "group_genetic_backgrounds": st.column_config.TextColumn(
            "Backgrounds", disabled=True, width="large"
        ),
        "n_lines": st.column_config.NumberColumn("n lines", disabled=True),
        "n_instances": st.column_config.NumberColumn("n instances", disabled=True),
        "all_fluor_tag_rollup": st.column_config.TextColumn(
            "fluor::tag(tag_pos)", disabled=True, width="large"
        ),
        "all_organelle_fluor_rollup": st.column_config.TextColumn(
            "organelle-fluor rollup", disabled=True, width="large"
        ),
        "group_line_codes": st.column_config.TextColumn(
            "Line codes", disabled=True, width="large"
        ),
    },
    hide_index=True,
)

selected_group_rows = edited_groups[edited_groups["✓"]]
if not selected_group_rows.empty:
    selected_group = selected_group_rows.iloc[0]
else:
    selected_group = groups_display.iloc[0]

selected_line_codes = selected_group["group_line_codes"].split("||") if selected_group["group_line_codes"] else []

st.caption("Select one group above, then drill down to its lines and instances.")

st.markdown("---")
st.subheader("Step 2 — Lines in selected group")

lines_in_group = lines_df[lines_df["line_code"].isin(selected_line_codes)].copy()

if lines_in_group.empty:
    st.info("No lines found for this group.")
    st.stop()

with st.form("line_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        search_text = st.text_input(
            "Search (line_code / nickname / background / genotype / markers)",
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

filtered_lines = lines_in_group.copy()

if search_text.strip():
    q = search_text.strip().lower()
    mask = (
        filtered_lines["line_code"].str.lower().str.contains(q, na=False)
        | filtered_lines["line_nickname"].str.lower().str.contains(q, na=False)
        | filtered_lines["genetic_background"].str.lower().str.contains(q, na=False)
        | filtered_lines["genotype_pretty"].str.lower().str.contains(q, na=False)
        | filtered_lines["all_fluor_tag_rollup"].str.lower().str.contains(q, na=False)
        | filtered_lines["all_organelle_fluor_rollup"].str.lower().str.contains(q, na=False)
    )
    filtered_lines = filtered_lines[mask]

if min_instances > 0:
    filtered_lines = filtered_lines[filtered_lines["n_instances"] >= min_instances]

if filtered_lines.empty:
    st.warning("No lines match the current filters.")
    st.stop()

st.caption(f"{len(filtered_lines)} line(s) in selected group")

lines_display = filtered_lines[
    [
        "line_id",
        "line_code",
        "line_nickname",
        "genetic_background",
        "genotype_pretty",
        "n_instances",
        "first_birthday",
        "last_birthday",
        "n_constructs",
        "n_fluors",
        "all_fluor_tag_rollup",
        "all_organelle_fluor_rollup",
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
        "n_constructs": st.column_config.NumberColumn(
            "n constructs", disabled=True
        ),
        "n_fluors": st.column_config.NumberColumn(
            "n fluors", disabled=True
        ),
        "all_fluor_tag_rollup": st.column_config.TextColumn(
            "fluor::tag(tag_pos)", disabled=True, width="large"
        ),
        "all_organelle_fluor_rollup": st.column_config.TextColumn(
            "organelle-fluor rollup", disabled=True, width="large"
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

st.markdown("---")
st.subheader("Step 3 — Instances for selected line")

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
            "allele_canonical_rollup",
            "allele_label_rollup",
            "n_constructs",
            "n_fluors",
            "all_fluor_tag_rollup",
            "all_organelle_fluor_rollup",
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
        if "allele_canonical_rollup" in inst_df.columns:
            cfg["allele_canonical_rollup"] = st.column_config.TextColumn(
                "Alleles (canonical)", disabled=True, width="large"
            )
        if "allele_label_rollup" in inst_df.columns:
            cfg["allele_label_rollup"] = st.column_config.TextColumn(
                "Alleles (labels)", disabled=True, width="large"
            )
        if "n_constructs" in inst_df.columns:
            cfg["n_constructs"] = st.column_config.NumberColumn(
                "n constructs", disabled=True
            )
        if "n_fluors" in inst_df.columns:
            cfg["n_fluors"] = st.column_config.NumberColumn(
                "n fluors", disabled=True
            )
        if "all_fluor_tag_rollup" in inst_df.columns:
            cfg["all_fluor_tag_rollup"] = st.column_config.TextColumn(
                "fluor::tag(tag_pos)", disabled=True, width="large"
            )
        if "all_organelle_fluor_rollup" in inst_df.columns:
            cfg["all_organelle_fluor_rollup"] = st.column_config.TextColumn(
                "organelle-fluor rollup", disabled=True, width="large"
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
            tab1, tab2, tab3 = st.tabs(["Overview", "Alleles", "Markers"])

            with tab1:
                d: Dict[str, Any] = {}
                _maybe(d, r, "fish_code")
                _maybe(d, r, "genetic_background", "background")
                _maybe(d, r, "genotype_pretty")
                _maybe(d, r, "birthday")
                st.write(d)

            with tab2:
                d: Dict[str, Any] = {}
                _maybe(d, r, "allele_canonical_rollup", "alleles (canonical)")
                _maybe(d, r, "allele_label_rollup", "alleles (labels)")
                st.write(d)

            with tab3:
                d: Dict[str, Any] = {}
                _maybe(d, r, "n_constructs")
                _maybe(d, r, "n_fluors")
                _maybe(d, r, "all_fluor_tag_rollup", "fluor::tag(tag_pos)")
                _maybe(d, r, "all_organelle_fluor_rollup", "organelle-fluor rollup")
                st.write(d)
        else:
            subset = grid_inst.loc[sel_idxs].reset_index(drop=True)
            cols_summary = [
                c
                for c in [
                    "genetic_background",
                    "genotype_pretty",
                    "allele_canonical_rollup",
                ]
                if c in subset.columns
            ]
            st.write("Summary for selected instances:")
            st.dataframe(
                subset[cols_summary],
                use_container_width=True,
            )