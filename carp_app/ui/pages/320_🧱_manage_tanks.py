# carp_app/ui/pages/320_🧱_manage_tanks.py
# 🧱 Manage tanks (v11) — fish_groups → lines → instances → tanks
from __future__ import annotations

import sys
import pathlib
from datetime import date
from typing import Optional, Dict, Any, List, Tuple

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

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🧱 Manage tanks (drilldown)",
    page_icon="🧱",
    layout="wide",
)
st.title("🧱 Manage tanks — fish groups → lines → instances → tanks")


def eng() -> Engine:
    return get_engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


def _exists(qualified: str, kind: str = "view") -> bool:
    schema, name = qualified.split(".", 1)
    with eng().begin() as cx:
        if kind == "view":
            df = pd.read_sql(
                text(
                    """
                    SELECT 1
                    FROM information_schema.views
                    WHERE table_schema = :s AND table_name = :n
                    UNION ALL
                    SELECT 1
                    FROM pg_catalog.pg_matviews
                    WHERE schemaname = :s AND matviewname = :n
                    LIMIT 1
                    """
                ),
                cx,
                params={"s": schema, "n": name},
            )
        else:
            df = pd.read_sql(
                text(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = :s AND table_name = :n
                    LIMIT 1
                    """
                ),
                cx,
                params={"s": schema, "n": name},
            )
    return not df.empty


V_FISH_GROUP_STAR = "public.v11_fish_group_star"
V_FISH_LINE_STAR = "public.v11_fish_line_star"
V_TANKS_OVERVIEW = "public.v_tanks_overview"
TANK_STATUS_OPTIONS = ["active", "to_kill", "inactive"]

REQUIRED = [
    (V_FISH_GROUP_STAR, "view"),
    (V_FISH_LINE_STAR, "view"),
    ("public.fish_instances_v10", "table"),
    (V_TANKS_OVERVIEW, "view"),
]
for obj, kind in REQUIRED:
    if not _exists(obj, kind):
        st.error(f"Required {kind} {obj} not found.")
        st.stop()

# ════════════════════════════════════════════════════════
# STEP 1 — FISH GROUPS (with #lines, #instances, #tanks)
# ════════════════════════════════════════════════════════

st.subheader("Step 1 — Fish groups", anchor=False)

with st.form("group_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        g_q_raw = st.text_input(
            "Search groups (construct/genotype rollup / line nicknames / backgrounds)",
            "",
        )
    with c2:
        g_lim = int(
            st.number_input("Limit", min_value=10, max_value=3000, value=500, step=50)
        )
    st.form_submit_button("Apply", use_container_width=True)

g_q = _norm(g_q_raw)

sql_groups = text(
    f"""
    WITH groups AS (
      SELECT
        g.group_transgene_rollup       AS group_key,
        g.group_line_codes             AS group_line_codes,
        g.group_line_nicknames         AS group_line_nicknames,
        g.group_genetic_backgrounds    AS group_backgrounds
      FROM {V_FISH_GROUP_STAR} g
      WHERE (
            :q IS NULL
        OR  g.group_transgene_rollup    ILIKE :ql
        OR  g.group_line_nicknames      ILIKE :ql
        OR  g.group_genetic_backgrounds ILIKE :ql
      )
    ),
    line_counts AS (
      SELECT
        line_transgene_rollup AS group_key,
        COUNT(*)::int         AS n_lines
      FROM {V_FISH_LINE_STAR}
      GROUP BY line_transgene_rollup
    ),
    inst_counts AS (
      SELECT
        fls.line_transgene_rollup AS group_key,
        COUNT(fi.id)::int         AS n_instances
      FROM public.fish_instances_v10 fi
      JOIN {V_FISH_LINE_STAR} fls
        ON fls.line_id = fi.line_id
      GROUP BY fls.line_transgene_rollup
    ),
    tank_counts AS (
      SELECT
        fls.line_transgene_rollup AS group_key,
        COUNT(DISTINCT t.tank_id)::int AS n_tanks
      FROM public.fish_instances_v10 fi
      JOIN {V_FISH_LINE_STAR} fls
        ON fls.line_id = fi.line_id
      JOIN {V_TANKS_OVERVIEW} t
        ON t.fish_code = fi.line_instance_code
      GROUP BY fls.line_transgene_rollup
    )
    SELECT
      g.group_key,
      g.group_line_codes,
      g.group_line_nicknames,
      g.group_backgrounds,
      COALESCE(lc.n_lines, 0)      AS n_lines,
      COALESCE(ic.n_instances, 0)  AS n_instances,
      COALESCE(tc.n_tanks, 0)      AS n_tanks
    FROM groups g
    LEFT JOIN line_counts lc ON lc.group_key = g.group_key
    LEFT JOIN inst_counts ic ON ic.group_key = g.group_key
    LEFT JOIN tank_counts tc ON tc.group_key = g.group_key
    ORDER BY g.group_key
    LIMIT :lim;
    """
)

params_groups = {
    "q": g_q,
    "ql": f"%{g_q}%" if g_q else None,
    "lim": g_lim,
}

with eng().begin() as cx:
    df_groups = pd.read_sql(sql_groups, cx, params=params_groups)

for c in df_groups.select_dtypes(include=["object"]).columns:
    df_groups[c] = df_groups[c].astype("string").fillna("")

st.caption(f"{len(df_groups)} group(s)")

if df_groups.empty:
    st.info("No fish groups found.")
    st.stop()

g_view = df_groups.copy()
sel_group_col = "✓ Select"
if sel_group_col not in g_view.columns:
    g_view.insert(0, sel_group_col, False)

cx_groups = st.data_editor(
    g_view[
        [
            sel_group_col,
            "group_key",
            "group_line_nicknames",
            "group_backgrounds",
            "n_lines",
            "n_instances",
            "n_tanks",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        sel_group_col: st.column_config.CheckboxColumn("✓", default=False),
        "group_key": st.column_config.TextColumn(
            "Construct/genotype rollup", disabled=True, width="large"
        ),
        "group_line_nicknames": st.column_config.TextColumn(
            "Line nicknames", disabled=True, width="large"
        ),
        "group_backgrounds": st.column_config.TextColumn(
            "Backgrounds", disabled=True, width="large"
        ),
        "n_lines": st.column_config.NumberColumn("# lines", disabled=True),
        "n_instances": st.column_config.NumberColumn("# instances", disabled=True),
        "n_tanks": st.column_config.NumberColumn("# tanks", disabled=True),
    },
    key="group_picker_v11",
)

g_mask = (
    cx_groups.get(sel_group_col, pd.Series(False, index=cx_groups.index))
    .fillna(False)
    .astype(bool)
)
chosen_groups = df_groups[g_mask].reset_index(drop=True)
st.caption(f"Selected group(s): {len(chosen_groups)}")

if chosen_groups.empty:
    st.stop()

group_row = chosen_groups.iloc[0]
group_key = group_row["group_key"]
st.caption(f"Using group: **{group_key}**")

# ════════════════════════════════════════════════════════
# STEP 2 — LINES FOR SELECTED GROUP
# ════════════════════════════════════════════════════════

st.subheader("Step 2 — Lines in this group", anchor=False)

sql_lines = text(
    f"""
    WITH base AS (
      SELECT
        fls.line_id::text          AS line_id,
        fls.line_code::text        AS line_code,
        fls.line_nickname::text    AS nickname,
        COALESCE(fls.genetic_background,'')::text   AS genetic_background,
        COALESCE(fls.line_building_stage,'')::text  AS line_building_stage
      FROM {V_FISH_LINE_STAR} fls
      WHERE fls.line_transgene_rollup = :gkey
    )
    SELECT
      b.line_id,
      b.line_code,
      b.nickname,
      b.genetic_background,
      b.line_building_stage,
      (SELECT COUNT(*)::int
         FROM public.fish_instances_v10 fi
        WHERE fi.line_id = b.line_id::uuid) AS n_instances,
      (SELECT COUNT(DISTINCT t.tank_id)::int
         FROM public.fish_instances_v10 fi
         JOIN {V_TANKS_OVERVIEW} t ON t.fish_code = fi.line_instance_code
        WHERE fi.line_id = b.line_id::uuid) AS n_tanks
    FROM base b
    ORDER BY b.line_code;
    """
)

with eng().begin() as cx:
    df_lines = pd.read_sql(sql_lines, cx, params={"gkey": group_key})

for c in df_lines.select_dtypes(include=["object"]).columns:
    df_lines[c] = df_lines[c].astype("string").fillna("")

st.caption(f"{len(df_lines)} line(s) in group")

if df_lines.empty:
    st.info("No lines for this group.")
    st.stop()

l_view = df_lines.copy()
sel_line_col = "✓ Select line"
if sel_line_col not in l_view.columns:
    l_view.insert(0, sel_line_col, False)

cx_lines = st.data_editor(
    l_view[
        [
            sel_line_col,
            "line_code",
            "nickname",
            "genetic_background",
            "line_building_stage",
            "n_instances",
            "n_tanks",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        sel_line_col: st.column_config.CheckboxColumn("✓", default=False),
        "line_code": st.column_config.TextColumn("Line code", disabled=True),
        "nickname": st.column_config.TextColumn(
            "Nickname", disabled=True, width="large"
        ),
        "genetic_background": st.column_config.TextColumn(
            "Background", disabled=True
        ),
        "line_building_stage": st.column_config.TextColumn("Stage", disabled=True),
        "n_instances": st.column_config.NumberColumn("# instances", disabled=True),
        "n_tanks": st.column_config.NumberColumn("# tanks", disabled=True),
    },
    key="line_picker_v11",
)

l_mask = (
    cx_lines.get(sel_line_col, pd.Series(False, index=cx_lines.index))
    .fillna(False)
    .astype(bool)
)
chosen_lines = df_lines[l_mask].reset_index(drop=True)
st.caption(f"Selected line(s): {len(chosen_lines)}")

if chosen_lines.empty:
    st.stop()

line_ids = chosen_lines["line_id"].tolist()

# ════════════════════════════════════════════════════════
# STEP 3 — INSTANCES FOR SELECTED LINES
# ════════════════════════════════════════════════════════

st.subheader("Step 3 — Instances for selected line(s)", anchor=False)

sql_instances = text(
    f"""
    WITH picked AS (
      SELECT unnest(:line_ids)::uuid AS line_id
    )
    SELECT
      fi.id::text                  AS fish_instance_id,
      COALESCE(fi.fish_code,'')    AS fish_code,
      fi.line_instance_code::text  AS line_instance_code,
      fi.birthday                  AS birthday,
      COALESCE(fi.notes,'')        AS notes,
      COUNT(DISTINCT t.tank_id)    AS n_tanks
    FROM public.fish_instances_v10 fi
    JOIN picked p ON p.line_id = fi.line_id
    LEFT JOIN {V_TANKS_OVERVIEW} t
      ON t.fish_code = fi.line_instance_code
    GROUP BY fi.id, fi.fish_code, fi.line_instance_code, fi.birthday, fi.notes
    ORDER BY fi.birthday DESC NULLS LAST, fi.fish_code;
    """
)

with eng().begin() as cx:
    df_instances = pd.read_sql(sql_instances, cx, params={"line_ids": line_ids})

for c in df_instances.select_dtypes(include=["object"]).columns:
    df_instances[c] = df_instances[c].astype("string").fillna("")

st.caption(f"{len(df_instances)} instance(s) in selected line(s)")

if df_instances.empty:
    st.info("No instances for selected lines.")
    st.stop()

i_view = df_instances.copy()
sel_inst_col = "✓ Select instance"
if sel_inst_col not in i_view.columns:
    i_view.insert(0, sel_inst_col, False)

cx_inst = st.data_editor(
    i_view[
        [
            sel_inst_col,
            "fish_code",
            "line_instance_code",
            "birthday",
            "n_tanks",
            "notes",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        sel_inst_col: st.column_config.CheckboxColumn("✓", default=False),
        "fish_code": st.column_config.TextColumn("Fish code", disabled=True),
        "line_instance_code": st.column_config.TextColumn(
            "Line instance", disabled=True
        ),
        "birthday": st.column_config.DateColumn("Birthday", disabled=True),
        "n_tanks": st.column_config.NumberColumn("# tanks", disabled=True),
        "notes": st.column_config.TextColumn("Notes", disabled=True, width="large"),
    },
    key="instance_picker_v11",
)

inst_mask = (
    cx_inst.get(sel_inst_col, pd.Series(False, index=cx_inst.index))
    .fillna(False)
    .astype(bool)
)
chosen_instances = df_instances[inst_mask].reset_index(drop=True)
st.caption(f"Selected instance(s): {len(chosen_instances)}")

if chosen_instances.empty:
    st.stop()

line_instance_codes = chosen_instances["line_instance_code"].tolist()

# ════════════════════════════════════════════════════════
# STEP 4 — TANKS FOR SELECTED INSTANCES
# ════════════════════════════════════════════════════════

st.subheader("Step 4 — Tanks for selected instance(s)", anchor=False)

sql_tanks = text(
    f"""
    SELECT
      tank_id,
      tank_code,
      fish_code,
      status,
      created_at
    FROM {V_TANKS_OVERVIEW}
    WHERE fish_code = ANY(:codes)
    ORDER BY created_at DESC NULLS LAST, tank_code;
    """
)

with eng().begin() as cx:
    df_tanks = pd.read_sql(sql_tanks, cx, params={"codes": line_instance_codes})

df_tanks = df_tanks.fillna("")
st.caption(f"{len(df_tanks)} tank(s) for selected instance(s)")

if df_tanks.empty:
    st.info("No tanks yet for these instances.")
else:
    t_view = df_tanks.copy()
    sel_tank_col = "✓ Select tank"
    if sel_tank_col not in t_view.columns:
        t_view.insert(0, sel_tank_col, False)

    t_grid = st.data_editor(
        t_view[
            [
                sel_tank_col,
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
            "tank_code": st.column_config.TextColumn("Tank", disabled=True),
            "fish_code": st.column_config.TextColumn(
                "Line instance", disabled=True
            ),
            "status": st.column_config.SelectboxColumn(
                "Status", options=TANK_STATUS_OPTIONS
            ),
            "created_at": st.column_config.DatetimeColumn(
                "Created at", disabled=True
            ),
        },
        key="tank_picker_v11",
    )

    t_edited = t_grid.copy()
    selected_tanks = t_edited[
        t_edited.get(sel_tank_col, pd.Series(False, index=t_edited.index))
        .fillna(False)
        .astype(bool)
    ].copy()

    c_left, c_right = st.columns(2)

    with c_left:
        if st.button("💾 Save tank status changes", use_container_width=True):
            try:
                merged = df_tanks.merge(
                    t_edited[["tank_id", "status"]],
                    on="tank_id",
                    suffixes=("_orig", "_new"),
                )
                changes = merged[merged["status_orig"] != merged["status_new"]]
                if changes.empty:
                    st.info("No status changes to save.")
                else:
                    update_sql = text(
                        """
                        UPDATE public.tanks
                        SET status = :status
                        WHERE id = :id::uuid
                        """
                    )
                    with eng().begin() as cx:
                        for _, r in changes.iterrows():
                            cx.execute(
                                update_sql,
                                {"id": r["tank_id"], "status": r["status_new"]},
                            )
                    st.success(f"Updated status for {len(changes)} tank(s).")
            except Exception as e:
                st.error(f"Failed to update tank status: {type(e).__name__}: {e}")

    with c_right:
        st.markdown("**Create new tank(s) from selected tanks**")
        new_status = st.selectbox(
            "New tank status",
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

        def _resolve_fish_instance_id_from_line_instance(
            code: str,
        ) -> Optional[str]:
            code = (code or "").strip()
            if not code:
                return None
            with eng().begin() as cx:
                row = cx.execute(
                    text(
                        """
                        SELECT id::text
                        FROM public.fish_instances_v10
                        WHERE line_instance_code = :lc
                        LIMIT 1
                        """
                    ),
                    {"lc": code},
                ).fetchone()
            return row[0] if row and row[0] else None

        def _create_tank_for_line_instance(
            line_instance_code: str, status: str, created_at: date
        ) -> str:
            fi_id = _resolve_fish_instance_id_from_line_instance(line_instance_code)
            if not fi_id:
                raise RuntimeError(
                    f"Could not resolve line_instance_code {line_instance_code} to a fish instance."
                )
            from uuid import uuid4

            tank_code = f"TK-{created_at.strftime('%Y%m%d')}-{uuid4().hex[:4]}"
            with eng().begin() as cx:
                cx.execute(
                    text(
                        """
                        INSERT INTO public.tanks (
                          id,
                          tank_code,
                          fish_instance_id,
                          status,
                          created_at
                        )
                        VALUES (
                          gen_random_uuid(),
                          :tank_code,
                          CAST(:fi_id AS uuid),
                          :status,
                          :created_at
                        )
                        """
                    ),
                    {
                        "tank_code": tank_code,
                        "fi_id": fi_id,
                        "status": status,
                        "created_at": created_at,
                    },
                )
            return tank_code

        if st.button(
            "➕ Create tank(s)",
            use_container_width=True,
            key="create_tanks_btn_v11",
        ):
            if selected_tanks.empty:
                st.warning("Select at least one tank row to create new tanks.")
            else:
                created_codes: List[str] = []
                try:
                    for _, r in selected_tanks.iterrows():
                        line_inst = (r.get("fish_code") or "").strip()
                        if not line_inst:
                            continue
                        for _ in range(new_count):
                            code = _create_tank_for_line_instance(
                                line_inst, new_status, tank_date
                            )
                            created_codes.append(code)
                except Exception as e:
                    st.error(f"Failed to create tanks: {type(e).__name__}: {e}")
                else:
                    if created_codes:
                        st.success(
                            f"Created {len(created_codes)} tank(s): "
                            + ", ".join(created_codes)
                        )
                    else:
                        st.info(
                            "No tanks were created (no valid line instance code on selected rows)."
                        )