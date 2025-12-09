from __future__ import annotations

import sys
import pathlib
import uuid
from datetime import datetime, timedelta
from typing import List

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
    def require_app_unlock() -> None:
        ...

from carp_app.ui.lib.app_ctx import get_engine


SESSION_SELECTED_IDS = "assign_fish_selected_ids"
SESSION_SUCCESS_MSG = "assign_fish_success"


def load_fish_instances_for_assignment(
    engine: Engine,
    start_created_at: datetime,
    end_created_at: datetime,
) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          fi.id::text AS fish_instance_id,
          fi.fish_code,
          fi.instance_stage,
          fi.birthday,
          fi.genetic_background,
          fi.origin_kind,
          fi.created_at,
          fl.line_code,
          fl.nickname AS line_nickname,
          fis.genotype_tg_style,
          fis.genotype_fluortag_style,
          fis.genotype_fluororganelle_style,
          fis.treatment_codes,
          fis.treatment_label_tg_style,
          fis.treatment_label_fluortag_style,
          fis.treatment_label_fluororganelle_style,
          CASE
            WHEN fis.treatment_codes IS NOT NULL AND fis.genotype_tg_style IS NOT NULL
              THEN fis.treatment_label_tg_style || ' > ' || fis.genotype_tg_style
            WHEN fis.treatment_codes IS NOT NULL
              THEN fis.treatment_label_tg_style
            ELSE fis.genotype_tg_style
          END AS treatment_or_genotype_tg_style,
          CASE
            WHEN fis.treatment_codes IS NOT NULL AND fis.genotype_fluortag_style IS NOT NULL
              THEN fis.treatment_label_fluortag_style || ' > ' || fis.genotype_fluortag_style
            WHEN fis.treatment_codes IS NOT NULL
              THEN fis.treatment_label_fluortag_style
            ELSE fis.genotype_fluortag_style
          END AS treatment_or_genotype_fluortag_style,
          CASE
            WHEN fis.treatment_codes IS NOT NULL AND fis.genotype_fluororganelle_style IS NOT NULL
              THEN fis.treatment_label_fluororganelle_style || ' > ' || fis.genotype_fluororganelle_style
            WHEN fis.treatment_codes IS NOT NULL
              THEN fis.treatment_label_fluororganelle_style
            ELSE fis.genotype_fluororganelle_style
          END AS treatment_or_genotype_fluororganelle_style,
          tank.tank_codes,
          COALESCE(tank.has_tank, false) AS has_tank
        FROM public.fish_instances_v10 fi
        JOIN public.fish_lines fl
          ON fl.id = fi.line_id
        LEFT JOIN public.v11_fish_instance_star_labels fis
          ON fis.fish_instance_id = fi.id
        LEFT JOIN LATERAL (
          SELECT
            string_agg(DISTINCT t.tank_code, ', ' ORDER BY t.tank_code) AS tank_codes,
            bool_or(true)                                               AS has_tank
          FROM public.tank_fish_instances tfi
          JOIN public.tanks t ON t.id = tfi.tank_id
          WHERE tfi.fish_instance_id = fi.id
        ) AS tank ON true
        WHERE fi.created_at >= :start_created_at
          AND fi.created_at < :end_created_at
        ORDER BY fi.created_at DESC, fi.fish_code
        """
    )
    with engine.connect() as cx:
        df = pd.read_sql(
            sql,
            cx,
            params={
                "start_created_at": start_created_at,
                "end_created_at": end_created_at,
            },
        )
    return df


def assign_fish_to_individual_tanks(
    engine: Engine,
    fish_instance_ids: List[str],
) -> List[str]:
    """
    For each fish_instance_id, create a new tank with code:

        FISH-<fish_slug>-TANKNNN

    where <fish_slug> is a stable 8-hex slug derived from fish_instance_id,
    and N is 001, 002, 003, ... for that fish_instance.
    """
    if not fish_instance_ids:
        return []

    created_tank_codes: List[str] = []

    with engine.begin() as cx:
        for fid in fish_instance_ids:
            # Stable 8-hex slug per fish_instance_id
            # (strip dashes, take first 8 characters)
            fish_slug = "".join(str(fid).split("-"))[:8]

            # Find existing tank numbers for this fish_instance
            existing_codes = cx.execute(
                text(
                    """
                    SELECT tank_code
                    FROM public.tanks
                    WHERE fish_instance_id = (:fid)::uuid
                    ORDER BY created_at ASC, tank_code ASC;
                    """
                ),
                {"fid": fid},
            ).scalars().all()

            max_n = 0
            for code in existing_codes:
                if not code:
                    continue
                parts = str(code).rsplit("-TANK", 1)
                if len(parts) != 2:
                    continue
                try:
                    n = int(parts[1])
                    if n > max_n:
                        max_n = n
                except ValueError:
                    continue

            next_n = max_n + 1  # 1 if none exist, else max+1

            tank_code = f"FISH-{fish_slug}-TANK{next_n:03d}"

            row = cx.execute(
                text(
                    """
                    INSERT INTO public.tanks (
                      id,
                      tank_code,
                      location,
                      status,
                      volume_l,
                      notes,
                      created_at,
                      fish_instance_id
                    )
                    VALUES (
                      gen_random_uuid(),
                      :tank_code,
                      NULL,
                      'active',
                      NULL,
                      NULL,
                      now(),
                      (:fish_instance_id)::uuid
                    )
                    RETURNING id::text AS tank_id;
                    """
                ),
                {"tank_code": tank_code, "fish_instance_id": fid},
            ).fetchone()
            tank_id = row._mapping["tank_id"]

            cx.execute(
                text(
                    """
                    INSERT INTO public.tank_fish_instances (
                      id,
                      tank_id,
                      fish_instance_id
                    )
                    VALUES (
                      gen_random_uuid(),
                      (:tank_id)::uuid,
                      (:fish_instance_id)::uuid
                    )
                    ON CONFLICT (tank_id, fish_instance_id) DO NOTHING;
                    """
                ),
                {"tank_id": tank_id, "fish_instance_id": fid},
            )

            created_tank_codes.append(tank_code)

    return created_tank_codes


def main() -> None:
    sb, session, user = require_auth()
    require_email_otp()
    require_app_unlock()

    st.set_page_config(
        page_title="CARP — 🐟 Assign fish to tanks",
        page_icon="🐟",
        layout="wide",
    )
    st.title("🐟 Assign fish to tanks")

    # Persistent success banner (until something else overwrites it)
    success_msg = st.session_state.get(SESSION_SUCCESS_MSG)
    if success_msg:
        st.success(success_msg)

    engine = get_engine()

    today = datetime.utcnow().date()
    default_start = today - timedelta(days=30)

    # ── Filters ────────────────────────────────────────────────────────────────
    st.subheader("Filters")

    date_range = st.date_input(
        "Created between (fish_instances_v10.created_at)",
        value=(default_start, today),
    )
    if isinstance(date_range, tuple):
        start_date, end_date = date_range
    else:
        start_date = date_range
        end_date = date_range

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    df = load_fish_instances_for_assignment(engine, start_dt, end_dt)

    if df.empty:
        st.info("No fish instances found for the selected date range.")
        return

    all_kinds = sorted([k for k in df["origin_kind"].dropna().unique()])
    kind_filter = st.multiselect(
        "origin_kind",
        options=all_kinds,
        default=all_kinds,
    )

    has_tank_filter = st.radio(
        "Has tank?",
        options=["Any", "Has tank", "No tank"],
        index=0,
        horizontal=True,
    )

    # ── Filtered data ─────────────────────────────────────────────────────────
    df_filtered = df.copy()
    if kind_filter:
        df_filtered = df_filtered[df_filtered["origin_kind"].isin(kind_filter)]

    if has_tank_filter == "Has tank":
        df_filtered = df_filtered[df_filtered["has_tank"]]
    elif has_tank_filter == "No tank":
        df_filtered = df_filtered[~df_filtered["has_tank"]]

    df_filtered = df_filtered.reset_index(drop=True)

    # Restore selection from session_state
    selected_ids_state: List[str] = st.session_state.get(SESSION_SELECTED_IDS, [])
    df_filtered["selected"] = df_filtered["fish_instance_id"].isin(selected_ids_state)

    display_cols = [
        "selected",
        "fish_code",
        "line_code",
        "line_nickname",
        "instance_stage",
        "birthday",
        "genetic_background",
        "origin_kind",
        "treatment_or_genotype_tg_style",
        "treatment_or_genotype_fluortag_style",
        "treatment_or_genotype_fluororganelle_style",
        "tank_codes",
        "created_at",
    ]

    # ── Table + selection controls ────────────────────────────────────────────
    st.subheader("Fish instances")

    sel_col1, sel_col2 = st.columns(2)
    with sel_col1:
        if st.button("Select all (filtered)"):
            st.session_state[SESSION_SELECTED_IDS] = df_filtered["fish_instance_id"].tolist()
            st.rerun()
    with sel_col2:
        if st.button("Clear all (filtered)"):
            st.session_state[SESSION_SELECTED_IDS] = []
            st.rerun()

    edited = st.data_editor(
        df_filtered[display_cols],
        hide_index=True,
        use_container_width=True,
        key="assign_fish_table",
    )

    # Update selection from editor
    df_filtered["selected"] = edited["selected"].values
    selected_ids = df_filtered.loc[df_filtered["selected"], "fish_instance_id"].tolist()
    st.session_state[SESSION_SELECTED_IDS] = selected_ids

    st.markdown("---")
    st.subheader("Assign selected fish to tanks")

    if not selected_ids:
        st.info("Select one or more fish instances above to enable tank assignment.")
        return

    with st.form("assign_tanks_form"):
        st.write(
            f"{len(selected_ids)} fish instance(s) selected. "
            "A new tank will be created for each selected fish."
        )
        submitted = st.form_submit_button("Create one new tank per selected fish")

    if not submitted:
        return

    created_codes = assign_fish_to_individual_tanks(engine, selected_ids)
    if not created_codes:
        st.error("No tanks were created.")
        return

    # Persist success message across rerun
    st.session_state[SESSION_SUCCESS_MSG] = (
        f"Created {len(created_codes)} tank(s) and assigned "
        f"{len(selected_ids)} fish instance(s) to them."
    )
    st.session_state[SESSION_SELECTED_IDS] = []
    st.rerun()


if __name__ == "__main__":
    main()