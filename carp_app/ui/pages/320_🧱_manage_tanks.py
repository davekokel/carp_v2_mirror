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
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock() -> None:
        ...
from carp_app.ui.lib.page_engine import engine as _engine  # core hook


# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🧱 Manage tanks",
    page_icon="🧱",
    layout="wide",
)
st.title("🧱 Manage tanks")


def eng() -> Engine:
    return _engine()


def _norm(s: str | None) -> Optional[str]:
    s = (s or "").strip()
    return s or None


def _exists_view(qualified: str) -> bool:
    s, n = qualified.split(".", 1)
    with eng().begin() as cx:
        r = pd.read_sql(
            text(
                """
          SELECT 1 FROM information_schema.views
          WHERE table_schema = :s AND table_name = :n
          UNION ALL
          SELECT 1 FROM pg_catalog.pg_matviews
          WHERE schemaname = :s AND matviewname = :n
          LIMIT 1
        """
            ),
            cx,
            params={"s": s, "n": n},
        )
    return not r.empty


V_TANKS_OVERVIEW = "public.v_tanks_overview"

if not _exists_view(V_TANKS_OVERVIEW):
    st.error(
        f"Required view {V_TANKS_OVERVIEW} not found. "
        "Create v_tanks_overview (tank_id, tank_code, fish_code, status, created_at) "
        "before using this page."
    )
    st.stop()


# ════════════════════════════════════════════════════════
# SECTION 1 — FILTER & VIEW TANKS
# ════════════════════════════════════════════════════════
st.subheader("Step 1 — Filter tanks", anchor=False)

with st.form("tank_filters_manage", clear_on_submit=False):
    c1, c2, c3 = st.columns([3, 1.2, 0.8])
    with c1:
        q_raw = st.text_input(
            "Search (tank_code / fish_code / status)",
            "",
        )
    with c2:
        status_choice = st.selectbox(
            "Status filter",
            ["all", "active", "retired"],
            index=0,
        )
    with c3:
        lim = int(
            st.number_input(
                "Limit",
                min_value=50,
                max_value=5000,
                value=500,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply", key="tank_filters_manage_apply")

q = _norm(q_raw)
status_filter = status_choice if status_choice != "all" else None

where: List[str] = ["1=1"]
params: Dict[str, Any] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  tank_code ILIKE :ql"
        " OR COALESCE(fish_code,'') ILIKE :ql"
        " OR COALESCE(status,'') ILIKE :ql"
        ")"
    )

if status_filter:
    params["status"] = status_filter
    where.append("status = :status")

where_sql = " AND ".join(where)

sql_tanks = text(
    f"""
    SELECT
      tank_id,
      tank_code,
      fish_code,
      status,
      created_at
    FROM {V_TANKS_OVERVIEW}
    WHERE {where_sql}
    ORDER BY created_at DESC, tank_code
    LIMIT :lim;
"""
)

with eng().begin() as cx:
    df_tanks = pd.read_sql(sql_tanks, cx, params=params)

df_tanks = df_tanks.fillna("")
st.caption(f"{len(df_tanks)} tank(s)")

if df_tanks.empty:
    st.info("No tanks match the current filters.")
    st.stop()

# ════════════════════════════════════════════════════════
# SECTION 2 — EDIT TANK STATUS
# ════════════════════════════════════════════════════════
st.subheader("Step 2 — Edit tank status", anchor=False)

view = df_tanks.copy()
view.insert(0, "✓ Select", False)

grid = st.data_editor(
    view,
    key="tanks_manage_grid",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=[
        "✓ Select",
        "tank_id",
        "tank_code",
        "fish_code",
        "status",
        "created_at",
    ],
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "tank_id": st.column_config.TextColumn("Tank ID", disabled=True),
        "tank_code": st.column_config.TextColumn("Tank code", disabled=True),
        "fish_code": st.column_config.TextColumn("Fish code", disabled=True),
        "status": st.column_config.TextColumn(
            "Status", disabled=False
        ),
        "created_at": st.column_config.DatetimeColumn(
            "Created at", disabled=True
        ),
    },
)

edited = grid.copy()

st.download_button(
    "⬇︎ Download tanks (CSV)",
    data=edited.to_csv(index=False).encode("utf-8"),
    file_name="tanks_manage_overview.csv",
    type="secondary",
    mime="text/csv",
)

if st.button("💾 Save status changes", type="primary", use_container_width=True):
    try:
        # Compare original vs edited to find changed statuses
        merged = df_tanks.merge(
            edited[["tank_id", "status"]],
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
                WHERE id = :id::uuid;
                """
            )
            with eng().begin() as cx:
                for _, row in changes.iterrows():
                    cx.execute(
                        update_sql,
                        {"id": row["tank_id"], "status": row["status_new"]},
                    )
            st.success(f"Updated status for {len(changes)} tank(s).")
    except Exception as e:
        st.error(f"Failed to update tank status: {type(e).__name__}: {e}")

# ════════════════════════════════════════════════════════
# SECTION 3 — CREATE NEW TANKS
# ════════════════════════════════════════════════════════
st.divider()
st.subheader("Step 3 — Create new tank", anchor=False)

st.markdown(
    "Create a new tank for an existing fish instance by **fish_code**. "
    "Tank codes will be auto-generated."
)

c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    new_fish_code = st.text_input(
        "Fish code (FSH-…)",
        value="",
        help="Must match an existing fish_code in v11_fish_instance_star / fish_instances_v10.",
    )
with c2:
    new_status = st.selectbox(
        "Initial status",
        options=["active", "retired"],
        index=0,
    )
with c3:
    tank_date = st.date_input("Tank created date", value=date.today())

def _resolve_fish_instance_id(fish_code: str) -> Optional[str]:
    """
    Resolve fish_code → fish_instance_id via v11_fish_instance_star.
    Falls back to fish_instances_v10 if needed.
    """
    fc = (fish_code or "").strip()
    if not fc:
        return None

    with eng().begin() as cx:
        row = cx.execute(
            text(
                """
                SELECT fish_instance_id::text
                FROM public.v11_fish_instance_star
                WHERE fish_code = :fc
                LIMIT 1;
                """
            ),
            {"fc": fc},
        ).fetchone()
        if row and row[0]:
            return str(row[0])

        row2 = cx.execute(
            text(
                """
                SELECT id::text
                FROM public.fish_instances_v10
                WHERE fish_code = :fc
                LIMIT 1;
                """
            ),
            {"fc": fc},
        ).fetchone()
        if row2 and row2[0]:
            return str(row2[0])

    return None


def _create_tank(fish_code: str, status: str, created_at: date) -> str:
    """
    Insert a new row into public.tanks for the given fish_code.
    Returns the new tank_code.
    """
    fish_instance_id = _resolve_fish_instance_id(fish_code)
    if not fish_instance_id:
        raise RuntimeError(f"Could not resolve fish_code {fish_code} to a fish instance.")

    # tank_code pattern: TK-YYYYMMDD-XXXX (random suffix)
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
                  :fish_instance_id::uuid,
                  :status,
                  :created_at
                );
                """
            ),
            {
                "tank_code": tank_code,
                "fish_instance_id": fish_instance_id,
                "status": status,
                "created_at": created_at,
            },
        )

    return tank_code

if st.button("➕ Create tank", type="primary", use_container_width=True):
    try:
        if not new_fish_code.strip():
            st.warning("Fish code is required.")
        else:
            code = _create_tank(new_fish_code.strip(), new_status, tank_date)
            st.success(f"Created tank {code} for fish {new_fish_code.strip()}.")
    except Exception as e:
        st.error(f"Failed to create tank: {type(e).__name__}: {e}")