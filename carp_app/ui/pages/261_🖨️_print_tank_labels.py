# carp_app/ui/pages/260_🖨️_print_tank_labels.py
from __future__ import annotations

import os, sys, pathlib, re
from typing import List, Dict, Tuple
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

# ── genotype → fusions helpers ───────────────────────────────────────────────
_BASE_ONLY_RE = re.compile(r"\b(?:p[A-Za-z]{2,}\d{2,}|[A-Z]{2,}-\d{1,})\b")

def _bases_from_genotype(geno: str) -> List[str]:
    if not geno:
        return []
    return sorted(set(_BASE_ONLY_RE.findall(str(geno))))

@st.cache_data(show_spinner=False)
def _fusion_names_for_bases(bases: List[str]) -> str:
    if not bases:
        return ""
    sql = text("""
      WITH b AS (SELECT unnest(:codes) AS base_code)
      SELECT COALESCE(string_agg(DISTINCT f.fusion_name, ', ' ORDER BY f.fusion_name), '') AS fus
      FROM b
      JOIN public.plasmids p               ON p.code = b.base_code
      LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
      LEFT JOIN public.fusions f                ON f.id = jpf.fusion_id
    """).bindparams(bindparam("codes", type_=ARRAY(TEXT())))
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": bases})
    return (df["fus"].iloc[0] or "") if not df.empty else ""

# ── data loaders ─────────────────────────────────────────────────────────────
def _load_fish(q: str | None, limit: int) -> pd.DataFrame:
    """
    Fish registry with nickname, DOB, background, stage, and collapsed genotype.
    (One row per fish_code.)
    """
    sql = text("""
      WITH vm AS (
        SELECT vm.fish_code,
               MAX(vm.genotype_pretty) AS genotype_pretty
        FROM public.v_fish_main vm
        GROUP BY vm.fish_code
      )
      SELECT
        f.fish_code::text                 AS fish_code,
        COALESCE(f.nickname,'')          AS nickname,
        f.dob                             AS dob,
        COALESCE(f.genetic_background,'') AS genetic_background,
        COALESCE(f.line_building_stage,'') AS line_building_stage,
        COALESCE(vm.genotype_pretty,'')   AS genotype_pretty
      FROM public.fish f
      LEFT JOIN vm ON vm.fish_code = f.fish_code
      WHERE (:q IS NULL)
         OR f.fish_code ILIKE :ql
         OR COALESCE(f.nickname,'') ILIKE :ql
         OR COALESCE(f.genetic_background,'') ILIKE :ql
         OR COALESCE(f.line_building_stage,'') ILIKE :ql
         OR COALESCE(vm.genotype_pretty,'') ILIKE :ql
      ORDER BY f.created_at DESC NULLS LAST, f.fish_code
      LIMIT :lim
    """)
    params = {"q": (q if (q or "").strip() else None), "ql": f"%{(q or '').strip()}%", "lim": int(limit)}
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _load_tanks_for_fish(fish_codes: List[str]) -> pd.DataFrame:
    """
    Tanks for the selected fish, plus fish metadata to preview labels.
    """
    if not fish_codes:
        return pd.DataFrame(columns=["tank_code","fish_code","nickname","dob","genetic_background","line_building_stage","genotype_pretty"])
    sql = text("""
      WITH picked AS (SELECT unnest(:codes) AS fish_code),
           vm AS (
             SELECT vm.fish_code, MAX(vm.genotype_pretty) AS genotype_pretty
             FROM public.v_fish_main vm
             GROUP BY vm.fish_code
           )
      SELECT
        vt.tank_code::text                    AS tank_code,
        vt.fish_code::text                    AS fish_code,
        COALESCE(f.nickname,'')               AS nickname,
        f.dob                                  AS dob,
        COALESCE(f.genetic_background,'')     AS genetic_background,
        COALESCE(f.line_building_stage,'')    AS line_building_stage,
        COALESCE(vm.genotype_pretty,'')       AS genotype_pretty
      FROM public.v_tanks vt
      JOIN picked p           ON p.fish_code = vt.fish_code
      LEFT JOIN public.fish f ON f.fish_code = vt.fish_code
      LEFT JOIN vm            ON vm.fish_code = vt.fish_code
      ORDER BY vt.created_at DESC NULLS LAST, vt.tank_code
    """).bindparams(bindparam("codes", type_=ARRAY(TEXT())))
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": fish_codes})
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _vert_table(title: str, kv_pairs: List[Tuple[str, str]]):
    tbl = pd.DataFrame(kv_pairs, columns=["Field", "Value"])
    tbl["Field"] = tbl["Field"].astype("string")
    tbl["Value"] = tbl["Value"].astype("string").fillna("")
    st.markdown(f"**{title}**")
    st.dataframe(tbl, hide_index=True, use_container_width=True)

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
    fish_view[[f_sel_col, "fish_code", "nickname", "genetic_background", "line_building_stage", "dob", "genotype_pretty"]],
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
    },
    key="fish_picker_editor_v2",
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
    t_view[[t_sel_col, "tank_code", "fish_code", "nickname", "genotype_pretty"]],
    hide_index=True,
    use_container_width=True,
    column_config={
        t_sel_col:               st.column_config.CheckboxColumn("✓", default=False),
        "tank_code":             st.column_config.TextColumn("Tank", disabled=True),
        "fish_code":             st.column_config.TextColumn("Fish", disabled=True),
        "nickname":              st.column_config.TextColumn("Nickname", disabled=True),
        "genotype_pretty":       st.column_config.TextColumn("Genotype", disabled=True, width="large"),
    },
    key="tank_picker_editor_v5",
)
tmask = tank_picker.get(t_sel_col, pd.Series(False, index=tank_picker.index)).fillna(False).astype(bool)
chosen_tanks = tanks_df.loc[tmask].reset_index(drop=True)
st.caption(f"Selected tanks: {len(chosen_tanks)}")

if chosen_tanks.empty:
    st.stop()

# ── Step 3 — label preview (vertical tables; add Fusions; paginate) ──────────
st.subheader("3) Label preview (vertical tables)")

# pagination control — one tank preview per page
n = len(chosen_tanks)
page = 1
if n > 1:
    page = st.number_input("Label page", min_value=1, max_value=n, value=1, step=1)
idx = int(page) - 1
row = chosen_tanks.iloc[idx].to_dict()

# compute fusions from genotype
bases = _bases_from_genotype(row.get("genotype_pretty",""))
fusions = _fusion_names_for_bases(bases)

_vert_table(
    f"TANK {row.get('tank_code','')}",
    [
        ("Tank code",           row.get("tank_code","")),
        ("Fish code",           row.get("fish_code","")),
        ("Nickname",            row.get("nickname","")),
        ("Genetic background",  row.get("genetic_background","")),
        ("Line-building stage", row.get("line_building_stage","")),
        ("DOB",                 str(row.get("dob") or "")),
        ("Genotype",            row.get("genotype_pretty","")),
        ("Fusions",             fusions),
    ]
)

# ── Step 4 — Download PDF ────────────────────────────────────────────────────
st.subheader("4) Download PDF")

label_rows: List[Dict] = []
for r in chosen_tanks.to_dict(orient="records"):
    label_rows.append({
        "tank_code":           r.get("tank_code"),
        "fish_code":           r.get("fish_code"),
        "nickname":            r.get("nickname") or "",
        "genetic_background":  r.get("genetic_background") or "",
        "line_building_stage": r.get("line_building_stage") or "",
        "dob":                 r.get("dob"),
        "genotype":            r.get("genotype_pretty") or "",
        "fusions":             _fusion_names_for_bases(_bases_from_genotype(r.get("genotype_pretty",""))),
    })

if HAVE_PRINT_HELPER:
    download_button_for_labels(
        rows=label_rows,
        builder="tank",
        file_prefix="tank_labels",
        button_text="⬇️ Download tank labels (PDF)",
    )
else:
    st.button("⬇️ Download tank labels (PDF)", disabled=True)

# ── Step 5 — Print labels ────────────────────────────────────────────────────
st.subheader("5) Print labels")
if HAVE_PRINT_HELPER:
    download_button_for_labels(
        rows=label_rows,
        builder="tank",
        file_prefix="tank_labels",
        button_text="🖨️ Print tank labels to lab printer",
    )
else:
    st.button("🖨️ Print tank labels to lab printer", disabled=True)