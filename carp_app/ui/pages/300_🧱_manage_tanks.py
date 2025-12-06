# carp_app/ui/pages/320_🧱_manage_tanks.py
# 🧱 Manage tanks (v11) — fish → tanks

from __future__ import annotations

import sys
import pathlib
from datetime import date
from typing import Optional, Dict, Any, List

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ───────── repo bootstrap ─────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock() -> None:
        ...
from carp_app.ui.lib.app_ctx import get_engine  # core hook

# ───────── constants ─────────
V_TANKS_OVERVIEW = "public.v_tanks_overview"
V_FISH_INSTANCE_LABELS = "public.v11_fish_instance_star_labels"
TANK_STATUS_OPTIONS = ["active", "to_kill", "inactive"]

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🧱 Manage tanks (fish → tanks)",
    page_icon="🧱",
    layout="wide",
)
st.title("🧱 Manage tanks — fish → tanks")


def eng() -> Engine:
    return get_engine()


def _norm(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None


# ════════════════════════════════════════════════════════
# STEP 1 — FISH INSTANCES (v11) WITH 3 GENOTYPE STYLES
# ════════════════════════════════════════════════════════

with st.form("fish_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        q_raw = st.text_input(
            "Search fish (FSH / line / nickname / background / genotype)",
            "",
        )
    with c2:
        lim = int(
            st.number_input(
                "Limit",
                min_value=50,
                max_value=5000,
                value=500,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply", key="fish_apply")

q = _norm(q_raw)

where: List[str] = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  fis.fish_code ILIKE :ql"
        " OR COALESCE(fis.line_code,'') ILIKE :ql"
        " OR COALESCE(fis.line_nickname,'') ILIKE :ql"
        " OR COALESCE(fis.genetic_background,'') ILIKE :ql"
        " OR COALESCE(fis.genotype_tg_style,'') ILIKE :ql"
        " OR COALESCE(fis.genotype_fluortag_style,'') ILIKE :ql"
        " OR COALESCE(fis.genotype_fluororganelle_style,'') ILIKE :ql"
        ")"
    )

where_sql = " AND ".join(where)

sql_fish = text(
    f"""
    SELECT
      fis.fish_instance_id::text          AS fish_instance_id,
      fis.fish_code,
      fis.line_code,
      fis.line_nickname,
      fis.genetic_background,
      fis.instance_stage,
      fis.birthday,
      fis.genotype_tg_style,
      fis.genotype_fluortag_style,
      fis.genotype_fluororganelle_style
    FROM {V_FISH_INSTANCE_LABELS} fis
    WHERE {where_sql}
    ORDER BY fis.birthday DESC NULLS LAST, fis.fish_code
    LIMIT :lim;
    """
)

with eng().begin() as cx:
    df_fish = pd.read_sql(sql_fish, cx, params=params)

df_fish = df_fish.fillna("")
st.caption(f"{len(df_fish)} fish instance(s)")

if df_fish.empty:
    st.info("No fish instances match the current filters.")
    st.stop()

fish_view = df_fish.copy()
fish_view.insert(0, "✓ Select", False)

fish_grid = st.data_editor(
    fish_view[
        [
            "✓ Select",
            "fish_code",
            "line_code",
            "line_nickname",
            "genetic_background",
            "instance_stage",
            "birthday",
            "genotype_tg_style",
            "genotype_fluortag_style",
            "genotype_fluororganelle_style",
        ]
    ],
    key="fish_manage_overview",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "fish_code": st.column_config.TextColumn("Fish code", disabled=True),
        "line_code": st.column_config.TextColumn("Line code", disabled=True),
        "line_nickname": st.column_config.TextColumn(
            "Line nickname", disabled=True, width="large"
        ),
        "genetic_background": st.column_config.TextColumn(
            "Background", disabled=True
        ),
        "instance_stage": st.column_config.TextColumn("Stage", disabled=True),
        "birthday": st.column_config.DateColumn("Birthday", disabled=True),
        "genotype_tg_style": st.column_config.TextColumn(
            "Genotype (tg)", disabled=True, width="large"
        ),
        "genotype_fluortag_style": st.column_config.TextColumn(
            "Genotype (fluor-tag)", disabled=True, width="large"
        ),
        "genotype_fluororganelle_style": st.column_config.TextColumn(
            "Genotype (fluor-organelle)", disabled=True, width="large"
        ),
    },
)

fish_sel_mask = (
    fish_grid.get("✓ Select", pd.Series(False, index=fish_grid.index))
    .fillna(False)
    .astype(bool)
)
selected_fish = df_fish[fish_sel_mask].reset_index(drop=True)

if selected_fish.empty:
    st.caption("Selected fish: 0")
else:
    st.caption(f"Selected fish: {len(selected_fish)}")

fish_codes_selected = selected_fish["fish_code"].tolist()

# ════════════════════════════════════════════════════════
# STEP 2 — TANKS FOR SELECTED FISH
# ════════════════════════════════════════════════════════

st.markdown("---")
st.subheader("Step 2 — Tanks for selected fish", anchor=False)

if not fish_codes_selected:
    st.info("Select one or more fish above to see their tanks.")
    df_tanks = pd.DataFrame()
    selected_tanks = pd.DataFrame()
else:
    sql_tanks = text(
        f"""
        SELECT
          t.tank_id::text AS tank_id,
          t.tank_code,
          t.fish_code,
          t.status,
          t.created_at
        FROM {V_TANKS_OVERVIEW} t
        WHERE t.fish_code = ANY(:codes)
        ORDER BY t.created_at DESC NULLS LAST, t.tank_code;
        """
    )
    with eng().begin() as cx:
        df_tanks = pd.read_sql(sql_tanks, cx, params={"codes": fish_codes_selected})

    df_tanks = df_tanks.fillna("")
    st.caption(f"{len(df_tanks)} tank(s) for selected fish")

    if df_tanks.empty:
        st.info("No tanks yet for these fish.")
        selected_tanks = pd.DataFrame()
    else:
        t_view = df_tanks.copy()
        sel_tank_col = "✓ Select tank"
        if sel_tank_col not in t_view.columns:
            t_view.insert(0, sel_tank_col, False)

        t_grid = st.data_editor(
            t_view[
                [
                    sel_tank_col,
                    "tank_id",
                    "tank_code",
                    "fish_code",
                    "status",
                    "created_at",
                ]
            ],
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                sel_tank_col: st.column_config.CheckboxColumn("✓", default=False),
                "tank_id": st.column_config.TextColumn("Tank id", disabled=True),
                "tank_code": st.column_config.TextColumn("Tank code", disabled=True),
                "fish_code": st.column_config.TextColumn(
                    "Fish code", disabled=True
                ),
                "status": st.column_config.SelectboxColumn(
                    "Status", options=TANK_STATUS_OPTIONS
                ),
                "created_at": st.column_config.DatetimeColumn(
                    "Created at", disabled=True
                ),
            },
            key="tank_picker_manage_v11",
        )

        t_mask = (
            t_grid.get(sel_tank_col, pd.Series(False, index=t_grid.index))
            .fillna(False)
            .astype(bool)
        )
        selected_tanks = t_grid[t_mask].copy()
        if selected_tanks.empty:
            st.caption("Selected tanks: 0")
        else:
            st.caption(f"Selected tanks: {len(selected_tanks)}")

# ════════════════════════════════════════════════════════
# STEP 3 — BULK ACTIONS ON SELECTED TANK(S)
# ════════════════════════════════════════════════════════

st.markdown("---")
st.subheader("Step 3 — Bulk actions on selected tank(s)", anchor=False)

c_left, c_right = st.columns(2)

# ── Bulk status change ──────────────────────────────────
with c_left:
    st.markdown("**Change status of selected tanks**")
    bulk_status = st.selectbox(
        "New status for selected tanks",
        options=TANK_STATUS_OPTIONS,
        index=0,
        key="bulk_tank_status",
    )
    if st.button("💾 Apply status to selected tanks", use_container_width=True):
        if selected_tanks.empty:
            st.warning("Select one or more tanks in Step 2 to change their status.")
        else:
            try:
                update_sql = text(
                    """
                    UPDATE public.tanks
                    SET status = :status
                    WHERE id = :id::uuid
                    """
                )
                with eng().begin() as cx:
                    for _, r in selected_tanks.iterrows():
                        cx.execute(
                            update_sql,
                            {"id": r["tank_id"], "status": bulk_status},
                        )
                st.success(
                    f"Updated status to '{bulk_status}' for {len(selected_tanks)} tank(s)."
                )
            except Exception as e:
                st.error(f"Failed to update tank status: {type(e).__name__}: {e}")

# ── Add N more tanks per selected tank's fish ────────────
with c_right:
    st.markdown("**Add new tank(s) for the fish in selected tanks**")
    new_status = st.selectbox(
        "Status for new tanks",
        options=TANK_STATUS_OPTIONS,
        index=0,
        key="new_tank_status",
    )
    tank_date = st.date_input(
        "New tank created date",
        value=date.today(),
        key="new_tank_date",
    )
    new_count = int(
        st.number_input(
            "New tanks per selected tank",
            min_value=1,
            max_value=20,
            value=1,
            step=1,
            key="new_tank_count",
        )
    )

    def _resolve_fish_instance_id_from_fish_code(code: str) -> Optional[str]:
        """
        Given an FSH fish_code, resolve the fish_instances_v10.id.
        """
        code = (code or "").strip()
        if not code:
            return None
        with eng().begin() as cx:
            row = cx.execute(
                text(
                    """
                    SELECT id::text
                    FROM public.fish_instances_v10
                    WHERE fish_code = :fc
                    LIMIT 1
                    """
                ),
                {"fc": code},
            ).fetchone()
        return row[0] if row and row[0] else None

    def _create_additional_tanks_for_fish_code(
        fish_code: str, status: str, created_at: date, count: int
    ) -> List[str]:
        """
        Add `count` new tanks for this fish instance.

        Pattern: {FSH}-TANK2, TANK3, ... based on existing tanks.
        """
        fish_code = (fish_code or "").strip()
        if not fish_code or count <= 0:
            return []

        fi_id = _resolve_fish_instance_id_from_fish_code(fish_code)
        if not fi_id:
            raise RuntimeError(
                f"Could not resolve fish_code {fish_code} to a fish instance."
            )

        base = f"{fish_code}-TANK"

        with eng().begin() as cx:
            max_n_row = cx.execute(
                text(
                    r"""
                    SELECT COALESCE(
                    MAX(
                        NULLIF(
                        regexp_replace(tank_code, '^.*-TANK([0-9]+)$', '\1'),
                        ''
                        )::int
                    ),
                    0
                    ) AS max_n
                    FROM public.tanks
                    WHERE fish_instance_id = :fid
                    OR tank_code LIKE :base || '%';
                    """
                ),
                {"fid": fi_id, "base": base},
            ).fetchone()
            max_n = int(max_n_row._mapping["max_n"]) if max_n_row else 0

            created_codes: List[str] = []
            insert_sql = text(
                """
                INSERT INTO public.tanks (
                id,
                tank_code,
                status,
                created_at,
                fish_instance_id
                )
                VALUES (
                gen_random_uuid(),
                :tank_code,
                :status,
                :created_at,
                :fid
                )
                """
            )

            for i in range(1, count + 1):
                n = max_n + i
                tank_code = f"{base}{n}"
                cx.execute(
                    insert_sql,
                    {
                        "tank_code": tank_code,
                        "status": status,
                        "created_at": created_at,
                        "fid": fi_id,
                    },
                )
                created_codes.append(tank_code)

        return created_codes

    if st.button(
        "➕ Add tank(s) for selected fish",
        use_container_width=True,
        key="create_tanks_btn_v11",
    ):
        if selected_tanks.empty:
            st.warning(
                "Select one or more tanks in Step 2 to create new tanks for their fish."
            )
        else:
            created_codes: List[str] = []
            try:
                for _, r in selected_tanks.iterrows():
                    fish_code = (r.get("fish_code") or "").strip()
                    if not fish_code:
                        continue
                    codes = _create_additional_tanks_for_fish_code(
                        fish_code, new_status, tank_date, new_count
                    )
                    created_codes.extend(codes)
            except Exception as e:
                st.error(f"Failed to create tanks: {type(e).__name__}: {e}")
            else:
                if created_codes:
                    st.success(
                        f"Created {len(created_codes)} new tank(s): "
                        + ", ".join(created_codes)
                    )
                else:
                    st.info(
                        "No tanks were created (no valid fish_code on selected rows)."
                    )