# carp_app/ui/pages/260_🖨️_print_tank_labels.py
# 🖨️ Print tank labels (v11) — tank_code, allele_label, organelle-fluor, stage + DOB

from __future__ import annotations

import os, sys, pathlib
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

st.set_page_config(page_title="CARP — 🖨️ Print tank labels", page_icon="🖨️", layout="wide")
st.title("🖨️ Print tank labels")

# ── engine cache ─────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        st.error("DB_URL not set"); st.stop()
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
    """
    Fish registry for selection: one row per *fish* (true fish_code),
    via v11_fish_instance_star + fish_instances_v10 + fish_lines.
    """
    sql = text("""
      WITH fis AS (
        SELECT
          fish_instance_id,
          fish_code,
          line_id,
          birthday,
          genetic_background,
          line_building_stage,
          genotype_pretty,
          all_organelle_fluor_rollup
        FROM public.v11_fish_instance_star
      )
      SELECT
        COALESCE(fi.fish_code, fis.fish_code)::text AS fish_code,
        COALESCE(fl.nickname, '')                  AS nickname,
        fis.birthday                               AS dob,
        COALESCE(fl.genetic_background,
                 fis.genetic_background, '')       AS genetic_background,
        COALESCE(fl.line_building_stage,
                 fis.line_building_stage, '')      AS line_building_stage,
        COALESCE(fis.genotype_pretty, '')          AS genotype_pretty,
        COALESCE(fis.all_organelle_fluor_rollup,'') AS organelle_fluor
      FROM fis
      LEFT JOIN public.fish_instances_v10 fi ON fi.id = fis.fish_instance_id
      LEFT JOIN public.fish_lines fl ON fl.id = fis.line_id
      WHERE (:q IS NULL)
         OR COALESCE(fi.fish_code, fis.fish_code) ILIKE :ql
         OR COALESCE(fl.nickname,'')           ILIKE :ql
         OR COALESCE(fl.genetic_background,'') ILIKE :ql
         OR COALESCE(fl.line_building_stage,'')ILIKE :ql
         OR COALESCE(fis.genotype_pretty,'')   ILIKE :ql
      ORDER BY fis.birthday DESC NULLS LAST, COALESCE(fi.fish_code, fis.fish_code)
      LIMIT :lim
    """)
    qnorm = (q or "").strip()
    params = {
        "q":  (qnorm if qnorm else None),
        "ql": f"%{qnorm}%",
        "lim": int(limit),
    }
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df


def _load_tanks_for_fish(fish_codes: List[str]) -> pd.DataFrame:
    """
    Tanks for the selected fish, via v11_tank_star.
    v11_tank_star must expose:
      tank_code, fish_code, allele_canonical, allele_label,
      organelle_fluor, line_building_stage, dob
    """
    if not fish_codes:
        return pd.DataFrame(columns=[
            "tank_code", "fish_code",
            "allele_canonical", "allele_label",
            "organelle_fluor",
            "line_building_stage", "dob",
        ])

    sql = text("""
      SELECT
        tank_code,
        fish_code,
        allele_canonical,
        allele_label,
        organelle_fluor,
        line_building_stage,
        dob
      FROM public.v11_tank_star
      WHERE fish_code = ANY(:codes)
      ORDER BY dob DESC NULLS LAST, tank_code
    """).bindparams(bindparam("codes", type_=ARRAY(TEXT())))

    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": fish_codes})
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters", clear_on_submit=False):
    c1, c2 = st.columns([3,1])
    q = c1.text_input("Search fish (code / nickname / background / stage / genotype)", "")
    limit = int(c2.number_input("Limit", min_value=10, max_value=3000, value=500, step=50))
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
        f_sel_col:               st.column_config.CheckboxColumn("✓", default=False),
        "fish_code":             st.column_config.TextColumn("Fish", disabled=True),
        "nickname":              st.column_config.TextColumn("Nickname", disabled=True),
        "genetic_background":    st.column_config.TextColumn("Background", disabled=True),
        "line_building_stage":   st.column_config.TextColumn("Stage", disabled=True),
        "dob":                   st.column_config.DateColumn("DOB", disabled=True),
        "genotype_pretty":       st.column_config.TextColumn("Genotype", disabled=True, width="large"),
        "organelle_fluor":       st.column_config.TextColumn("Organelle-fluor", disabled=True, width="large"),
    },
    key="fish_picker_editor_v11",
)
fmask = fish_picker.get(f_sel_col, pd.Series(False, index=fish_picker.index)).fillna(False).astype(bool)
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
            "allele_label",
            "organelle_fluor",
            "line_building_stage",
            "dob",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        t_sel_col:             st.column_config.CheckboxColumn("✓", default=False),
        "tank_code":           st.column_config.TextColumn("Tank", disabled=True),
        "allele_label":        st.column_config.TextColumn("Tg(base)label", disabled=True, width="large"),
        "organelle_fluor":     st.column_config.TextColumn("Organelle-fluor", disabled=True, width="large"),
        "line_building_stage": st.column_config.TextColumn("Stage", disabled=True),
        "dob":                 st.column_config.DateColumn("DOB", disabled=True),
    },
    key="tank_picker_editor_v11",
)
tmask = tank_picker.get(t_sel_col, pd.Series(False, index=tank_picker.index)).fillna(False).astype(bool)
chosen_tanks = tanks_df.loc[tmask].reset_index(drop=True)
st.caption(f"Selected tanks: {len(chosen_tanks)}")

if chosen_tanks.empty:
    st.stop()

# ── Step 3 — label preview (vertical tables) ─────────────────────────────────
st.subheader("3) Label preview (vertical tables)")

# pagination control — one tank preview per page
n = len(chosen_tanks)
page = 1
if n > 1:
    page = st.number_input("Label page", min_value=1, max_value=n, value=1, step=1)
idx = int(page) - 1
row = chosen_tanks.iloc[idx].to_dict()

stage_dob = " ".join(
    x for x in [row.get("line_building_stage") or "", _safe(row.get("dob"))] if x
)

_vert_table(
    f"TANK {row.get('tank_code','')}",
    [
        ("Tank code",        row.get("tank_code","")),
        ("Transgene alleles", row.get("allele_label","")),
        ("Organelle-fluor",  row.get("organelle_fluor","")),
        ("Stage + DOB",      stage_dob),
    ]
)

# ── Step 4 — Download / Print labels ─────────────────────────────────────────
st.subheader("4) Download / print tank labels")

label_rows: List[Dict] = []
for r in chosen_tanks.to_dict(orient="records"):
    stage_dob = " ".join(
        x for x in [r.get("line_building_stage") or "", _safe(r.get("dob"))] if x
    )

    label_rows.append({
        # Line 1: header / label (what prints as "line 1")
        "label":               r.get("tank_code"),
        "tank_code":           r.get("tank_code"),   # also QR payload
        # Line 2: nickname (we leave blank)
        "nickname":            "",
        # Line 3: tank_display → allele_label (canonical label)
        "tank_display":        r.get("allele_label") or "",
        # Line 4: fusions → organelle-fluor
        "fusions":             r.get("organelle_fluor") or "",
        # Line 5: genetic_background (unused)
        "genetic_background":  "",
        # Line 6: stage → "stage DOB"
        "line_building_stage": stage_dob,
        "stage":               stage_dob,
        # Line 7: dob (leave None; we already encoded it in stage_dob)
        "dob":                 None,
    })

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