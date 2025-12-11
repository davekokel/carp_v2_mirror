# carp_app/ui/pages/200_⚙️_select_tank_pairs.py
# ⚙️ Select tank pairings (v11 fish instances & tanks)
from __future__ import annotations

import os
import sys
import uuid
import pathlib
from typing import List, Optional, Dict, Tuple, Any

import pandas as pd
import streamlit as st
from sqlalchemy import text

# ---- path/auth bootstrap ----------------------------------------------------
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

from carp_app.ui.lib.page_engine import engine as _engine

# ---- auth gates -------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — ⚙️ Select tank pairings",
    page_icon="⚙️",
    layout="wide",
)
st.title("⚙️ Select tank pairings (v11 fish instances & tanks)")


def eng():
    return _engine()


# ------------------ core queries (v11) ---------------------------------------


@st.cache_data(show_spinner=False)
def search_fish(q: Optional[str], limit: int) -> pd.DataFrame:
    """
    Search fish instances (FSH codes) using v11_fish_instance_star_labels
    + live tank counts from v_tanks_overview.
    Uses the 3 genotype style fields.
    """
    qnorm = (q or "").strip()
    params: Dict[str, object] = {
        "q": (qnorm if qnorm else None),
        "ql": (f"%{qnorm}%" if qnorm else None),
        "lim": int(limit),
    }

    sql = text(
        """
        WITH base AS (
          SELECT
            fis.fish_instance_id,
            fis.fish_code,
            fis.line_code,
            fis.line_nickname                      AS nickname,
            COALESCE(fis.genetic_background,'')    AS genetic_background,
            COALESCE(fis.instance_stage,'')        AS stage,
            COALESCE(fis.genotype_tg_style,'')          AS genotype_tg_style,
            COALESCE(fis.genotype_fluortag_style,'')    AS genotype_fluortag_style,
            COALESCE(fis.genotype_fluororganelle_style,'') AS genotype_fluororganelle_style,
            fis.birthday                           AS birthday,
            fis.birthday                           AS created_at
          FROM public.v11_fish_instance_star_labels fis
          WHERE (:q IS NULL)
             OR (
                  fis.fish_code                        ILIKE :ql
               OR COALESCE(fis.line_nickname,'')       ILIKE :ql
               OR COALESCE(fis.genetic_background,'')  ILIKE :ql
               OR COALESCE(fis.instance_stage,'')      ILIKE :ql
               OR COALESCE(fis.genotype_tg_style,'')   ILIKE :ql
               OR COALESCE(fis.genotype_fluortag_style,'') ILIKE :ql
               OR COALESCE(fis.genotype_fluororganelle_style,'') ILIKE :ql
             )
          ORDER BY fis.birthday DESC NULLS LAST, fis.fish_code
          LIMIT :lim
        ),
        live AS (
          SELECT
            ts.fish_code,
            COUNT(*)::int AS n_live,
            string_agg(DISTINCT ts.tank_code, ', ' ORDER BY ts.tank_code) AS live_tank_codes
          FROM public.v_tanks_overview ts
          WHERE lower(trim(ts.status)) = 'active'
          GROUP BY ts.fish_code
        )
        SELECT
          b.fish_code,
          b.line_code,
          b.nickname                  AS name,
          b.genetic_background        AS background,
          b.stage                     AS stage,
          b.genotype_tg_style,
          b.genotype_fluortag_style,
          b.genotype_fluororganelle_style,
          b.birthday                  AS birthday,
          COALESCE(l.n_live, 0)       AS live_tanks,
          COALESCE(l.live_tank_codes,'') AS live_tank_codes
        FROM base b
        LEFT JOIN live l
          ON l.fish_code = b.fish_code;
        """
    )

    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df.fillna("")


@st.cache_data(show_spinner=False)
def load_active_tanks_for_fish(codes: List[str]) -> pd.DataFrame:
    """
    Return active tanks for the given FSH fish_codes,
    with line nickname + 3 genotype display styles.
    """
    if not codes:
        return pd.DataFrame()

    sql = text(
        """
        SELECT
          ts.fish_code,
          fis.line_code,
          fis.line_nickname                      AS fish_name,
          COALESCE(fis.genotype_tg_style,'')          AS genotype_tg_style,
          COALESCE(fis.genotype_fluortag_style,'')    AS genotype_fluortag_style,
          COALESCE(fis.genotype_fluororganelle_style,'') AS genotype_fluororganelle_style,
          fis.birthday                           AS birthday,
          ts.tank_code,
          ts.tank_id::text                       AS tank_id,
          ts.status                              AS status,
          ts.created_at                          AS created_at
        FROM public.v_tanks_overview ts
        JOIN public.v11_fish_instance_star_labels fis
          ON fis.fish_code = ts.fish_code
        WHERE ts.fish_code = ANY(:codes)
          AND lower(trim(ts.status)) = 'active'
        ORDER BY ts.fish_code, ts.created_at DESC NULLS LAST;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df.fillna("")


def _tank_pair_parent_cols() -> Tuple[str, str]:
    with eng().begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'tank_pairs'
                ORDER BY ordinal_position;
                """
            ),
            cx,
        )
    cols = df["column_name"].tolist()
    for a, b in (("mother_tank_id", "father_tank_id"), ("tank_id_mother", "tank_id_father")):
        if a in cols and b in cols:
            return a, b
    raise RuntimeError(
        "public.tank_pairs must have mother/father UUID columns. "
        f"Expected (mother_tank_id,father_tank_id) or (tank_id_mother,tank_id_father). Found: {cols}"
    )


def upsert_tank_pair(mother_tank_id: str, father_tank_id: str, created_by: str, note: str):
    mom_col, dad_col = _tank_pair_parent_cols()

    with eng().begin() as cx:
        cols_df = pd.read_sql(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='tank_pairs';
                """
            ),
            cx,
        )
        cols = set(cols_df["column_name"].tolist())

        # 1) Try to find an existing tank_pair for this mother/father
        row = pd.read_sql(
            text(
                f"""
                SELECT id::text, tank_pair_code
                FROM public.tank_pairs
                WHERE {mom_col} = :m AND {dad_col} = :d
                LIMIT 1;
                """
            ),
            cx,
            params={"m": mother_tank_id, "d": father_tank_id},
        )

        if not row.empty:
            sets = []
            params = {"id": row.iloc[0]["id"], "note": note, "by": created_by}
            if "updated_at" in cols:
                sets.append("updated_at = now()")
            if "notes" in cols:
                sets.append("notes = COALESCE(NULLIF(:note,''), notes)")
            if "updated_by" in cols:
                sets.append("updated_by = COALESCE(NULLIF(:by,''), updated_by)")
            if sets:
                cx.execute(
                    text(
                        f"UPDATE public.tank_pairs SET {', '.join(sets)} WHERE id = :id::uuid"
                    ),
                    params,
                )
            return False, str(row.iloc[0]["tank_pair_code"])

        # 2) Insert a new tank_pair
        new_id = str(uuid.uuid4())
        new_code = f"TP-{new_id[:8]}"

        params = {
            "id": new_id,
            "m": mother_tank_id,
            "d": father_tank_id,
            "by": created_by,
            "note": note,
            "tp_code": new_code,
        }

        sql = text(
            f"""
            INSERT INTO public.tank_pairs (
                id,
                {mom_col},
                {dad_col},
                created_at,
                tank_pair_code,
                notes
            )
            VALUES (
                :id,
                :m,
                :d,
                now(),
                :tp_code,
                NULLIF(:note,'')
            )
            RETURNING tank_pair_code;
            """
        )
        tp_code_db = cx.execute(sql, params).scalar()
        return True, str(tp_code_db)


# ------------------ UI -------------------------------------------------------

# Session state for persistent parent selection across searches
if "selected_parent_fish_codes" not in st.session_state:
    st.session_state["selected_parent_fish_codes"] = []

with st.form("filters"):
    c1, c2 = st.columns([3, 1])
    with c1:
        q = st.text_input(
            "Filter by code / nickname / background / genotype",
            "",
        )
    with c2:
        limit = int(st.number_input("Rows", 1, 2000, 500, 50))
    st.form_submit_button("Apply")

df = search_fish(q, limit)
if df.empty:
    st.info("No fish match filters.")
    st.stop()

st.subheader("Step 1 — Select parents (from fish instances)")

view = df[
    [
        "fish_code",
        "line_code",
        "name",
        "background",
        "stage",
        "genotype_tg_style",
        "genotype_fluortag_style",
        "genotype_fluororganelle_style",
        "birthday",
        "live_tanks",
        "live_tank_codes",
    ]
].copy()

# --- NEW LOGIC: keep selections that are not visible in this search ---

prev_selection: List[str] = st.session_state.get("selected_parent_fish_codes", [])
visible_codes = view["fish_code"].astype(str).tolist()

# Pre-populate checkboxes for codes that were previously selected *and* are visible
view.insert(0, "✓ Parent", view["fish_code"].isin(prev_selection))

pick = st.data_editor(
    view,
    key="parent_table_v11",
    width="stretch",
    hide_index=True,
    column_config={
        "✓ Parent": st.column_config.CheckboxColumn("✓", default=False),
        "fish_code": st.column_config.TextColumn("FSH code", disabled=True),
        "line_code": st.column_config.TextColumn("LINE code", disabled=True),
        "name": st.column_config.TextColumn("Name", disabled=True, width="large"),
        "background": st.column_config.TextColumn("Background", disabled=True),
        "stage": st.column_config.TextColumn("Stage", disabled=True),
        "genotype_tg_style": st.column_config.TextColumn(
            "Genotype (tg)", disabled=True, width="large"
        ),
        "genotype_fluortag_style": st.column_config.TextColumn(
            "Genotype (fluor-tag)", disabled=True, width="large"
        ),
        "genotype_fluororganelle_style": st.column_config.TextColumn(
            "Genotype (fluor-organelle)", disabled=True, width="large"
        ),
        "birthday": st.column_config.DateColumn("Birthday", disabled=True),
        "live_tanks": st.column_config.NumberColumn("Live tanks", disabled=True),
        "live_tank_codes": st.column_config.TextColumn(
            "Live tank codes", disabled=True, width="large"
        ),
    },
)

# What is selected *in this view* right now?
if not pick.empty:
    visible_selected = (
        pick.loc[pick["✓ Parent"], "fish_code"].dropna().astype(str).tolist()
    )
    visible_selected = list(dict.fromkeys(visible_selected))  # preserve order, dedupe
else:
    visible_selected = []

# Split previous selection into "hidden" vs "visible in this view"
hidden_prev = [c for c in prev_selection if c not in visible_codes]

# Combine:
#   - keep hidden previous selections
#   - override selections for visible rows with the current checkbox state
combined: List[str] = []
for code in hidden_prev + visible_selected:
    if code not in combined:
        combined.append(code)

# Enforce max of two parents
combined = combined[:2]

st.session_state["selected_parent_fish_codes"] = combined
parents = combined

if len(parents) < 2:
    if parents:
        st.info(f"Currently selected parent(s): {', '.join(parents)}. Select one more to continue.")
    else:
        st.info("Select two parents above to continue.")
    st.stop()

st.success(f"Selected parents: {parents[0]} × {parents[1]}")

st.subheader("Step 2 — Choose Mother and Father tanks (active only)")
live = load_active_tanks_for_fish(parents)
if live.empty:
    st.warning("No active tanks for selected parents.")
    st.stop()

st.subheader("Mother")
m_candidates = live.copy()
m_candidates.insert(0, "✓ Mother", False)
m_sel = st.data_editor(
    m_candidates[
        [
            "✓ Mother",
            "fish_code",
            "line_code",
            "fish_name",
            "genotype_tg_style",
            "genotype_fluortag_style",
            "genotype_fluororganelle_style",
            "birthday",
            "tank_code",
            "tank_id",
            "status",
            "created_at",
        ]
    ],
    key="mother_table_v11",
    width="stretch",
    hide_index=True,
    column_config={
        "✓ Mother": st.column_config.CheckboxColumn("✓", default=False),
        "fish_code": st.column_config.TextColumn("FSH code", disabled=True),
        "line_code": st.column_config.TextColumn("LINE code", disabled=True),
        "fish_name": st.column_config.TextColumn("Name", disabled=True, width="large"),
        "genotype_tg_style": st.column_config.TextColumn(
            "Genotype (tg)", disabled=True, width="large"
        ),
        "genotype_fluortag_style": st.column_config.TextColumn(
            "Genotype (fluor-tag)", disabled=True, width="large"
        ),
        "genotype_fluororganelle_style": st.column_config.TextColumn(
            "Genotype (fluor-organelle)", disabled=True, width="large"
        ),
        "birthday": st.column_config.DateColumn("Birthday", disabled=True),
        "tank_code": st.column_config.TextColumn("Tank code", disabled=True),
        "tank_id": st.column_config.TextColumn("Tank id", disabled=True),
        "status": st.column_config.TextColumn("Status", disabled=True),
        "created_at": st.column_config.DatetimeColumn("Created at", disabled=True),
    },
)
m_pick = m_sel.loc[m_sel["✓ Mother"]] if not m_sel.empty else pd.DataFrame()
if m_pick.empty:
    st.info("Pick a Mother tank to continue.")
    st.stop()

mother_row = m_pick.iloc[0]
mother_fish = str(mother_row["fish_code"])
mother_tank_id = str(mother_row["tank_id"])

other_fish = next(f for f in parents if f != mother_fish)
f_candidates = live[live["fish_code"] == other_fish].copy()
if f_candidates.empty:
    st.warning(f"No active tanks for father fish {other_fish}.")
    st.stop()

st.subheader("Father")
f_candidates.insert(0, "✓ Father", False)
f_sel = st.data_editor(
    f_candidates[
        [
            "✓ Father",
            "fish_code",
            "line_code",
            "fish_name",
            "genotype_tg_style",
            "genotype_fluortag_style",
            "genotype_fluororganelle_style",
            "birthday",
            "tank_code",
            "tank_id",
            "status",
            "created_at",
        ]
    ],
    key="father_table_v11",
    width="stretch",
    hide_index=True,
    column_config={
        "✓ Father": st.column_config.CheckboxColumn("✓", default=False),
        "fish_code": st.column_config.TextColumn("FSH code", disabled=True),
        "line_code": st.column_config.TextColumn("LINE code", disabled=True),
        "fish_name": st.column_config.TextColumn("Name", disabled=True, width="large"),
        "genotype_tg_style": st.column_config.TextColumn(
            "Genotype (tg)", disabled=True, width="large"
        ),
        "genotype_fluortag_style": st.column_config.TextColumn(
            "Genotype (fluor-tag)", disabled=True, width="large"
        ),
        "genotype_fluororganelle_style": st.column_config.TextColumn(
            "Genotype (fluor-organelle)", disabled=True, width="large"
        ),
        "birthday": st.column_config.DateColumn("Birthday", disabled=True),
        "tank_code": st.column_config.TextColumn("Tank code", disabled=True),
        "tank_id": st.column_config.TextColumn("Tank id", disabled=True),
        "status": st.column_config.TextColumn("Status", disabled=True),
        "created_at": st.column_config.DatetimeColumn("Created at", disabled=True),
    },
)
f_pick = f_sel.loc[f_sel["✓ Father"]] if not f_sel.empty else pd.DataFrame()
if f_pick.empty:
    st.info("Pick a Father tank to continue.")
    st.stop()

father_tank_id = str(f_pick.iloc[0]["tank_id"])
if mother_tank_id == father_tank_id:
    st.error("Mother and Father cannot be the same tank.")
    st.stop()

st.subheader("Step 3 — Save tank pairing")
creator = os.getenv("USER") or os.getenv("USERNAME") or "unknown"
note = st.text_input("Note (optional)", "")

if st.button("💾 Save tank pairing", type="primary", use_container_width=True):
    created, code = upsert_tank_pair(mother_tank_id, father_tank_id, creator, note)
    st.success(f"{'Created' if created else 'Updated'} tank_pair {code}")
    st.info("You can now go to ⚙️ Schedule new crosses and pick this tank pair.")