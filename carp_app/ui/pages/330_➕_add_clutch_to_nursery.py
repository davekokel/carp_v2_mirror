# carp_app/ui/pages/330_➕_add_clutch_to_nursery.py
# 🧱 Add clutch to nursery — convert clutch → fish_instances_v10

from __future__ import annotations

import sys
import pathlib
import uuid
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List

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
V_FISH_LINE_STAR = "public.v11_fish_line_star"

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🧱 Add clutch to nursery",
    page_icon="🧱",
    layout="wide",
)
st.title("🧱 Add clutch to nursery — convert clutch → fish instances")


def eng() -> Engine:
    return get_engine()


def _norm(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None


def _who() -> str:
    return (
        getattr(user, "email", None)
        or st.session_state.get("user_email")
        or "system"
    )


# ════════════════════════════════════════════════════════
# LOADERS
# ════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def load_clutches_for_nursery(
    q: Optional[str],
    from_date: Optional[date],
    to_date: Optional[date],
    limit: int,
) -> pd.DataFrame:
    """
    Flat clutch overview for nursery based on v11_clutch_label_star,
    excluding legacy_imaging clutches.
    """
    sql = text(
        """
        SELECT
          v.clutch_kind,
          v.clutch_id::text            AS clutch_id,
          v.treated_clutch_id::text    AS treated_clutch_id,
          v.selection_event_id::text   AS selection_event_id,
          v.clutch_code,
          v.clutch_date,
          v.treated_clutch_code,
          v.treatment_code,
          v.treat_text,
          v.selection_label,
          v.genotype_v11_id::text      AS genotype_v11_id,
          v.genotype_code,
          v.genotype_basecodes,
          v.genotype_pretty,
          v.genotype_tg_style,
          v.genotype_fluortag_style,
          v.genotype_fluororganelle_style,
          v.label_tg_style,
          v.label_fluortag_style,
          v.label_fluororganelle_style
        FROM public.v11_clutch_label_star v
        JOIN public.clutches c
          ON c.id = v.clutch_id
        WHERE COALESCE(c.source_system, '') <> 'legacy_imaging'
          AND (
               :q IS NULL
            OR v.clutch_code                 ILIKE :ql
            OR COALESCE(v.treated_clutch_code,'') ILIKE :ql
            OR COALESCE(v.treatment_code,'')      ILIKE :ql
            OR COALESCE(v.treat_text,'')          ILIKE :ql
            OR COALESCE(v.selection_label,'')     ILIKE :ql
            OR COALESCE(v.label_tg_style,'')      ILIKE :ql
          )
          AND (:from_d IS NULL OR v.clutch_date >= :from_d)
          AND (:to_d   IS NULL OR v.clutch_date <= :to_d)
        ORDER BY v.clutch_date DESC NULLS LAST,
                 v.clutch_code,
                 v.clutch_kind,
                 v.treated_clutch_code NULLS FIRST,
                 v.selection_label NULLS FIRST
        LIMIT :lim;
        """
    )

    params = {
        "q": q,
        "ql": f"%{q}%" if q else None,
        "from_d": from_date,
        "to_d": to_date,
        "lim": int(limit),
    }

    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    return df.fillna("")


@st.cache_data(show_spinner=False)
def load_all_lines_for_nursery() -> pd.DataFrame:
    """
    All fish lines (for fallback or manual selection).
    """
    sql = text(
        """
        SELECT
          id::text            AS line_id,
          line_code,
          nickname,
          genetic_background,
          construct_code
        FROM public.fish_lines
        ORDER BY line_code;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx)
    return df.fillna("")


@st.cache_data(show_spinner=False)
def load_candidate_lines_for_clutch(clutch_id: str) -> pd.DataFrame:
    """
    Candidate lines for a clutch, based on matching genotype_pretty
    between clutches.genotype_v11_id and v11_fish_line_star.genotype_pretty.
    """
    sql = text(
        f"""
        SELECT
          fls.line_id::text       AS line_id,
          fls.line_code,
          fls.line_nickname       AS nickname,
          fls.genetic_background,
          fls.genotype_pretty
        FROM {V_FISH_LINE_STAR} fls
        JOIN public.clutches c
          ON c.id = :cid
        WHERE fls.genotype_pretty = (
            SELECT g.genotype_pretty
            FROM public.genotypes_v11 g
            WHERE g.id = c.genotype_v11_id
        )
        ORDER BY fls.line_code;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"cid": clutch_id})
    return df.fillna("")


# ════════════════════════════════════════════════════════
# STEP 1 — FLAT CLUTCH TABLE (v11_clutch_label_star)
# ════════════════════════════════════════════════════════

# Time-window selector: default to last 21 days
window_mode = st.radio(
    "Clutch time window",
    options=["Last 21 days", "All"],
    index=0,
    horizontal=True,
    key="nursery_clutch_window",
)

with st.form("clutch_filters_for_nursery", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 1])
    with c1:
        q_raw = st.text_input(
            "Search clutches (clutch_code / genotype / treatment / selection)",
            "",
        )
    with c2:
        from_raw = st.text_input("From clutch_date (YYYY-MM-DD)", "")
    with c3:
        to_raw = st.text_input("To clutch_date (YYYY-MM-DD)", "")
    with c4:
        lim = int(
            st.number_input(
                "Limit",
                min_value=10,
                max_value=2000,
                value=200,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply")

q = _norm(q_raw)
from_d: Optional[date] = None
to_d: Optional[date] = None

# Default window logic:
# • If user supplies explicit from/to, we honor those.
# • Otherwise, "Last 21 days" mode sets from_d = today-21; "All" leaves from_d None.
today = date.today()

if from_raw:
    try:
        from_d = datetime.strptime(from_raw, "%Y-%m-%d").date()
    except ValueError:
        st.warning("From date must be YYYY-MM-DD if provided.")
elif window_mode == "Last 21 days":
    from_d = today - timedelta(days=21)

if to_raw:
    try:
        to_d = datetime.strptime(to_raw, "%Y-%m-%d").date()
    except ValueError:
        st.warning("To date must be YYYY-MM-DD if provided.")

clutches = load_clutches_for_nursery(q, from_d, to_d, lim)

if clutches.empty:
    st.info("No clutches match the current filters (after time-window + non-legacy filter).")
    st.stop()

st.subheader("Step 1 — Select a clutch (flat view)", anchor=False)

view = clutches.copy()
view.insert(0, "✓ Select", False)

flat_cols = [
    "✓ Select",
    "clutch_kind",
    "clutch_code",
    "clutch_date",
    "treated_clutch_code",
    "treatment_code",
    "treat_text",
    "selection_label",
    "genotype_tg_style",
    "label_tg_style",
    "label_fluortag_style",
    "label_fluororganelle_style",
]
flat_cols = [c for c in flat_cols if c in view.columns]

grid = st.data_editor(
    view[flat_cols],
    key="clutch_nursery_flat_picker",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_kind": st.column_config.TextColumn("Kind", disabled=True),
        "clutch_code": st.column_config.TextColumn("Clutch", disabled=True),
        "clutch_date": st.column_config.DateColumn("Clutch date", disabled=True),
        "treated_clutch_code": st.column_config.TextColumn(
            "Treated clutch", disabled=True
        ),
        "treatment_code": st.column_config.TextColumn(
            "Treatment code", disabled=True
        ),
        "treat_text": st.column_config.TextColumn(
            "Treatment text", disabled=True, width="large"
        ),
        "selection_label": st.column_config.TextColumn(
            "Selection label", disabled=True, width="large"
        ),
        "genotype_tg_style": st.column_config.TextColumn(
            "Genotype (tg)", disabled=True, width="large"
        ),
        "label_tg_style": st.column_config.TextColumn(
            "Label (tg)", disabled=True, width="large"
        ),
        "label_fluortag_style": st.column_config.TextColumn(
            "Label (fluor-tag)", disabled=True, width="large"
        ),
        "label_fluororganelle_style": st.column_config.TextColumn(
            "Label (fluor-organelle)", disabled=True, width="large"
        ),
    },
)

sel_mask = (
    grid.get("✓ Select", pd.Series(False, index=grid.index))
    .fillna(False)
    .astype(bool)
)
selected = clutches[sel_mask].reset_index(drop=True)

if selected.empty:
    st.info("Select one clutch row above to convert to nursery fish.")
    st.stop()

row = selected.iloc[0]
clutch_id = row["clutch_id"]
clutch_code = row["clutch_code"]
clutch_date = row["clutch_date"]
genotype_v11_id = row["genotype_v11_id"]
genotype_code = row.get("genotype_code") or ""
genotype_pretty = row.get("genotype_pretty") or ""
genotype_basecodes = row.get("genotype_basecodes") or ""
kind = row.get("clutch_kind")

st.success(
    f"Selected {kind} row for clutch {clutch_code} "
    f"(date={clutch_date}, genotype={genotype_code or genotype_pretty or genotype_basecodes})"
)

# ════════════════════════════════════════════════════════
# STEP 2 — DB-DRIVEN LINE CANDIDATES + MANUAL FALLBACK
# ════════════════════════════════════════════════════════

st.markdown("---")
st.subheader("Step 2 — Configure nursery fish instances", anchor=False)

candidate_lines_df = load_candidate_lines_for_clutch(clutch_id)
all_lines_df = load_all_lines_for_nursery()

if all_lines_df.empty:
    st.warning(
        "No fish lines found. You may need to create lines before adding nursery fish."
    )
    st.stop()

needs_first_member_confirm = False

if not candidate_lines_df.empty:
    lines_df = candidate_lines_df
    n_candidates = len(lines_df)

    if n_candidates == 1:
        line_row = lines_df.iloc[0]
        chosen_line_id = line_row["line_id"]
        chosen_bg = line_row["genetic_background"]
        line_label_str = (
            f"{line_row['line_code']} — {line_row['nickname']} [{chosen_bg}]"
        )
        st.caption(
            "Using 1 candidate line whose genotype matches the clutch genotype."
        )
        st.markdown(f"**Line for nursery instances:** {line_label_str}")
        line_options: List[str] = [line_label_str]
        line_idx_to_line_id: Dict[int, str] = {0: chosen_line_id}
        default_bg = chosen_bg
        fixed_line_idx = 0
    else:
        st.caption(
            f"Using {n_candidates} candidate line(s) whose genotype matches the clutch genotype. "
            "Please choose which line to use."
        )
        lines_df = candidate_lines_df
        line_options = [
            f"{r['line_code']} — {r['nickname']} [{r['genetic_background']}]"
            for _, r in lines_df.iterrows()
        ]
        line_idx_to_line_id = {
            idx: r["line_id"] for idx, r in enumerate(lines_df.to_dict("records"))
        }
        default_bg = lines_df.iloc[0]["genetic_background"]
        fixed_line_idx = None
else:
    # No genotype-matching lines; manual fallback using all lines + confirmation.
    st.warning(
        "No lines share this clutch genotype yet. "
        "You can still proceed by choosing a line manually; "
        "these nursery fish will act as the first instances for that genotype/line mapping."
    )
    lines_df = all_lines_df
    line_options = [
        f"{r['line_code']} — {r['nickname']} [{r['genetic_background']}]"
        for _, r in lines_df.iterrows()
    ]
    line_idx_to_line_id = {
        idx: r["line_id"] for idx, r in enumerate(lines_df.to_dict("records"))
    }
    default_bg = lines_df.iloc[0]["genetic_background"]
    fixed_line_idx = None
    needs_first_member_confirm = True

with st.form("nursery_instance_form", clear_on_submit=False):
    c1, c2 = st.columns([2, 1])
    with c1:
        if fixed_line_idx is not None:
            st.markdown(
                f"**Line to assign nursery instances into:** {line_options[fixed_line_idx]}"
            )
            line_idx = fixed_line_idx
        else:
            line_idx = st.selectbox(
                "Line to assign nursery instances into",
                options=list(range(len(line_options))),
                format_func=lambda i: line_options[i],
                index=0,
            )

        birthday = st.date_input(
            "Birthday (defaults to clutch_date)",
            value=clutch_date or date.today(),
        )
        instance_stage = st.text_input(
            "Instance stage (e.g. 'nursery')",
            value="nursery",
        )
    with c2:
        n_instances = int(
            st.number_input(
                "Number of nursery fish to create",
                min_value=1,
                max_value=200,
                value=1,
                step=1,
            )
        )
        genetic_background = st.text_input(
            "Genetic background",
            value=default_bg,
        )

    confirm_first_member = False
    if needs_first_member_confirm:
        confirm_first_member = st.checkbox(
            "I understand this will create the first member(s) of a new genotype/line mapping.",
            value=False,
        )

    notes = st.text_area(
        "Notes for these nursery instances (optional)",
        "",
        height=80,
    )

    submit = st.form_submit_button(
        "💾 Create nursery fish instances", use_container_width=True
    )

# ════════════════════════════════════════════════════════
# STEP 3 — INSERT NURSERY FISH INSTANCES
# ════════════════════════════════════════════════════════

if submit:
    if n_instances <= 0:
        st.error("Number of nursery fish must be at least 1.")
    elif needs_first_member_confirm and not confirm_first_member:
        st.error(
            "Please confirm that you want to create the first member(s) of a new genotype/line mapping."
        )
    else:
        line_id = line_idx_to_line_id[line_idx]
        created_codes: List[str] = []

        try:
            with eng().begin() as cx:
                for _ in range(n_instances):
                    fish_code = f"FSH-{uuid.uuid4().hex[:8]}"
                    line_instance_code = fish_code

                    cx.execute(
                        text(
                            """
                            INSERT INTO public.fish_instances_v10 (
                                id,
                                line_instance_code,
                                line_id,
                                birthday,
                                notes,
                                created_at,
                                fish_code,
                                genotype_v11_id,
                                instance_stage,
                                genetic_background
                                )
                                VALUES (
                                gen_random_uuid(),
                                :line_instance_code,
                                CAST(:line_id AS uuid),
                                :birthday,
                                :notes,
                                now(),
                                :fish_code,
                                CAST(:genotype_v11_id AS uuid),
                                :instance_stage,
                                :genetic_background
                                );
                            """
                        ),
                        {
                            "line_instance_code": line_instance_code,
                            "line_id": line_id,
                            "birthday": birthday,
                            "notes": notes.strip() or None,
                            "fish_code": fish_code,
                            "genotype_v11_id": genotype_v11_id,
                            "instance_stage": instance_stage.strip() or None,
                            "genetic_background": genetic_background.strip() or None,
                        },
                    )
                    created_codes.append(fish_code)

            st.success(
                f"Created {len(created_codes)} nursery fish instance(s) "
                f"from clutch {clutch_code}: {', '.join(created_codes)}"
            )
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Failed to create nursery fish instances: {type(e).__name__}: {e}")