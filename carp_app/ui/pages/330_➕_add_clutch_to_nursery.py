# carp_app/ui/pages/330_➕_add_clutch_to_nursery.py
# 🧱 Add clutch to nursery — convert clutch → fish_instances_v10 (+ create tanks)

from __future__ import annotations

import sys
import pathlib
import uuid
from datetime import date
from typing import Optional, Dict, List, Any, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

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
from carp_app.ui.lib.app_ctx import get_engine

V_CLUTCH_FLAT = "public.v11_clutch_treated_groups_flat"
V_FISH_LINE_STAR = "public.v11_fish_line_star"

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🧱 Add clutch to nursery",
    page_icon="🧱",
    layout="wide",
)
st.title("🧱 Add clutch to nursery — convert clutch → fish instances (and tanks)")


def eng() -> Engine:
    return get_engine()


def _who() -> str:
    return getattr(user, "email", None) or st.session_state.get("user_email") or "system"


@st.cache_data(show_spinner=False)
def _cols(schema: str, name: str) -> List[str]:
    sql = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :s AND table_name = :t
        ORDER BY ordinal_position;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"s": schema, "t": name})
    return df["column_name"].astype(str).tolist()


@st.cache_data(show_spinner=False)
def load_clutch_rows(q: str, d_from: Optional[str], d_to: Optional[str], limit: int) -> pd.DataFrame:
    qn = (q or "").strip()
    like = f"%{qn}%" if qn else None

    sql = text(
        f"""
        SELECT
          COALESCE(treated_clutch_id::text,'') AS treated_clutch_id,
          COALESCE(treated_clutch_code,'')     AS treated_clutch_code,

          clutch_id::text                      AS clutch_id,
          clutch_code                          AS clutch_code,
          clutch_date                          AS clutch_date,

          COALESCE(genotype_pretty,'')         AS genotype_pretty,
          COALESCE(genotype_basecodes,'')      AS genotype_basecodes,

          COALESCE(treatment_code,'')          AS treatment_code,
          COALESCE(treat_basecodes,'')         AS treat_basecodes,

          COALESCE(marker_basecode_style,'')   AS marker_rollup_tg_style,
          COALESCE(marker_fluortag_style,'')   AS marker_rollup_fluortag_style,
          COALESCE(marker_organelle_style,'')  AS marker_rollup_fluororganelle_style,

          COALESCE(assign_code,'')             AS assign_code
        FROM {V_CLUTCH_FLAT}
        WHERE
          (:q IS NULL)
          OR (
               clutch_code ILIKE :ql
            OR COALESCE(treated_clutch_code,'') ILIKE :ql
            OR COALESCE(treatment_code,'') ILIKE :ql
            OR COALESCE(genotype_pretty,'') ILIKE :ql
            OR COALESCE(genotype_basecodes,'') ILIKE :ql
            OR COALESCE(marker_basecode_style,'') ILIKE :ql
            OR COALESCE(marker_fluortag_style,'') ILIKE :ql
            OR COALESCE(marker_organelle_style,'') ILIKE :ql
            OR COALESCE(assign_code,'') ILIKE :ql
          )
          AND (:d_from IS NULL OR clutch_date >= CAST(:d_from AS date))
          AND (:d_to   IS NULL OR clutch_date <= CAST(:d_to AS date))
        ORDER BY clutch_date DESC NULLS LAST, clutch_code, treated_clutch_code
        LIMIT :lim;
        """
    )

    with eng().begin() as cx:
        df = pd.read_sql(
            sql,
            cx,
            params={"q": qn if qn else None, "ql": like, "d_from": d_from, "d_to": d_to, "lim": int(limit)},
        )

    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    df = df.fillna("")

    def _kind_row(r: pd.Series) -> str:
        geno = (r.get("genotype_basecodes") or "").strip()
        treat = (r.get("treat_basecodes") or "").strip()
        if treat and not geno:
            return "treated only"
        if geno and not treat:
            return "transgenic only"
        if geno and treat:
            return "treated transgenic"
        return "none"

    df["kind"] = df.apply(_kind_row, axis=1)
    return df


@st.cache_data(show_spinner=False)
def load_all_lines() -> pd.DataFrame:
    sql = text(
        f"""
        SELECT
          line_id::text AS line_id,
          COALESCE(line_code,'') AS line_code,
          COALESCE(line_nickname,'') AS line_nickname,
          COALESCE(genetic_background,'') AS genetic_background,
          COALESCE(line_building_stage,'') AS line_building_stage,
          COALESCE(genotype_pretty,'') AS genotype_pretty
        FROM {V_FISH_LINE_STAR}
        ORDER BY line_code;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx)

    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df.fillna("")


def _insert_tank_for_fish(cx, fish_instance_id: str, created_by: str) -> Tuple[Optional[str], Optional[str]]:
    tank_cols = _cols("public", "tanks")
    has = set(tank_cols)

    tank_uuid = str(uuid.uuid4())
    tank_code = f"T-{tank_uuid[:8]}"

    cols: List[str] = []
    vals: List[str] = []
    params: Dict[str, Any] = {
        "tank_id": tank_uuid,
        "tank_code": tank_code,
        "fish_instance_id": fish_instance_id,
        "created_by": created_by,
    }

    if "id" in has:
        cols.append("id")
        vals.append("CAST(:tank_id AS uuid)")
    if "tank_code" in has:
        cols.append("tank_code")
        vals.append(":tank_code")
    if "fish_instance_id" in has:
        cols.append("fish_instance_id")
        vals.append("CAST(:fish_instance_id AS uuid)")
    if "status" in has:
        cols.append("status")
        vals.append("'active'")
    if "created_at" in has:
        cols.append("created_at")
        vals.append("now()")
    if "created_by" in has:
        cols.append("created_by")
        vals.append(":created_by")

    if not cols:
        raise RuntimeError(f"public.tanks has no insertable columns we recognize. Columns: {tank_cols}")

    returning = "id::text, COALESCE(tank_code,'')::text" if "id" in has else "COALESCE(tank_code,'')::text"
    sql = text(
        f"INSERT INTO public.tanks ({', '.join(cols)}) VALUES ({', '.join(vals)}) RETURNING {returning};"
    )

    row = cx.execute(sql, params).fetchone()
    if not row:
        return None, None
    if "id" in has:
        return str(row[0]), str(row[1])
    return None, str(row[0])


def _resolve_genotype_v11_id(cx, clutch_id_text: str, genotype_basecodes: str) -> str:
    clutch_gid = cx.execute(
        text("SELECT genotype_v11_id::text FROM public.clutches WHERE id = CAST(:cid AS uuid)"),
        {"cid": clutch_id_text},
    ).scalar()

    if clutch_gid:
        return str(clutch_gid)

    gb = (genotype_basecodes or "").strip()
    if not gb:
        raise RuntimeError(
            f"Clutch {clutch_id_text} has NULL genotype_v11_id and empty genotype_basecodes; cannot resolve."
        )

    gid2 = cx.execute(
        text(
            """
            SELECT id::text
            FROM public.genotypes_v11
            WHERE replace(COALESCE(genotype_basecodes,''),' ','') = replace(:gb,' ','')
            LIMIT 1;
            """
        ),
        {"gb": gb},
    ).scalar()

    if gid2:
        return str(gid2)

    raise RuntimeError(
        f"Clutch {clutch_id_text} has NULL genotype_v11_id and no genotypes_v11 row matches genotype_basecodes='{gb}'. "
        "Fix the clutch genotype at the source (set clutches.genotype_v11_id or create the genotype)."
    )


# ════════════════════════════════════════════════════════
# STEP 1 — Select clutch rows
# ════════════════════════════════════════════════════════

st.subheader("Step 1 — Select clutch row(s)", anchor=False)

with st.form("clutch_filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([4, 2, 2, 1])
    with c1:
        q = st.text_input("Search", value="", key="clutch_search")
    with c2:
        d_from = st.text_input("From clutch_date (YYYY-MM-DD)", value="", key="clutch_from")
    with c3:
        d_to = st.text_input("To clutch_date (YYYY-MM-DD)", value="", key="clutch_to")
    with c4:
        lim = int(st.number_input("Limit", min_value=10, max_value=5000, value=200, step=50, key="clutch_limit"))
    st.form_submit_button("Apply")

d_from_norm = (d_from or "").strip() or None
d_to_norm = (d_to or "").strip() or None

flat = load_clutch_rows(q, d_from_norm, d_to_norm, lim)
if flat.empty:
    st.info("No clutch rows match the current filters.")
    st.stop()

view = flat[
    [
        "kind",
        "clutch_code",
        "clutch_date",
        "treated_clutch_code",
        "treatment_code",
        "genotype_pretty",
        "marker_rollup_tg_style",
        "marker_rollup_fluortag_style",
        "marker_rollup_fluororganelle_style",
        "assign_code",
    ]
].copy()
view.insert(0, "✓", False)

grid = st.data_editor(
    view,
    key="clutch_picker_flat_multi",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓": st.column_config.CheckboxColumn("✓", default=False),
        "kind": st.column_config.TextColumn("Kind", disabled=True),
        "clutch_code": st.column_config.TextColumn("Clutch", disabled=True),
        "clutch_date": st.column_config.DateColumn("Clutch date", disabled=True),
        "treated_clutch_code": st.column_config.TextColumn("Treated clutch", disabled=True),
        "treatment_code": st.column_config.TextColumn("Treatment", disabled=True),
        "genotype_pretty": st.column_config.TextColumn("Genotype", disabled=True, width="large"),
        "marker_rollup_tg_style": st.column_config.TextColumn("Marker rollup (tg)", disabled=True, width="large"),
        "marker_rollup_fluortag_style": st.column_config.TextColumn("Marker rollup (fluor-tag)", disabled=True, width="large"),
        "marker_rollup_fluororganelle_style": st.column_config.TextColumn("Marker rollup (fluor-organelle)", disabled=True, width="large"),
        "assign_code": st.column_config.TextColumn("Assign code", disabled=True),
    },
)

sel_mask = grid.get("✓", pd.Series(False, index=grid.index)).fillna(False).astype(bool)
selected_idxs = grid.index[sel_mask].tolist()
if not selected_idxs:
    st.info("Select one or more rows above to continue.")
    st.stop()

selected_rows = flat.iloc[selected_idxs].copy()
st.success(f"Selected {len(selected_rows)} row(s).")

# ════════════════════════════════════════════════════════
# STEP 2 — Choose/auto line, nickname, n-per-row
# ════════════════════════════════════════════════════════

st.markdown("---")
st.subheader("Step 2 — Configure nursery fish instances", anchor=False)

lines = load_all_lines()
if lines.empty:
    st.warning("No fish lines found.")
    st.stop()

unique_genos = sorted(set([str(x or "") for x in selected_rows["genotype_pretty"].tolist() if str(x or "").strip()]))
geno_for_match = unique_genos[0] if len(unique_genos) == 1 else ""

matches = lines[lines["genotype_pretty"].astype(str) == geno_for_match].copy() if geno_for_match else lines.iloc[0:0].copy()

needs_confirm = False
fixed_line_id: Optional[str] = None

if geno_for_match and len(matches) == 1:
    fixed_line_id = str(matches.iloc[0]["line_id"])
    fixed_line_label = f"{matches.iloc[0]['line_code']} — {matches.iloc[0]['line_nickname']} [{matches.iloc[0]['genetic_background']}]"
    st.caption("Auto-selected the single matching line for this genotype.")
    st.markdown(f"**Line:** {fixed_line_label}")
elif geno_for_match and len(matches) == 0:
    st.warning("No matching line found for this genotype. Choose a line manually.")
    needs_confirm = True
elif geno_for_match and len(matches) > 1:
    st.warning("Multiple matching lines found. Choose which line to use.")
else:
    st.warning("Multiple genotypes selected. Choose a line manually (or select a single genotype set).")
    needs_confirm = True

line_options = [f"{r['line_code']} — {r['line_nickname']} [{r['genetic_background']}]" for _, r in lines.iterrows()]
line_idx_to_line_id = {idx: str(r["line_id"]) for idx, r in enumerate(lines.to_dict("records"))}

with st.form("nursery_instance_form", clear_on_submit=False):
    c1, c2 = st.columns([2, 1])
    with c1:
        if fixed_line_id:
            chosen_line_id = fixed_line_id
            st.markdown("**Line selection is fixed (single match).**")
        else:
            line_idx = st.selectbox(
                "Line to assign nursery instances into",
                options=list(range(len(line_options))),
                format_func=lambda i: line_options[i],
                index=0,
            )
            chosen_line_id = line_idx_to_line_id[line_idx]

        instance_stage = st.text_input(
            "Instance stage (e.g. F0, P0, F1, F2)",
            value="",
        )

        instance_nickname = st.text_input(
            "Instance nickname (optional)",
            value="",
            help="Saved into public.fish_instances_v10.nickname. Applied to all created instances.",
        )

    with c2:
        n_per_row = int(st.number_input("New instances per selected row", min_value=1, max_value=200, value=1, step=1))
        line_bg = ""
        m = lines[lines["line_id"].astype(str) == str(chosen_line_id)]
        if not m.empty:
            line_bg = str(m.iloc[0]["genetic_background"] or "")
        genetic_background = st.text_input(
            "Genetic background (auto-filled from line; override if needed)",
            value=line_bg,
        )

    confirm_first_members = True
    if needs_confirm:
        confirm_first_members = st.checkbox(
            "I understand I am manually assigning these clutch rows into the selected line.",
            value=False,
        )

    notes = st.text_area("Notes for these nursery instances (optional)", "", height=80)
    submit = st.form_submit_button("💾 Create nursery fish instances + tanks", use_container_width=True)

# ════════════════════════════════════════════════════════
# STEP 3 — Create fish instances + tanks with resolved genotype_v11_id
# ════════════════════════════════════════════════════════

if submit:
    if needs_confirm and not confirm_first_members:
        st.error("Please confirm manual assignment to proceed.")
        st.stop()

    if not (instance_stage or "").strip():
        st.error("Instance stage is required (e.g. F0, P0, F1, F2).")
        st.stop()

    created_by = _who()
    created_fish: List[str] = []
    created_tanks: List[str] = []

    try:
        with eng().begin() as cx:
            for _, row in selected_rows.iterrows():
                clutch_id = str(row.get("clutch_id") or "")
                if not clutch_id:
                    raise RuntimeError("Selected row missing clutch_id.")

                genotype_basecodes = str(row.get("genotype_basecodes") or "")
                gid = _resolve_genotype_v11_id(cx, clutch_id, genotype_basecodes)

                clutch_date = row.get("clutch_date", None)

                for _k in range(int(n_per_row)):
                    fish_code = f"FSH-{uuid.uuid4().hex[:8]}"
                    line_instance_code = fish_code

                    ins = cx.execute(
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
                              genetic_background,
                              nickname,
                              origin_kind,
                              source_clutch_id
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
                              :genetic_background,
                              NULLIF(:nickname,''),
                              :origin_kind,
                              CAST(:source_clutch_id AS uuid)
                            )
                            RETURNING id::text;
                            """
                        ),
                        {
                            "line_instance_code": line_instance_code,
                            "line_id": chosen_line_id,
                            "birthday": clutch_date if isinstance(clutch_date, date) else date.today(),
                            "notes": notes.strip() or None,
                            "fish_code": fish_code,
                            "genotype_v11_id": gid,
                            "instance_stage": (instance_stage or "").strip(),
                            "genetic_background": (genetic_background or "").strip() or None,
                            "nickname": (instance_nickname or "").strip(),
                            "origin_kind": "nursery_from_clutch",
                            "source_clutch_id": clutch_id,
                        },
                    )
                    fish_instance_id = ins.scalar()
                    created_fish.append(fish_code)

                    _tank_id, tank_code = _insert_tank_for_fish(cx, fish_instance_id, created_by)
                    if tank_code:
                        created_tanks.append(tank_code)

        st.success(f"Created {len(created_fish)} fish instance(s): {', '.join(created_fish)}")
        st.success(f"Created {len(created_tanks)} tank(s): {', '.join(created_tanks)}")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Failed: {type(e).__name__}: {e}")