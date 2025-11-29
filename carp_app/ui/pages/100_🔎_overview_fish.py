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

from carp_app.ui.lib.page_engine import engine  # core engine hook

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview: Fish",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 Overview: Fish (groups → lines → instances)")


# ───────── engine (centralized) ─────────
def _eng() -> Engine:
    return engine()


def _norm(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# small helper for conditional dict entries
def _maybe(d: Dict[str, Any], row: pd.Series, col: str, label: Optional[str] = None):
    if col in row.index:
        d[label or col] = row[col]


# ════════════════════════════════════════════════════════
# STEP 1 — FISH GROUPS (v_fish_groups_overview)
# ════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def load_groups() -> pd.DataFrame:
    sql = text(
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
        ORDER BY group_code;
        """
    )
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx)
    return df.fillna("")


groups_df = load_groups()

st.subheader("Step 1 — Fish groups")

if groups_df.empty:
    st.info("No fish groups found.")
    st.stop()

with st.form("group_filters", clear_on_submit=False):
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
        min_lines = st.number_input(
            "Min lines (optional)",
            min_value=0,
            value=0,
            step=1,
        )
    _ = st.form_submit_button("Apply", use_container_width=True)

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

if min_lines > 0:
    filtered = filtered[filtered["n_lines"] >= min_lines]

if filtered.empty:
    st.warning("No groups match the current filters.")
    st.stop()

st.caption(f"{len(filtered)} group(s)")

groups_display = filtered[
    [
        "fish_group_id",
        "basecode_genotype",
        "fluor_tag",
        "organelle_fluor",
        "group_code",
        "n_lines",
        "n_instances",
        "first_birthday",
        "last_birthday",
        "genotype_key",
    ]
].copy()

groups_display.insert(0, "✓", False)

edited_groups = st.data_editor(
    groups_display,
    use_container_width=True,
    num_rows="fixed",
    key="groups_editor_v11",
    column_config={
        "✓": st.column_config.CheckboxColumn("Select", width=60),
        "fish_group_id": st.column_config.Column(
            "fish_group_id", width=0, disabled=True
        ),
        "basecode_genotype": st.column_config.Column(
            "Genotype (basecode set)"
        ),
        "fluor_tag": st.column_config.Column("fluor::tag(tag_pos)"),
        "organelle_fluor": st.column_config.Column("organelle-fluor"),
        "n_lines": st.column_config.NumberColumn("n lines", disabled=True),
        "n_instances": st.column_config.NumberColumn("n instances", disabled=True),
    },
    hide_index=True,
)

selected_group_rows = edited_groups[edited_groups["✓"]]
if not selected_group_rows.empty:
    selected_group_id = selected_group_rows.iloc[0]["fish_group_id"]
else:
    selected_group_id = groups_display.iloc[0]["fish_group_id"]

st.caption("Select one group above to see its linked lines and linked instances.")


# ════════════════════════════════════════════════════════
# STEP 2 — LINES FOR SELECTED GROUP
# ════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def load_lines_for_group(fish_group_id: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          fl.id::text AS line_id,
          fl.line_code,
          fl.nickname,
          fl.genetic_background,
          fl.line_building_stage,
          fl.group_instance_code,
          la.allele_label_rollup AS genotype_pretty,
          COUNT(DISTINCT fi.id) AS n_instances,
          MIN(fi.birthday) AS first_birthday,
          MAX(fi.birthday) AS last_birthday
        FROM public.fish_lines fl
        LEFT JOIN public.fish_instances_v10 fi
          ON fi.line_id = fl.id
        LEFT JOIN public.v11_line_allele_rollups la
          ON la.line_id = fl.id
        WHERE fl.fish_group_id = :fish_group_id
        GROUP BY
          fl.id,
          fl.line_code,
          fl.nickname,
          fl.genetic_background,
          fl.line_building_stage,
          fl.group_instance_code,
          la.allele_label_rollup
        ORDER BY fl.line_code;
        """
    )
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"fish_group_id": fish_group_id})
    return df.fillna("")


st.markdown("---")
st.subheader("Step 2 — Lines in selected group")

lines_df = load_lines_for_group(selected_group_id)

if lines_df.empty:
    st.caption("No lines found for this group.")
    selected_line_id: Optional[str] = None
else:
    lines_display = lines_df[
        [
            "line_id",
            "line_code",
            "nickname",
            "genetic_background",
            "line_building_stage",
            "group_instance_code",
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
        key=f"lines_editor_{selected_group_id}",
        column_config={
            "✓": st.column_config.CheckboxColumn("Select", width=60),
            "line_id": st.column_config.Column("line_id", width=0, disabled=True),
            "line_code": st.column_config.TextColumn("Line code", disabled=True),
            "nickname": st.column_config.TextColumn(
                "Nickname", disabled=True, width="large"
            ),
            "genetic_background": st.column_config.TextColumn(
                "Background", disabled=True
            ),
            "line_building_stage": st.column_config.TextColumn(
                "Stage", disabled=True
            ),
            "group_instance_code": st.column_config.TextColumn(
                "Group instance", disabled=True
            ),
            "genotype_pretty": st.column_config.TextColumn(
                "Genotype", disabled=True, width="large"
            ),
            "n_instances": st.column_config.NumberColumn(
                "n instances", disabled=True
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
# STEP 3 — INSTANCES FOR SELECTED LINE
# ════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def load_instances_for_line(line_id: str) -> pd.DataFrame:
    """
    Load all columns from v11_fish_instance_star for a given line_id.
    We then conditionally show summary fields that actually exist.
    """
    sql = text(
        """
        SELECT *
        FROM public.v11_fish_instance_star fis
        WHERE fis.line_id = :line_id
        ORDER BY fis.fish_code, fis.birthday NULLS LAST;
        """
    )
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"line_id": line_id})
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df.fillna("")


st.markdown("---")
st.subheader("Step 3 — Instances for selected line")

if not selected_line_id:
    st.caption("No line selected or no lines in this group.")
else:
    inst_df = load_instances_for_line(selected_line_id)

    if inst_df.empty:
        st.caption("No instances found for this line.")
    else:
        # Desired column order (only those that exist will be used)
        desired_order = [
            "fish_code",
            "genetic_background",
            "genotype_pretty",
            "birthday",
            "tank_status",
            "tank_code",
            "n_transgenes",
            "n_fluors",
            "all_fluor_tag_rollup",
            "all_organelle_fluor_rollup",
            "transgene_code",
            "treatment_code",
            "line_instance_code",
            "line_code",
            "group_code",
            "line_nickname",
            "line_building_stage",
            "fluor_codes",
            "tag_codes",
            "organelle_fluors",
            "tank_created_at",
        ]

        cols_present = [c for c in desired_order if c in inst_df.columns]

        view_inst = inst_df.copy()
        view_inst.insert(0, "✓ Select", False)

        column_order = ["✓ Select"] + cols_present

        # Build column_config only for present columns
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
        if "tank_status" in inst_df.columns:
            cfg["tank_status"] = st.column_config.TextColumn(
                "Status", disabled=True
            )
        if "tank_code" in inst_df.columns:
            cfg["tank_code"] = st.column_config.TextColumn(
                "Tank code", disabled=True
            )
        if "n_transgenes" in inst_df.columns:
            cfg["n_transgenes"] = st.column_config.NumberColumn(
                "n_transgenes", disabled=True
            )
        if "n_fluors" in inst_df.columns:
            cfg["n_fluors"] = st.column_config.NumberColumn(
                "n_fluors", disabled=True
            )
        if "all_fluor_tag_rollup" in inst_df.columns:
            cfg["all_fluor_tag_rollup"] = st.column_config.TextColumn(
                "all_fluor_tag_rollup (fluor::tag(pos))",
                disabled=True,
                width="large",
            )
        if "all_organelle_fluor_rollup" in inst_df.columns:
            cfg["all_organelle_fluor_rollup"] = st.column_config.TextColumn(
                "all_organelle_fluor_rollup (organelle-fluor)",
                disabled=True,
                width="large",
            )
        if "transgene_code" in inst_df.columns:
            cfg["transgene_code"] = st.column_config.TextColumn(
                "Transgene code", disabled=True
            )
        if "treatment_code" in inst_df.columns:
            cfg["treatment_code"] = st.column_config.TextColumn(
                "Treatment code", disabled=True
            )
        if "line_instance_code" in inst_df.columns:
            cfg["line_instance_code"] = st.column_config.TextColumn(
                "LINE instance", disabled=True
            )
        if "line_code" in inst_df.columns:
            cfg["line_code"] = st.column_config.TextColumn(
                "LINE code", disabled=True
            )
        if "group_code" in inst_df.columns:
            cfg["group_code"] = st.column_config.TextColumn(
                "Group", disabled=True
            )
        if "line_nickname" in inst_df.columns:
            cfg["line_nickname"] = st.column_config.TextColumn(
                "Line nickname", disabled=True
            )
        if "line_building_stage" in inst_df.columns:
            cfg["line_building_stage"] = st.column_config.TextColumn(
                "Stage", disabled=True
            )
        if "fluor_codes" in inst_df.columns:
            cfg["fluor_codes"] = st.column_config.TextColumn(
                "Fluor codes", disabled=True
            )
        if "tag_codes" in inst_df.columns:
            cfg["tag_codes"] = st.column_config.TextColumn(
                "Tag codes", disabled=True
            )
        if "organelle_fluors" in inst_df.columns:
            cfg["organelle_fluors"] = st.column_config.TextColumn(
                "Organelle-fluor (legacy)", disabled=True
            )
        if "tank_created_at" in inst_df.columns:
            cfg["tank_created_at"] = st.column_config.DatetimeColumn(
                "Tank created", disabled=True
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

        # ── Drill-down for selected instance(s) ─────────────────────────────
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
            tab1, tab2, tab3 = st.tabs(["Overview", "Genetics", "Tank"])

            with tab1:
                d: Dict[str, Any] = {}
                _maybe(d, r, "fish_code")
                _maybe(d, r, "genetic_background", "background")
                _maybe(d, r, "genotype_pretty")
                _maybe(d, r, "birthday")
                _maybe(d, r, "tank_status", "status")
                _maybe(d, r, "tank_code")
                _maybe(d, r, "n_transgenes")
                _maybe(d, r, "n_fluors")
                _maybe(d, r, "transgene_code")
                _maybe(d, r, "treatment_code")
                st.write(d)

            with tab2:
                d: Dict[str, Any] = {}
                _maybe(d, r, "line_code")
                _maybe(d, r, "line_instance_code")
                _maybe(d, r, "line_nickname")
                _maybe(d, r, "line_building_stage", "stage")
                _maybe(d, r, "all_fluor_tag_rollup")
                _maybe(d, r, "all_organelle_fluor_rollup")
                _maybe(d, r, "fluor_codes")
                _maybe(d, r, "tag_codes")
                _maybe(d, r, "organelle_fluors", "organelle_fluors (legacy)")
                st.write(d)

            with tab3:
                d: Dict[str, Any] = {}
                _maybe(d, r, "tank_code")
                _maybe(d, r, "tank_status")
                _maybe(d, r, "tank_created_at")
                st.write(d)
        else:
            subset = grid_inst.loc[sel_idxs].reset_index(drop=True)
            cols_summary = [
                c
                for c in [
                    "genetic_background",
                    "genotype_pretty",
                    "n_transgenes",
                    "n_fluors",
                    "tank_status",
                    "tank_code",
                ]
                if c in subset.columns
            ]
            st.write("Summary for selected instances:")
            st.dataframe(
                subset[cols_summary],
                use_container_width=True,
            )