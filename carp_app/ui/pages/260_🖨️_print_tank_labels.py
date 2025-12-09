# carp_app/ui/pages/260_🖨️_print_tank_labels.py
# 🖨️ Print tank labels (v11) — tank_code, nickname, treatment/genotype styles, organelle-fluor, Tank N + DOB

from __future__ import annotations

import sys, pathlib
from typing import List, Dict, Tuple, Any

import pandas as pd
import streamlit as st
from sqlalchemy import text, bindparam
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import ARRAY, TEXT

# ── repo path wiring ─────────────────────────────────────────────────────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── auth / engine / labels helpers ───────────────────────────────────────────
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine as _engine

HAVE_PRINT_HELPER = False
try:
    from carp_app.ui.lib.labels_components import download_button_for_labels
    HAVE_PRINT_HELPER = True
except Exception:
    pass

# ── auth gates ───────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🖨️ Print tank labels",
    page_icon="🖨️",
    layout="wide",
)
st.title("🖨️ Print tank labels")


def eng() -> Engine:
    return _engine()


# ── helpers ──────────────────────────────────────────────────────────────────
def _vert_table(title: str, kv_pairs: List[Tuple[str, Any]]):
    tbl = pd.DataFrame(kv_pairs, columns=["Field", "Value"])
    tbl["Field"] = tbl["Field"].astype("string")
    tbl["Value"] = tbl["Value"].astype("string").fillna("")
    st.markdown(f"**{title}**")
    st.dataframe(tbl, hide_index=True, use_container_width=True)


def _safe(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (pd.Timestamp,)):
        return v.strftime("%Y-%m-%d")
    return str(v)


# ── data loaders (v11) ───────────────────────────────────────────────────────
def _load_fish(q: str | None, limit: int) -> pd.DataFrame:
    sql = text(
        """
        WITH fis AS (
          SELECT
            fish_instance_id,
            fish_code,
            birthday,
            genetic_background,
            instance_stage,
            genotype_pretty,
            line_code,
            line_nickname
          FROM public.v11_fish_instance_star
        ),
        markers AS (
          SELECT
            fish_instance_id,
            organelle_fluor_rollup
          FROM public.v11_fish_marker_rollups
        )
        SELECT
          fis.fish_code::text                     AS fish_code,
          COALESCE(fis.line_nickname, '')         AS nickname,
          fis.birthday                            AS dob,
          COALESCE(fis.genetic_background, '')    AS genetic_background,
          COALESCE(fis.instance_stage, '')        AS line_building_stage,
          COALESCE(fis.genotype_pretty, '')       AS genotype_pretty,
          COALESCE(mr.organelle_fluor_rollup,'')  AS organelle_fluor
        FROM fis
        LEFT JOIN markers mr
          ON mr.fish_instance_id = fis.fish_instance_id
        WHERE (:q IS NULL)
           OR fis.fish_code                 ILIKE :ql
           OR COALESCE(fis.line_nickname,'')      ILIKE :ql
           OR COALESCE(fis.genetic_background,'') ILIKE :ql
           OR COALESCE(fis.instance_stage,'')     ILIKE :ql
           OR COALESCE(fis.genotype_pretty,'')    ILIKE :ql
        ORDER BY fis.birthday DESC NULLS LAST, fis.fish_code
        LIMIT :lim
        """
    )

    qnorm = (q or "").strip()
    params = {
        "q": qnorm if qnorm else None,
        "ql": f"%{qnorm}%" if qnorm else None,
        "lim": int(limit),
    }

    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")

    return df


def _load_tanks_for_fish(fish_codes: List[str]) -> pd.DataFrame:
    if not fish_codes:
        return pd.DataFrame(
            columns=[
                "tank_code",
                "fish_code",
                "nickname",
                "allele_labels",
                "allele_canonical",
                "line_building_stage",
                "dob",
                "organelle_fluor",
                "tg_style",
                "fluortag_style",
                "fluororganelle_style",
                "tank_index",
            ]
        )

    sql = (
        text(
            """
            SELECT
              t.tank_code,
              fis.fish_code,
              COALESCE(fis.line_nickname, '')              AS nickname,
              -- canonical-only rollup
              COALESCE(fa.allele_canonical_rollup, '')      AS allele_canonical,
              -- canonical + pretty label for display on labels
              COALESCE(
                NULLIF(fa.allele_canonical_rollup, ''),
                ''
              ) ||
              CASE
                WHEN fa.allele_label_rollup IS NOT NULL
                     AND fa.allele_label_rollup <> ''
                  THEN ' ' || fa.allele_label_rollup
                ELSE ''
              END                                           AS allele_labels,
              COALESCE(fis.instance_stage, '')              AS line_building_stage,
              fis.birthday                                  AS dob,
              COALESCE(mr.organelle_fluor_rollup, '')       AS organelle_fluor,
              -- treatment > genotype / genotype only / background only (tg style)
              CASE
                WHEN flbls.treatment_codes IS NOT NULL AND flbls.genotype_tg_style IS NOT NULL
                  THEN flbls.treatment_label_tg_style || ' > ' || flbls.genotype_tg_style
                WHEN flbls.treatment_codes IS NOT NULL
                  THEN flbls.treatment_label_tg_style
                WHEN flbls.genotype_tg_style IS NOT NULL
                  THEN flbls.genotype_tg_style
                ELSE 'background only'
              END AS treatment_or_genotype_tg_style,
              CASE
                WHEN flbls.treatment_codes IS NOT NULL AND flbls.genotype_fluortag_style IS NOT NULL
                  THEN flbls.treatment_label_fluortag_style || ' > ' || flbls.genotype_fluortag_style
                WHEN flbls.treatment_codes IS NOT NULL
                  THEN flbls.treatment_label_fluortag_style
                WHEN flbls.genotype_fluortag_style IS NOT NULL
                  THEN flbls.genotype_fluortag_style
                ELSE 'background only'
              END AS treatment_or_genotype_fluortag_style,
              CASE
                WHEN flbls.treatment_codes IS NOT NULL AND flbls.genotype_fluororganelle_style IS NOT NULL
                  THEN flbls.treatment_label_fluororganelle_style || ' > ' || flbls.genotype_fluororganelle_style
                WHEN flbls.treatment_codes IS NOT NULL
                  THEN flbls.treatment_label_fluororganelle_style
                WHEN flbls.genotype_fluororganelle_style IS NOT NULL
                  THEN flbls.genotype_fluororganelle_style
                ELSE 'background only'
              END AS treatment_or_genotype_fluororganelle_style
            FROM public.tanks t
            JOIN public.fish_instances_v10 fi
              ON fi.id = t.fish_instance_id
            LEFT JOIN public.v11_fish_instance_star fis
              ON fis.fish_instance_id = fi.id
            LEFT JOIN public.v11_fish_allele_rollups fa
              ON fa.fish_instance_id = fi.id
            LEFT JOIN public.v11_fish_marker_rollups mr
              ON mr.fish_instance_id = fi.id
            LEFT JOIN public.v11_fish_instance_star_labels flbls
              ON flbls.fish_instance_id = fi.id
            WHERE fis.fish_code = ANY(:codes)
            ORDER BY fis.birthday DESC NULLS LAST, t.tank_code
            """
        ).bindparams(bindparam("codes", type_=ARRAY(TEXT())))
    )

    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": fish_codes})

    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")

    # assign Tank 1 / Tank 2 / ... per (nickname, dob) group
    if not df.empty:
        df["dob_key"] = df["dob"].astype("string")
        df["group_key"] = df["nickname"].astype("string") + "|" + df["dob_key"]
        df["tank_index"] = df.groupby("group_key").cumcount() + 1
    else:
        df["tank_index"] = []

    return df


# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    q = c1.text_input(
        "Search fish (code / nickname / background / stage / genotype)",
        "",
    )
    limit = int(
        c2.number_input("Limit", min_value=10, max_value=3000, value=500, step=50)
    )
    st.form_submit_button("Apply", use_container_width=True)

# ── Step 1 — select fish ─────────────────────────────────────────────────────
fish_df = _load_fish(q, limit)
st.caption(f"{len(fish_df)} fish")

st.subheader("1) Select fish")
f_sel_col = "✓ Select fish"
fish_view = fish_df.copy()
if f_sel_col not in fish_view.columns:
    fish_view.insert(0, f_sel_col, False)

fish_picker = st.data_editor(
    fish_view[
        [
            f_sel_col,
            "fish_code",
            "nickname",
            "genetic_background",
            "line_building_stage",
            "dob",
            "genotype_pretty",
            "organelle_fluor",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        f_sel_col: st.column_config.CheckboxColumn("✓", default=False),
        "fish_code": st.column_config.TextColumn("Fish", disabled=True),
        "nickname": st.column_config.TextColumn("Nickname", disabled=True),
        "genetic_background": st.column_config.TextColumn(
            "Background", disabled=True
        ),
        "line_building_stage": st.column_config.TextColumn(
            "Stage", disabled=True
        ),
        "dob": st.column_config.DateColumn("DOB", disabled=True),
        "genotype_pretty": st.column_config.TextColumn(
            "Genotype", disabled=True, width="large"
        ),
        "organelle_fluor": st.column_config.TextColumn(
            "Organelle-fluor", disabled=True, width="large"
        ),
    },
    key="fish_picker_editor_v11",
)
fmask = (
    fish_picker.get(f_sel_col, pd.Series(False, index=fish_picker.index))
    .fillna(False)
    .astype(bool)
)
chosen_fish = fish_df.loc[fmask].reset_index(drop=True)
st.caption(f"Selected fish: {len(chosen_fish)}")

if chosen_fish.empty:
    st.stop()

# ── Step 2 — select tanks for chosen fish ────────────────────────────────────
st.subheader("2) Select tank(s) for selected fish")
codes = chosen_fish["fish_code"].astype(str).tolist()
tanks_df = _load_tanks_for_fish(codes)

if tanks_df.empty:
    st.info("No tanks for the selected fish.")
    st.stop()

t_sel_col = "✓ Select tank"
t_view = tanks_df.copy()
if t_sel_col not in t_view.columns:
    t_view.insert(0, t_sel_col, False)

tank_picker = st.data_editor(
    t_view[
        [
            t_sel_col,
            "tank_code",
            "nickname",
            "allele_labels",
            "organelle_fluor",
            "line_building_stage",
            "dob",
            "treatment_or_genotype_tg_style",
            "treatment_or_genotype_fluortag_style",
            "treatment_or_genotype_fluororganelle_style",
            "tank_index",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        t_sel_col: st.column_config.CheckboxColumn("✓", default=False),
        "tank_code": st.column_config.TextColumn("Tank code", disabled=True),
        "nickname": st.column_config.TextColumn("Nickname", disabled=True),
        "allele_labels": st.column_config.TextColumn(
            "Tg(base)alleles", disabled=True, width="large"
        ),
        "organelle_fluor": st.column_config.TextColumn(
            "Organelle-fluor", disabled=True, width="large"
        ),
        "line_building_stage": st.column_config.TextColumn(
            "Stage", disabled=True
        ),
        "dob": st.column_config.DateColumn("DOB", disabled=True),
        "treatment_or_genotype_tg_style": st.column_config.TextColumn(
            "T/G (tg-style)", disabled=True, width="large"
        ),
        "treatment_or_genotype_fluortag_style": st.column_config.TextColumn(
            "T/G (tag-style)", disabled=True, width="large"
        ),
        "treatment_or_genotype_fluororganelle_style": st.column_config.TextColumn(
            "T/G (org-style)", disabled=True, width="large"
        ),
        "tank_index": st.column_config.NumberColumn(
            "Tank # (per nickname+DOB)", disabled=True
        ),
    },
    key="tank_picker_editor_v11",
)
tmask = (
    tank_picker.get(t_sel_col, pd.Series(False, index=tank_picker.index))
    .fillna(False)
    .astype(bool)
)
chosen_tanks = tanks_df.loc[tmask].reset_index(drop=True)
st.caption(f"Selected tanks: {len(chosen_tanks)}")

if chosen_tanks.empty:
    st.stop()

# ── Step 3 — Label preview (vertical tables) ─────────────────────────────────
st.subheader("3) Label preview (vertical tables)")

n = len(chosen_tanks)
page = 1
if n > 1:
    page = st.number_input("Label page", min_value=1, max_value=n, value=1, step=1)
idx = int(page) - 1
row = chosen_tanks.iloc[idx].to_dict()

raw_stage = row.get("line_building_stage") or ""
dob_str = _safe(row.get("dob"))
dob_label = f"DOB:{dob_str}" if dob_str else ""
tank_idx = row.get("tank_index")
tank_idx_label = f"Tank {int(tank_idx)}" if tank_idx else ""
stage_line = " ".join(x for x in [tank_idx_label, raw_stage] if x)

def _strip_arrow(x: str) -> str:
    return (x or "").lstrip("> ").strip()

tg_style = _strip_arrow(row.get("treatment_or_genotype_tg_style") or "")
tag_style = _strip_arrow(row.get("treatment_or_genotype_fluortag_style") or "")
org_style = _strip_arrow(row.get("treatment_or_genotype_fluororganelle_style") or "")

_vert_table(
    f"TANK {row.get('tank_code','')}",
    [
        ("Tank code", row.get("tank_code", "")),
        ("Nickname", row.get("nickname", "")),
        ("T/G (tg-style)", tg_style),
        ("T/G (tag-style)", tag_style),
        ("T/G (org-style)", org_style),
        ("Stage", stage_line),
        ("DOB", dob_label),
    ],
)

# ── Step 4 — Download / print tank labels ────────────────────────────────────
st.subheader("4) Download / print tank labels")

label_rows: List[Dict] = []
for r in chosen_tanks.to_dict(orient="records"):
    raw_stage = r.get("line_building_stage") or ""
    dob_str = _safe(r.get("dob"))
    dob_label = f"DOB:{dob_str}" if dob_str else ""
    tank_idx = r.get("tank_index")
    tank_idx_label = f"Tank {int(tank_idx)}" if tank_idx else ""
    stage_line = " ".join(x for x in [tank_idx_label, raw_stage] if x)

    nickname = r.get("nickname") or ""

    tg_style = _strip_arrow(r.get("treatment_or_genotype_tg_style") or "")
    tag_style = _strip_arrow(r.get("treatment_or_genotype_fluortag_style") or "")
    org_style = _strip_arrow(r.get("treatment_or_genotype_fluororganelle_style") or "")

    label_rows.append(
        {
            "label": r.get("tank_code"),
            "tank_code": r.get("tank_code"),
            "nickname": nickname,
            # three explicit styles for the PDF builder
            "tg_style": tg_style,
            "tag_style": tag_style,
            "org_style": org_style,
            # stage / DOB for the bottom two lines
            "line_building_stage": stage_line,
            "stage": stage_line,
            "dob": dob_label,
            # these can stay blank for now
            "genetic_background": "",
            "tank_display": "",
            "fusions": "",
        }
    )

if HAVE_PRINT_HELPER:
    download_button_for_labels(
        rows=label_rows,
        builder="tank",
        file_prefix="tank_labels_v11",
        button_text="⬇️ Download tank labels (PDF)",
    )
    download_button_for_labels(
        rows=label_rows,
        builder="tank",
        file_prefix="tank_labels_v11",
        button_text="🖨️ Print tank labels to lab printer",
    )
else:
    st.button("⬇️ Download tank labels (PDF)", disabled=True)
    st.button("🖨️ Print tank labels to lab printer", disabled=True)