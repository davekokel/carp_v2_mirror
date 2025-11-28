# carp_app/ui/pages/028_🖨️_print_cross_and_clutch_labels.py
# 🖨️ Cross & Clutch labels (v11) — genotype-focused clutch labels

from __future__ import annotations

import os, sys, pathlib
from typing import List, Dict, Tuple, Optional
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

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
    page_title="CARP — 🖨️ Cross & Clutch labels (v11)",
    page_icon="🖨️",
    layout="wide",
)
st.title("🖨️ Cross & Clutch labels (v11)")

# ── engine cache ─────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        st.error("DB_URL not set")
        st.stop()
    return _engine()

# ── tiny utils ───────────────────────────────────────────────────────────────
def _vert_table(title: str, rows: List[Tuple[str, str]]):
    t = pd.DataFrame(rows, columns=["Field", "Value"])
    t["Field"] = t["Field"].astype("string")
    t["Value"] = t["Value"].astype("string").fillna("")
    st.markdown(f"**{title}**")
    st.dataframe(t, hide_index=True, use_container_width=True)

def _dedup_rollup(*parts: List[str]) -> str:
    toks: List[str] = []
    for s in parts:
        if not s:
            continue
        toks.extend([t.strip() for t in str(s).split(",") if t.strip()])
    return ", ".join(sorted(set(toks), key=str.lower))

# ── dynamic tank_pairs columns (mother/father) ───────────────────────────────
@st.cache_data(show_spinner=False)
def _parent_cols() -> Tuple[str, str]:
    sql = text(
        """
      SELECT column_name FROM information_schema.columns
      WHERE table_schema='public' AND table_name='tank_pairs'
    """
    )
    with _eng().begin() as cx:
        cols = pd.read_sql(sql, cx)["column_name"].tolist()
    for a, b in (("mother_tank_id", "father_tank_id"), ("tank_id_mother", "tank_id_father")):
        if a in cols and b in cols:
            return a, b
    return "mother_tank_id", "father_tank_id"

# ── loaders: crosses (v11 fish star + v11_line_allele_rollups) ───────────────
def _load_crosses_v11(
    q: Optional[str], d_from: Optional[date], d_to: Optional[date], limit: int
) -> pd.DataFrame:
    """
    Cross rows with mom/dad tanks + v11 fish fields + per-line allele rollups:

      - mom/dad genotype_pretty (for display / search)
      - mom/dad allele_canonical_rollup  (Tg(base)allele_name)
      - mom/dad allele_nickname_rollup   (Tg(base)nickname_or_name)
      - mom/dad all_organelle_fluor_rollup
    """
    mom_col, dad_col = _parent_cols()
    sql = text(
        f"""
      WITH fis AS (
        SELECT
          fish_instance_id,
          fish_code,
          line_id,
          genotype_pretty,
          genotype_basecode_code,
          genotype_transgene_allele_code,
          all_fluor_tag_rollup,
          all_organelle_fluor_rollup
        FROM public.v11_fish_instance_star
      )
      SELECT
        cr.id::uuid::text         AS cross_id,
        COALESCE(cr.cross_run_code, tp.tank_pair_code || ' @ ' || cr.created_at::date::text)
                                   AS cross_code,
        cr.created_at::date       AS cross_date,
        tp.tank_pair_code         AS tank_pair_code,

        tm.tank_code              AS mom_tank_code,
        tf.tank_code              AS dad_tank_code,

        COALESCE(fm.genotype_pretty,'')                AS mom_genotype_pretty,
        COALESCE(ff.genotype_pretty,'')                AS dad_genotype_pretty,

        COALESCE(lm.allele_canonical_rollup,'')        AS mom_allele_canonical,
        COALESCE(lf.allele_canonical_rollup,'')        AS dad_allele_canonical,

        COALESCE(lm.allele_nickname_rollup,'')         AS mom_allele_nicknames,
        COALESCE(lf.allele_nickname_rollup,'')         AS dad_allele_nicknames,

        COALESCE(fm.all_organelle_fluor_rollup,'')     AS mom_organelle_fluor_rollup,
        COALESCE(ff.all_organelle_fluor_rollup,'')     AS dad_organelle_fluor_rollup

      FROM public.crosses cr
      LEFT JOIN public.tank_pairs tp ON tp.id = cr.tank_pair_id

      LEFT JOIN public.tanks tm ON tm.id = tp.{mom_col}
      LEFT JOIN public.tanks tf ON tf.id = tp.{dad_col}

      LEFT JOIN public.fish_instances_v10 fim ON fim.id = tm.fish_instance_id
      LEFT JOIN public.fish_instances_v10 fif ON fif.id = tf.fish_instance_id

      LEFT JOIN fis fm ON fm.fish_instance_id = fim.id
      LEFT JOIN fis ff ON ff.fish_instance_id = fif.id

      LEFT JOIN public.v11_line_allele_rollups lm ON lm.line_id = fim.line_id
      LEFT JOIN public.v11_line_allele_rollups lf ON lf.line_id = fif.line_id

      WHERE (:d1 IS NULL OR cr.created_at::date >= :d1)
        AND (:d2 IS NULL OR cr.created_at::date <= :d2)
        AND (
          :q IS NULL OR
          COALESCE(cr.cross_run_code,'')        ILIKE :ql OR
          tp.tank_pair_code                     ILIKE :ql OR
          COALESCE(tm.tank_code,'')             ILIKE :ql OR
          COALESCE(tf.tank_code,'')             ILIKE :ql OR
          COALESCE(fm.genotype_pretty,'')       ILIKE :ql OR
          COALESCE(ff.genotype_pretty,'')       ILIKE :ql
        )
      ORDER BY cr.created_at DESC NULLS LAST, cr.cross_run_code
      LIMIT :lim
    """
    )

    qnorm = (q or "").strip()
    params = {
        "q": (qnorm if qnorm else None),
        "ql": f"%{qnorm}%",
        "d1": (str(d_from) if d_from else None),
        "d2": (str(d_to) if d_to else None),
        "lim": int(limit),
    }

    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    for c in df.select_dtypes("object").columns:
        df[c] = df[c].astype("string").fillna("")

    return df

# ── loaders: clutches for selected crosses (v11_clutch_star) ─────────────────
def _load_clutches_for_crosses(cross_ids: List[str]) -> pd.DataFrame:
    """
    Clutches for the selected crosses, genotype-only (no treatment filter).
    """
    if not cross_ids:
        return pd.DataFrame(
            columns=[
                "clutch_id",
                "clutch_code",
                "clutch_date",
                "genotype_pretty",
                "genotype_basecode_code",
                "genotype_transgene_allele_code",
                "treat_codes",
                "all_fluor_tag_rollup",
                "all_organelle_fluor_rollup",
                "cross_id",
            ]
        )

    sql = text(
        """
      WITH picked AS (
        SELECT unnest(:ids)::uuid AS cross_id
      )
      SELECT
        c.id::text                    AS clutch_id,
        COALESCE(c.clutch_code,'')    AS clutch_code,
        c.clutch_date                 AS clutch_date,
        COALESCE(s.genotype_pretty,'')           AS genotype_pretty,
        COALESCE(s.genotype_basecode_code,'')    AS genotype_basecode_code,
        COALESCE(s.genotype_transgene_allele_code,'') AS genotype_transgene_allele_code,
        COALESCE(s.treat_codes,'')               AS treat_codes,
        COALESCE(s.all_fluor_tag_rollup,'')      AS all_fluor_tag_rollup,
        COALESCE(s.all_organelle_fluor_rollup,'') AS all_organelle_fluor_rollup,
        c.cross_id::text               AS cross_id
      FROM public.clutches c
      JOIN picked p ON p.cross_id = c.cross_id
      LEFT JOIN public.v11_clutch_star s
             ON s.clutch_id = c.id::text
      ORDER BY c.clutch_date DESC NULLS LAST, c.clutch_code
    """
    )

    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"ids": cross_ids})

    for c in df.select_dtypes("object").columns:
        df[c] = df[c].astype("string").fillna("")

    return df

# ── filters ──────────────────────────────────────────────────────────────────
with st.form("filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([2, 1, 1])
    q = c1.text_input("Search crosses (code / TP / parent genotypes)", "")
    d_from = c2.date_input("From", value=None)
    d_to = c3.date_input("To", value=None)
    limit = int(st.number_input("Limit", min_value=10, max_value=3000, value=500, step=50))
    st.form_submit_button("Apply", use_container_width=True)

# ── Step 1: select crosses ───────────────────────────────────────────────────
df_cross = _load_crosses_v11(q, d_from, d_to, limit)
st.caption(f"{len(df_cross)} cross(es)")

st.subheader("1) Select cross(es)")
cx_sel = "✓ Select"
cx_view = df_cross.copy()
if cx_sel not in cx_view.columns:
    cx_view.insert(0, cx_sel, False)

cx_picker = st.data_editor(
    cx_view[
        [
            cx_sel,
            "cross_code",
            "cross_date",
            "tank_pair_code",
            "mom_tank_code",
            "dad_tank_code",
            "mom_genotype_pretty",
            "dad_genotype_pretty",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        cx_sel:                 st.column_config.CheckboxColumn("✓", default=False),
        "cross_code":           st.column_config.TextColumn("Cross code", disabled=True),
        "cross_date":           st.column_config.DateColumn("Date", disabled=True),
        "tank_pair_code":       st.column_config.TextColumn("Tank pair", disabled=True),
        "mom_tank_code":        st.column_config.TextColumn("Mother tank", disabled=True),
        "dad_tank_code":        st.column_config.TextColumn("Father tank", disabled=True),
        "mom_genotype_pretty":  st.column_config.TextColumn("Mom genotype", disabled=True, width="large"),
        "dad_genotype_pretty":  st.column_config.TextColumn("Dad genotype", disabled=True, width="large"),
    },
    key="cross_picker_editor_v11",
)
cx_mask = cx_picker.get(cx_sel, pd.Series(False, index=cx_picker.index)).fillna(False).astype(bool)
chosen_crosses = df_cross.loc[cx_mask].reset_index(drop=True)
st.caption(f"Selected: {len(chosen_crosses)} cross(es)")
if chosen_crosses.empty:
    st.stop()

# ── Step 2: select clutches for selected crosses (genotype-only) ─────────────
st.subheader("2) Select clutches for labels")

cross_ids = chosen_crosses["cross_id"].astype(str).tolist()
df_clutch = _load_clutches_for_crosses(cross_ids)
st.caption(f"{len(df_clutch)} clutch(es) for selected cross(es)")

cl_sel = "✓ Select"
cl_view = df_clutch.copy()
if cl_sel not in cl_view.columns:
    cl_view.insert(0, cl_sel, False)

cl_picker = st.data_editor(
    cl_view[
        [
            cl_sel,
            "clutch_code",
            "clutch_date",
            "genotype_pretty",
            "genotype_basecode_code",
            "genotype_transgene_allele_code",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        cl_sel:                    st.column_config.CheckboxColumn("✓", default=False),
        "clutch_code":             st.column_config.TextColumn("Clutch code", disabled=True),
        "clutch_date":             st.column_config.DateColumn("DOB", disabled=True),
        "genotype_pretty":         st.column_config.TextColumn("Genotype (pretty)", disabled=True, width="large"),
        "genotype_basecode_code":  st.column_config.TextColumn("Genotype basecodes", disabled=True, width="large"),
        "genotype_transgene_allele_code": st.column_config.TextColumn("Genotype allele code", disabled=True, width="large"),
    },
    key="clutch_picker_editor_v11",
)

cl_mask = cl_picker.get(cl_sel, pd.Series(False, index=cl_picker.index)).fillna(False).astype(bool)
chosen_clutches = df_clutch.loc[cl_mask].reset_index(drop=True)
st.caption(f"Selected: {len(chosen_clutches)} clutch(es)")

# ── Step 3: label preview ────────────────────────────────────────────────────
st.subheader("3) Label preview")

n_cross = len(chosen_crosses)
page = 1
if n_cross > 1:
    page = st.number_input(
        "Preview page (per cross)",
        min_value=1,
        max_value=n_cross,
        value=1,
        step=1,
    )
idx = int(page) - 1
cx_row = chosen_crosses.iloc[idx].to_dict()

# CROSS preview — allele_nicknames + organelle-fluor (mom × dad)
allele_nick_row = (
    f"{cx_row.get('mom_allele_nicknames','')} × {cx_row.get('dad_allele_nicknames','')}".strip()
)
org_row = (
    f"{cx_row.get('mom_organelle_fluor_rollup','')} × {cx_row.get('dad_organelle_fluor_rollup','')}".strip()
)

cross_rows_preview: List[Tuple[str, str]] = [
    ("Cross code",  cx_row.get("cross_code", "")),
    ("Cross date",  str(cx_row.get("cross_date") or "")),
    ("Mother tank", cx_row.get("mom_tank_code", "")),
    ("Father tank", cx_row.get("dad_tank_code", "")),
    ("Allele nicknames",  allele_nick_row),
    ("Organelle-fluor",   org_row),
]

_vert_table(f"CROSS {cx_row.get('cross_code','')}", cross_rows_preview)

# CLUTCH preview for this cross (genotype-only; canonical + organelle)
if not chosen_clutches.empty:
    cl_for_cross = chosen_clutches[chosen_clutches["cross_id"] == cx_row["cross_id"]]
else:
    cl_for_cross = pd.DataFrame()

if cl_for_cross.empty:
    st.info("No selected clutches for this cross (choose some in Step 2 to preview clutch labels).")
else:
    tr = cl_for_cross.iloc[0].to_dict()
    # canonical line for clutch = mom_allele_canonical; dad_allele_canonical
    canonical_line = "; ".join(
        [x for x in [cx_row.get("mom_allele_canonical",""), cx_row.get("dad_allele_canonical","")] if x]
    )
    # organelle line for clutch = mom_organelle_fluor_rollup; dad_organelle_fluor_rollup
    clutch_org_line = "; ".join(
        [x for x in [cx_row.get("mom_organelle_fluor_rollup",""), cx_row.get("dad_organelle_fluor_rollup","")] if x]
    )

    clutch_rows_preview: List[Tuple[str, str]] = [
        ("Clutch code",      tr.get("clutch_code", "")),
        ("DOB",              tr.get("clutch_date", "")),
        ("Line 1",           f"{cx_row.get('cross_code','')} @ {cx_row.get('cross_date','')}"),
        ("Line 2 (canonical)", canonical_line),
        ("Line 3 (organelle)", clutch_org_line),
    ]
    _vert_table(f"CLUTCH {tr.get('clutch_code','')}", clutch_rows_preview)

# ── Step 4: download / print labels for ALL selected ─────────────────────────
st.subheader("4) Download / print labels for selected")

# CROSS label rows — mapped onto labels_components.crossing
cross_rows: List[Dict] = []
for r in chosen_crosses.to_dict(orient="records"):
    # cross_code on label includes date
    cross_code_label = f"{r.get('cross_code','')} @ {r.get('cross_date','')}"

    allele_nick_row  = f"{r.get('mom_allele_nicknames','')} × {r.get('dad_allele_nicknames','')}".strip()
    org_row          = f"{r.get('mom_organelle_fluor_rollup','')} × {r.get('dad_organelle_fluor_rollup','')}".strip()

    # arrow to clutch: pick any selected clutch for this cross
    if not chosen_clutches.empty:
        cl_for_cross = chosen_clutches[chosen_clutches["cross_id"] == r["cross_id"]]
    else:
        cl_for_cross = pd.DataFrame()
    clutch_label = ""
    clutch_fluors = ""
    if not cl_for_cross.empty:
        c0 = cl_for_cross.iloc[0].to_dict()
        clutch_label = c0.get("clutch_code", "")
        # clutch_fluors intentionally left blank at cross-setup time

    cross_rows.append(
        {
            "cross_code":       cross_code_label,
            "mother_tank_code": r.get("mom_tank_code"),
            "father_tank_code": r.get("dad_tank_code"),
            # put allele nicknames into the mom/dad genotype slots
            "mom_genotype":     r.get("mom_allele_nicknames"),
            "dad_genotype":     r.get("dad_allele_nicknames"),
            # use "fusions" line for organelle-fluor rollup
            "fusions":          org_row,
            "clutch_label":     clutch_label,
            "clutch_fluors":    clutch_fluors,
        }
    )

# CLUTCH (petri) label rows — 3 lines:
#  line1: cross_code @ date
#  line2: canonical alleles (mom; dad)
#  line3: organelle-fluor (mom; dad)
petri_rows: List[Dict] = []
for r in chosen_clutches.to_dict(orient="records"):
    # find the cross row for this clutch
    cross = chosen_crosses[chosen_crosses["cross_id"] == r["cross_id"]]
    if cross.empty:
        continue
    cx = cross.iloc[0].to_dict()

    # line 1: CR-… @ date
    cross_line = f"{cx.get('cross_code','')} @ {cx.get('cross_date','')}"

    # line 2: canonical alleles as mom; dad
    canonical_line = "; ".join(
        [x for x in [cx.get("mom_allele_canonical",""), cx.get("dad_allele_canonical","")] if x]
    )

    # line 3: organelle fluor as mom; dad
    clutch_org_line = "; ".join(
        [x for x in [cx.get("mom_organelle_fluor_rollup",""), cx.get("dad_organelle_fluor_rollup","")] if x]
    )

    petri_rows.append(
        {
            "clutch_instance_code": cross_line,        # label line 1
            "clutch_name":          "",               # unused
            "mom_code":             "",               # unused
            "dad_code":             "",               # unused
            "clutch_genotype":      canonical_line,   # label line 2
            "date_birth":           str(r.get("clutch_date") or ""),
            "tx_codes":             "",               # unused for cross-time labels
            "tx_fluors":            clutch_org_line,  # label line 3
        }
    )

c1, c2 = st.columns(2)
with c1:
    if HAVE_PRINT_HELPER:
        download_button_for_labels(
            rows=cross_rows,
            builder="crossing",
            file_prefix="cross_labels_v11",
            button_text="🖨️ Print / Download CROSS labels (ALL selected)",
        )
    else:
        st.button("🖨️ Print / Download CROSS labels (ALL selected)", disabled=True)

with c2:
    if HAVE_PRINT_HELPER:
        download_button_for_labels(
            rows=petri_rows,
            builder="petri",
            file_prefix="clutch_labels_v11",
            button_text="🖨️ Print / Download CLUTCH labels (ALL selected)",
        )
    else:
        st.button("🖨️ Print / Download CLUTCH labels (ALL selected)", disabled=True)