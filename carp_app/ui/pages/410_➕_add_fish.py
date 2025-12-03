# carp_app/ui/pages/410_➕_add_fish.py
# ➕ Add fish (lines • alleles • instances) — v11

from __future__ import annotations

import os
import sys
import uuid
import pathlib
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ── repo wiring / auth / engine ──────────────────────────────────────────────
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

from carp_app.ui.lib.page_engine import engine as _engine
from carp_app.etl.fish_v11_shared import ensure_tank_for_instance

# ── auth gates ───────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — ➕ Add fish (lines • alleles • instances)",
    page_icon="➕",
    layout="wide",
)
st.title("➕ Add fish (lines • alleles • instances) — v11")


def eng() -> Engine:
    return _engine()


def _norm(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None


def _coerce_date(value: Any) -> Optional[date]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def load_constructs() -> pd.DataFrame:
    sql = text(
        """
        SELECT
          construct_code,
          COALESCE(construct_name,'')    AS construct_name,
          COALESCE(construct_kind,'')    AS construct_kind,
          COALESCE(fusion_pretty,'')     AS fusion_pretty,
          COALESCE(organelle_fluors,'')  AS organelle_fluors,
          COALESCE(description,'')       AS description
        FROM public.v_constructs_overview
        ORDER BY construct_code;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx)
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df


@st.cache_data(show_spinner=False)
def load_construct_ids() -> pd.DataFrame:
    sql = text(
        """
        SELECT
          id::text AS construct_id,
          construct_code
        FROM public.constructs;
        """
    )
    with eng().begin() as cx:
        return pd.read_sql(sql, cx)


@st.cache_data(show_spinner=False)
def load_all_alleles() -> pd.DataFrame:
    sql = text(
        """
        SELECT
          transgene_base_code,
          allele_number,
          COALESCE(allele_name,'')     AS allele_name,
          COALESCE(allele_nickname,'') AS allele_nickname
        FROM public.transgene_alleles
        ORDER BY transgene_base_code, allele_number;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx)
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df


@st.cache_data(show_spinner=False)
def load_background_choices() -> pd.DataFrame:
    sql = text(
        """
        SELECT
          bg_code,
          COALESCE(bg_name,'')     AS bg_name,
          COALESCE(bg_category,'') AS bg_category
        FROM public.genetic_backgrounds
        ORDER BY bg_code;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx)
    df["bg_code"] = df["bg_code"].astype("string").fillna("")
    df["bg_name"] = df["bg_name"].astype("string").fillna("")
    df["bg_category"] = df["bg_category"].astype("string").fillna("")
    return df


def _suggest_line_nickname(
    constructs_df: pd.DataFrame,
    allele_plan_rows: List[Dict[str, Any]],
    all_alleles_df: pd.DataFrame,
) -> Optional[str]:
    if not allele_plan_rows:
        return None

    tags: List[str] = []
    for row in allele_plan_rows:
        base = row["transgene_base_code"]
        tag = None

        if row["mode"] == "Create new allele":
            tag = row.get("new_allele_nickname") or None
        elif row["mode"] == "Reuse existing allele" and row.get("existing_allele_number") is not None:
            num = int(row["existing_allele_number"])
            existing = all_alleles_df[
                (all_alleles_df["transgene_base_code"] == base)
                & (all_alleles_df["allele_number"] == num)
            ]
            if not existing.empty:
                r = existing.iloc[0]
                tag = (r["allele_nickname"] or "") or (r["allele_name"] or "")

        if not tag:
            c = constructs_df[constructs_df["construct_code"] == base]
            if not c.empty:
                cr = c.iloc[0]
                orgs = (cr["organelle_fluors"] or "").strip()
                fusion = (cr["fusion_pretty"] or "").strip()
                if orgs:
                    tag = orgs.split(",")[0].replace(":", "-")
                elif fusion:
                    tag = fusion.split(",")[0]

        if tag:
            tags.append(f"{base}-{tag}")
        else:
            tags.append(base)

    if len(tags) == 1:
        return tags[0]
    if len(tags) == 2:
        return "+".join(tags)
    return "+".join(tags[:2]) + "+…"


def _generate_line_code(cx) -> str:
    attempt = 0
    while True:
        attempt += 1
        candidate = f"LINE-{uuid.uuid4().hex[:8]}"
        existing = pd.read_sql(
            text(
                """
                SELECT 1
                FROM public.fish_lines
                WHERE line_code = :code
                LIMIT 1;
                """
            ),
            cx,
            params={"code": candidate},
        )
        if existing.empty:
            return candidate
        if attempt > 10:
            raise RuntimeError("Failed to generate unique line_code after 10 attempts")


def _ensure_allele_new_or_existing(
    cx,
    *,
    transgene_base_code: str,
    mode: str,
    existing_allele_number: Optional[int],
    new_allele_nickname: Optional[str],
) -> Tuple[str, int, str]:
    base = _norm(transgene_base_code)
    if not base:
        raise ValueError("transgene_base_code is required for each allele.")

    if mode == "Reuse existing allele":
        if existing_allele_number is None:
            raise ValueError(f"{base}: no existing allele_number selected.")
        row = pd.read_sql(
            text(
                """
                SELECT allele_number, COALESCE(allele_nickname,'') AS allele_nickname
                FROM public.transgene_alleles
                WHERE transgene_base_code = :bc
                  AND allele_number = :num
                LIMIT 1;
                """
            ),
            cx,
            params={"bc": base, "num": existing_allele_number},
        )
        if row.empty:
            raise ValueError(
                f"{base}: existing allele_number {existing_allele_number} not found."
            )
        r = row.iloc[0]
        label = f"{base} #{int(r['allele_number'])}"
        if r["allele_nickname"]:
            label += f" ({r['allele_nickname']})"
        return base, int(r["allele_number"]), label

    if mode != "Create new allele":
        raise ValueError(f"{base}: unknown allele mode '{mode}'")

    nick = _norm(new_allele_nickname)
    if not nick:
        raise ValueError(f"{base}: new allele_nickname is required to create an allele.")

    row = pd.read_sql(
        text(
            """
            SELECT allele_number, COALESCE(allele_nickname,'') AS allele_nickname
            FROM public.transgene_alleles
            WHERE transgene_base_code = :bc
              AND allele_nickname = :nick
            LIMIT 1;
            """
        ),
        cx,
        params={"bc": base, "nick": nick},
    )
    if not row.empty:
        r = row.iloc[0]
        label = f"{base} #{int(r['allele_number'])}"
        if r["allele_nickname"]:
            label += f" ({r['allele_nickname']})"
        return base, int(r["allele_number"]), label

    seq_res = cx.execute(
        text("SELECT nextval('public.transgene_alleles_allele_number_seq') AS n;")
    )
    allele_number = int(seq_res.scalar())
    allele_name = f"gu{allele_number}"

    cx.execute(
        text(
            """
            INSERT INTO public.transgenes (transgene_base_code, description, transgene_name)
            VALUES (:bc, NULL, :bc)
            ON CONFLICT (transgene_base_code) DO NOTHING;
            """
        ),
        {"bc": base},
    )

    cx.execute(
        text(
            """
            INSERT INTO public.transgene_alleles (
              transgene_base_code,
              allele_number,
              allele_name,
              allele_nickname
            )
            VALUES (
              :bc,
              :num,
              :aname,
              :nick
            )
            ON CONFLICT (transgene_base_code, allele_number) DO NOTHING;
            """
        ),
        {
            "bc": base,
            "num": allele_number,
            "aname": allele_name,
            "nick": nick,
        },
    )

    label = f"{base} #{allele_number} ({nick})"
    return base, allele_number, label


def _ensure_group_and_genotype_for_alleles(
    cx,
    *,
    resolved_alleles: List[Dict[str, Any]],
    constructs_ids_df: pd.DataFrame,
) -> Tuple[str, str, str]:
    if not resolved_alleles:
        raise ValueError("No alleles to build genotype / fish_group.")

    code_to_id = {
        r["construct_code"]: r["construct_id"]
        for _, r in constructs_ids_df.iterrows()
    }

    pairs: List[Tuple[str, int]] = []
    for a in resolved_alleles:
        base = a["transgene_base_code"]
        num = int(a["allele_number"])
        if base not in code_to_id:
            raise ValueError(f"Construct code {base} not found in public.constructs.")
        pairs.append((base, num))

    pairs_sorted = sorted(pairs)
    target_set = set(pairs_sorted)

    df = pd.read_sql(
        text(
            """
            SELECT
              fg.id::text        AS fish_group_id,
              fg.genotype_key    AS genotype_key,
              g.id::text         AS genotype_v11_id,
              c.construct_code   AS construct_code,
              j.allele_number    AS allele_number
            FROM public.fish_groups fg
            JOIN public.genotypes_v11 g
              ON g.genotype_code = fg.genotype_key
            JOIN public.join_fish_group_alleles j
              ON j.fish_group_id = fg.id
            JOIN public.constructs c
              ON c.id = j.construct_id;
            """
        ),
        cx,
    )

    if not df.empty:
        grouped = df.groupby(
            ["fish_group_id", "genotype_key", "genotype_v11_id"], as_index=False
        )
        for (fg_id, gkey, g_id), sub in grouped:
            existing_pairs = set(
                (str(sub_row["construct_code"]), int(sub_row["allele_number"]))
                for _, sub_row in sub.iterrows()
            )
            if existing_pairs == target_set:
                return fg_id, g_id, gkey

    base_parts = [f"{code}:{num}" for code, num in pairs_sorted]
    genotype_basecodes = " + ".join(base_parts)
    genotype_code = "G-" + uuid.uuid4().hex[:8]
    genotype_pretty = genotype_basecodes

    g_row = cx.execute(
        text(
            """
            INSERT INTO public.genotypes_v11 (
              genotype_code,
              genotype_pretty,
              genotype_basecodes,
              source_system
            )
            VALUES (
              :gcode,
              :gpretty,
              :gbasecodes,
              'add_fish_page_v11'
            )
            RETURNING id::text AS genotype_v11_id, genotype_code;
            """
        ),
        {
            "gcode": genotype_code,
            "gpretty": genotype_pretty,
            "gbasecodes": genotype_basecodes,
        },
    ).fetchone()

    genotype_v11_id = g_row._mapping["genotype_v11_id"]
    genotype_code = g_row._mapping["genotype_code"]

    group_code = "GROUP-" + uuid.uuid4().hex[:8]
    fg_row = cx.execute(
        text(
            """
            INSERT INTO public.fish_groups (
              genotype_key,
              nickname,
              created_at,
              group_code
            )
            VALUES (
              :gkey,
              NULL,
              now(),
              :gcode
            )
            RETURNING id::text AS fish_group_id;
            """
        ),
        {"gkey": genotype_code, "gcode": group_code},
    ).fetchone()

    fish_group_id = fg_row._mapping["fish_group_id"]

    for base, num in pairs_sorted:
        construct_id = code_to_id[base]
        cx.execute(
            text(
                """
                INSERT INTO public.join_fish_group_alleles (
                  fish_group_id,
                  construct_id,
                  allele_number
                )
                VALUES (
                  :fgid,
                  :cid,
                  :anum
                )
                ON CONFLICT DO NOTHING;
                """
            ),
            {"fgid": fish_group_id, "cid": construct_id, "anum": num},
        )

    return fish_group_id, genotype_v11_id, genotype_code


def _ensure_line_for_description(
    cx,
    *,
    fish_group_id: str,
    nickname: str,
    primary_base_code: str,
    default_bg_code: Optional[str],
) -> Tuple[str, str, bool]:
    nn = _norm(nickname)
    bc = _norm(primary_base_code)

    if not nn:
        raise ValueError("Line nickname is required.")
    if not bc:
        raise ValueError("Primary construct base_code is required to define the line.")
    if not fish_group_id:
        raise ValueError("fish_group_id is required to create a line.")

    existing = pd.read_sql(
        text(
            """
            SELECT id::text AS line_id, line_code::text AS line_code
            FROM public.fish_lines
            WHERE nickname = :nn
              AND construct_code = :bc
              AND fish_group_id = :fgid
            ORDER BY created_at ASC
            LIMIT 1;
            """
        ),
        cx,
        params={"nn": nn, "bc": bc, "fgid": fish_group_id},
    )

    if not existing.empty:
        r = existing.iloc[0]
        return r["line_id"], r["line_code"], False

    line_code = _generate_line_code(cx)
    line_row = cx.execute(
        text(
            """
            INSERT INTO public.fish_lines (
              line_code,
              nickname,
              genetic_background,
              line_building_stage,
              notes,
              created_at,
              fish_group_id,
              group_instance_code,
              construct_code
            )
            VALUES (
              :code,
              :nickname,
              :bg,
              NULL,
              NULL,
              now(),
              :fgid,
              NULL,
              :construct_code
            )
            RETURNING id::text AS line_id, line_code;
            """
        ),
        {
            "code": line_code,
            "nickname": nn,
            "bg": default_bg_code,
            "fgid": fish_group_id,
            "construct_code": bc,
        },
    ).fetchone()

    return line_row._mapping["line_id"], line_row._mapping["line_code"], True


def _create_instances_with_genotype_and_bg(
    cx,
    *,
    line_id: str,
    line_code: str,
    genotype_v11_id: str,
    instances: List[Dict[str, Any]],
) -> Tuple[int, int]:
    """
    Create instances under the given line_id, set genotype_v11_id, genetic_background,
    and create tanks. Returns (n_instances, n_tanks).

    fish_code:      canonical instance ID (FSH-xxxxxxxx by default)
    line_code:      stable line ID (LINE-xxxxxxxx)
    line_instance_code: internal per-line instance label (LINE-<frag>-<stage>-NNN)
    """
    n_instances = 0
    n_tanks = 0

    for idx, inst in enumerate(instances, start=1):
        provided_fish_code = _norm(inst.get("fish_code"))
        stage = _norm(inst.get("instance_stage"))
        notes = _norm(inst.get("notes"))
        birthday = _coerce_date(inst.get("birthday"))
        bg_code = _norm(inst.get("genetic_background"))

        if birthday is None:
            raise ValueError("Birthday is required for each instance.")
        if not bg_code:
            raise ValueError("Genetic background (bg_code) is required for each instance.")

        if provided_fish_code:
            fish_code = provided_fish_code
        else:
            fish_code = f"FSH-{uuid.uuid4().hex[:8]}"

        suffix = f"{idx:03d}"
        prefix = stage or "inst"
        line_instance_code = f"{line_code}-{prefix}-{suffix}"

        ins = cx.execute(
            text(
                """
                INSERT INTO public.fish_instances_v10 (
                  line_id,
                  fish_code,
                  line_instance_code,
                  birthday,
                  instance_stage,
                  notes,
                  genotype_v11_id,
                  genetic_background,
                  created_at
                )
                VALUES (
                  :line_id,
                  :fish_code,
                  :line_instance_code,
                  :birthday,
                  :instance_stage,
                  :notes,
                  :genotype_id,
                  :bg,
                  now()
                )
                RETURNING id::text AS fish_instance_id;
                """
            ),
            {
                "line_id": line_id,
                "fish_code": fish_code,
                "line_instance_code": line_instance_code,
                "birthday": birthday,
                "instance_stage": stage,
                "notes": notes,
                "genotype_id": genotype_v11_id,
                "bg": bg_code,
            },
        ).fetchone()

        fish_id = ins._mapping["fish_instance_id"]
        n_instances += 1

        ensure_tank_for_instance(cx, fish_id, fish_code)
        n_tanks += 1

    return n_instances, n_tanks


# ── UI ────────────────────────────────────────────────────────────────────────

st.markdown(
    """
Use this page to add **new fish instances** into the v11 system:

1. Select one or more constructs (transgene base codes).  
2. For each base code, either **reuse an existing allele** or **create a new allele** (by nickname).  
3. Choose a line nickname (the DB will reuse or create a line for the genotype).  
4. Define one or more instances; each instance has its own background, stage, birthday, and notes.
"""
)

constructs = load_constructs()
constructs_ids_df = load_construct_ids()
all_alleles_df = load_all_alleles()
bg_df = load_background_choices()

if constructs.empty:
    st.warning(
        "No constructs found in v_constructs_overview — run your constructs loader first."
    )
    st.stop()

st.markdown("### Step 1 — Select construct base codes")
st.caption("Use the ✓ column to choose which constructs will define alleles.")

base_cols = [
    "construct_code",
    "construct_name",
    "construct_kind",
    "fusion_pretty",
    "organelle_fluors",
]

constructs_view = constructs[base_cols].copy()
constructs_view.insert(0, "selected", False)

edited_constructs = st.data_editor(
    constructs_view,
    key="add_fish_construct_picker",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "selected": st.column_config.CheckboxColumn("✓", default=False),
        "construct_code": st.column_config.TextColumn(
            "Construct", help="transgene_base_code"
        ),
        "construct_name": st.column_config.TextColumn("Name"),
        "construct_kind": st.column_config.TextColumn("Kind"),
        "fusion_pretty": st.column_config.TextColumn(
            "Fusions (fluor::tag)", width="large"
        ),
        "organelle_fluors": st.column_config.TextColumn(
            "Organelle-fluor", width="large"
        ),
    },
)

selected_mask = edited_constructs["selected"].fillna(False).astype(bool)
selected_codes: List[str] = (
    edited_constructs.loc[selected_mask, "construct_code"].astype(str).tolist()
)

st.caption(
    "Selected construct base codes: "
    + (", ".join(selected_codes) if selected_codes else "none")
)

st.markdown("### Step 1b — Define alleles for these constructs")

st.caption(
    "For each selected construct, either pick an **existing allele** or choose to "
    "**create a new allele**. New alleles are identified by a single "
    "**allele_nickname**."
)

allele_plan_rows: List[Dict[str, Any]] = []

if not selected_codes:
    st.info("Select at least one construct above to define alleles.")
else:
    for base_code in selected_codes:
        df_existing = all_alleles_df[
            all_alleles_df["transgene_base_code"] == base_code
        ].copy()

        with st.expander(f"{base_code} — define allele", expanded=True):
            if df_existing.empty:
                st.caption("No existing alleles found for this base code.")
            else:
                df_existing = df_existing.copy()
                df_existing["label"] = df_existing.apply(
                    lambda r: " ".join(
                        [
                            f"#{r['allele_number']}",
                            (r["allele_name"] or ""),
                            f"({r['allele_nickname']})" if r["allele_nickname"] else "",
                        ]
                    ).strip(),
                    axis=1,
                )
                st.caption("Existing alleles for this base code:")
                st.dataframe(
                    df_existing[
                        [
                            "allele_number",
                            "allele_name",
                            "allele_nickname",
                            "label",
                        ]
                    ],
                    hide_index=True,
                    use_container_width=True,
                )

            mode_key = f"allele_mode_{base_code}"
            mode = st.radio(
                "How should this allele be handled?",
                ["Reuse existing allele", "Create new allele"],
                key=mode_key,
                horizontal=True,
            )

            chosen_existing: Optional[int] = None
            new_nickname: Optional[str] = None

            if mode == "Reuse existing allele":
                if df_existing.empty:
                    st.warning(
                        "No existing alleles for this base code; you must create a new allele."
                    )
                else:
                    options = df_existing["label"].tolist()
                    label_to_number = dict(
                        zip(df_existing["label"], df_existing["allele_number"])
                    )
                    choice = st.selectbox(
                        "Choose existing allele",
                        options=options,
                        key=f"allele_existing_choice_{base_code}",
                    )
                    chosen_existing = int(label_to_number[choice])
            else:
                new_nickname = _norm(
                    st.text_input(
                        "New allele_nickname (required to create new allele)",
                        value="",
                        key=f"allele_new_nickname_{base_code}",
                    )
                )
                st.caption(
                    "This nickname will be stored on the new allele. "
                    "If you wanted to reuse an existing allele, switch to 'Reuse existing allele'."
                )

        allele_plan_rows.append(
            {
                "transgene_base_code": base_code,
                "mode": st.session_state.get(mode_key, "Reuse existing allele"),
                "existing_allele_number": chosen_existing,
                "new_allele_nickname": new_nickname,
            }
        )

if allele_plan_rows:
    st.markdown("#### Current allele plan (preview only, no DB writes yet)")
    plan_df = pd.DataFrame(allele_plan_rows)
    st.dataframe(plan_df, hide_index=True, use_container_width=True)

st.markdown("### Step 2 — Line nickname")

st.caption(
    "Choose a nickname for this line. The database will reuse an existing line "
    "for this genotype + nickname + primary construct, or create a new one."
)

suggested_nickname = _suggest_line_nickname(constructs, allele_plan_rows, all_alleles_df)
prev_suggestion = st.session_state.get("line_nickname_last_suggestion")
current_value = st.session_state.get("line_nickname_input", "")

if suggested_nickname:
    if not current_value:
        st.session_state["line_nickname_input"] = suggested_nickname
        st.session_state["line_nickname_last_suggestion"] = suggested_nickname
    elif current_value == prev_suggestion:
        st.session_state["line_nickname_input"] = suggested_nickname
        st.session_state["line_nickname_last_suggestion"] = suggested_nickname

c1, _c2, _c3 = st.columns([2, 2, 2])
with c1:
    line_nickname = st.text_input(
        "Line nickname",
        key="line_nickname_input",
    )

st.markdown("### Step 3 — Define new fish instances")

st.caption(
    "Each checked row becomes a new `fish_instances_v10` under the resolved line, "
    "linked to the genotype implied by the allele set. "
    "**Background and stage are per-instance**."
)

default_bg_code = None
if bg_df.empty:
    st.warning("No genetic backgrounds defined; please load genetic_backgrounds.")
else:
    bg_codes = bg_df["bg_code"].tolist()
    bg_labels = []
    for _, row in bg_df.iterrows():
        parts = [row["bg_code"]]
        if row["bg_name"]:
            parts.append(f"— {row['bg_name']}")
        if row["bg_category"]:
            parts.append(f"[{row['bg_category']}]")
        bg_labels.append(" ".join(parts))
    default_bg_code = st.selectbox(
        "Default genetic background (bg_code) for instances",
        options=bg_codes,
        format_func=lambda code: bg_labels[bg_codes.index(code)],
        key="instance_default_bg_code",
    )

inst_df_initial = pd.DataFrame(
    [
        {
            "✓ Add": True,
            "fish_code": "",
            "instance_stage": "",
            "birthday": date.today(),
            "genetic_background": default_bg_code or "",
            "notes": "",
        }
    ]
)

inst_grid = st.data_editor(
    inst_df_initial,
    key="add_fish_instances_grid",
    hide_index=True,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "✓ Add": st.column_config.CheckboxColumn("Add", default=True),
        "fish_code": st.column_config.TextColumn(
            "Fish code (optional, FSH-…)",
            help="If empty, a code like FSH-xxxxxxxx will be generated.",
        ),
        "instance_stage": st.column_config.TextColumn(
            "Instance stage",
            help="e.g. f1, f2, juvenile, adult…",
        ),
        "birthday": st.column_config.DateColumn("Birth date"),
        "genetic_background": st.column_config.TextColumn(
            "Genetic background (bg_code)",
            help="Instance-level background (bg_code).",
        ),
        "notes": st.column_config.TextColumn("Notes", width="large"),
    },
)

submitted = st.button(
    "➕ Add fish (lines • alleles • instances)",
    type="primary",
    use_container_width=True,
)

if submitted:
    try:
        if not selected_codes:
            raise ValueError("Select at least one construct in Step 1.")

        if not allele_plan_rows:
            raise ValueError("Define at least one allele in Step 1b.")

        inst_df = inst_grid
        if inst_df is None or inst_df.empty:
            raise ValueError("No instances defined; please add at least one row.")

        instance_rows: List[Dict[str, Any]] = []
        for _, r in inst_df.iterrows():
            if not bool(r.get("✓ Add")):
                continue
            instance_rows.append(
                {
                    "fish_code": _norm(r.get("fish_code")),
                    "instance_stage": _norm(r.get("instance_stage")),
                    "birthday": r.get("birthday"),
                    "genetic_background": _norm(r.get("genetic_background")),
                    "notes": _norm(r.get("notes")),
                }
            )

        if not instance_rows:
            raise ValueError(
                "No instances selected to add. Check at least one row in the instances table."
            )

        primary_base_code = selected_codes[0] if selected_codes else None

        with eng().begin() as cx:
            resolved_alleles: List[Dict[str, Any]] = []
            for row in allele_plan_rows:
                base = row["transgene_base_code"]
                mode = row["mode"]
                existing_num = row["existing_allele_number"]
                new_nick = row["new_allele_nickname"]

                base2, num, label = _ensure_allele_new_or_existing(
                    cx,
                    transgene_base_code=base,
                    mode=mode,
                    existing_allele_number=existing_num,
                    new_allele_nickname=new_nick,
                )
                resolved_alleles.append(
                    {
                        "transgene_base_code": base2,
                        "allele_number": num,
                        "label": label,
                    }
                )

            fish_group_id, genotype_v11_id, genotype_code = _ensure_group_and_genotype_for_alleles(
                cx,
                resolved_alleles=resolved_alleles,
                constructs_ids_df=constructs_ids_df,
            )

            default_bg_for_line = instance_rows[0]["genetic_background"] if instance_rows else None

            line_id, line_code, created_new_line = _ensure_line_for_description(
                cx,
                fish_group_id=fish_group_id,
                nickname=line_nickname,
                primary_base_code=primary_base_code or "",
                default_bg_code=default_bg_for_line,
            )

            n_instances, n_tanks = _create_instances_with_genotype_and_bg(
                cx,
                line_id=line_id,
                line_code=line_code,
                genotype_v11_id=genotype_v11_id,
                instances=instance_rows,
            )

        if created_new_line:
            st.success(
                f"Created new line {line_code} (genotype {genotype_code}) and "
                f"{n_instances} fish instance(s) with {n_tanks} tank(s)."
            )
        else:
            st.success(
                f"Reused existing line {line_code} (genotype {genotype_code}) and "
                f"added {n_instances} fish instance(s) with {n_tanks} tank(s)."
            )

    except Exception as e:
        st.error(f"Error while adding fish: {e}")
