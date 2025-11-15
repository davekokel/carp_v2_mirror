# carp_app/ui/pages/028_🖨️_print_cross_and_clutch_labels.py
# 🖨️ Cross & Clutch labels — select → preview (pivot tables, paginated) → download/print
from __future__ import annotations

import os, sys, pathlib, re
from typing import List, Dict, Tuple, Optional
from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import text, bindparam
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import ARRAY, UUID, TEXT

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

st.set_page_config(page_title="CARP — 🖨️ Cross & Clutch labels", page_icon="🖨️", layout="wide")
st.title("🖨️ Cross & Clutch labels")

# ── engine cache ─────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        st.error("DB_URL not set"); st.stop()
    return _engine()

# ── utils ────────────────────────────────────────────────────────────────────
_BASE_ONLY_RE = re.compile(r"\b(?:p[A-Za-z]{2,}\d{2,}|[A-Z]{2,}-\d{1,})\b")

def _bases_from_genotype(geno: str) -> List[str]:
    if not geno:
        return []
    return sorted(set(_BASE_ONLY_RE.findall(str(geno))))

@st.cache_data(show_spinner=False)
def _fluor_names_for_bases(bases: List[str]) -> str:
    """Fluor rollup from plasmid→fusions→fluors for a list of base plasmid codes."""
    if not bases:
        return ""
    sql = text("""
      WITH b AS (SELECT unnest(:codes) AS base_code)
      SELECT COALESCE(
               string_agg(
                 DISTINCT COALESCE(fl.fluor_name, fl.fluor_code),
                 ', ' ORDER BY COALESCE(fl.fluor_name, fl.fluor_code)
               ),
               ''
             ) AS fls
      FROM b
      JOIN public.plasmids p               ON p.code = b.base_code
      LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
      LEFT JOIN public.fusions f                ON f.id = jpf.fusion_id
      LEFT JOIN public.fluors  fl               ON fl.id = f.fluor_id
    """).bindparams(bindparam("codes", type_=ARRAY(TEXT())))
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": bases})
    return (df["fls"].iloc[0] or "") if not df.empty else ""

@st.cache_data(show_spinner=False)
def _fluors_for_ft_codes(codes: List[str]) -> str:
    """
    Fluor rollup for a list of codes.

    We no longer depend on ft_proteins (which does not exist in this schema).
    Instead, we treat any code that matches a fluor_code or fluor_name in public.fluors
    as a fluor and ignore non-fluor codes (plasmids, RNAs, etc.).
    """
    if not codes:
        return ""
    sql = text("""
      WITH c AS (
        SELECT unnest(:codes) AS code
      )
      SELECT COALESCE(
               string_agg(
                 DISTINCT COALESCE(fl.fluor_name, fl.fluor_code),
                 ', ' ORDER BY COALESCE(fl.fluor_name, fl.fluor_code)
               ),
               ''
             ) AS flu
      FROM c
      JOIN public.fluors fl
        ON fl.fluor_code = c.code
        OR fl.fluor_name = c.code
    """).bindparams(bindparam("codes", type_=ARRAY(TEXT())))
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    return (df["flu"].iloc[0] or "") if not df.empty else ""

def _split_tx_codes(s: str) -> List[str]:
    if not s:
        return []
    parts = [p.strip() for p in re.split(r"\s*\+\s*", s) if p.strip()]
    return parts

def _dedup_rollup(*parts: List[str]) -> str:
    toks: List[str] = []
    for s in parts:
        if not s:
            continue
        toks.extend([t.strip() for t in str(s).split(",") if t.strip()])
    return ", ".join(sorted(set(toks), key=str.lower))

def _vert_table(title: str, rows: List[Tuple[str, str]]):
    t = pd.DataFrame(rows, columns=["Field","Value"])
    t["Field"] = t["Field"].astype("string")
    t["Value"] = t["Value"].astype("string").fillna("")
    st.markdown(f"**{title}**")
    st.dataframe(t, hide_index=True, use_container_width=True)

# ── dynamic tank_pairs columns (mother/father) ───────────────────────────────
@st.cache_data(show_spinner=False)
def _parent_cols() -> Tuple[str, str]:
    sql = text("""
      SELECT column_name FROM information_schema.columns
      WHERE table_schema='public' AND table_name='tank_pairs'
    """)
    with _eng().begin() as cx:
        cols = pd.read_sql(sql, cx)["column_name"].tolist()
    for a,b in (("mother_tank_id","father_tank_id"), ("tank_id_mother","tank_id_father")):
        if a in cols and b in cols:
            return a,b
    return "mother_tank_id","father_tank_id"

# ── loaders ──────────────────────────────────────────────────────────────────
def _load_crosses(q: Optional[str], d_from: Optional[date], d_to: Optional[date], limit: int) -> pd.DataFrame:
    """
    Cross rows with mom/dad tanks + genotypes + fusions.
    Uses v_fish_overview for genotype/fusions and tank_pairs + tanks + fish for parents.
    """
    mom_col, dad_col = _parent_cols()
    sql = text(f"""
      WITH fm AS (
        SELECT
          v.fish_code_raw        AS fish_code,
          MAX(v.genotype_pretty) AS genotype_pretty,
          MAX(v.fusions)         AS fusions
        FROM public.v_fish_overview v
        GROUP BY v.fish_code_raw
      )
      SELECT
        cr.id::uuid::text         AS cross_id,
        -- DISPLAY cross code: stored cross_run_code or TP@date
        COALESCE(
          cr.cross_run_code,
          tp.tank_pair_code || ' @ ' || cr.created_at::date::text
        )                         AS cross_code,
        cr.created_at::date       AS cross_date,
        tp.tank_pair_code         AS tank_pair_code,
        tm.tank_code              AS mom_tank_code,
        tf.tank_code              AS dad_tank_code,
        COALESCE(fm_m.genotype_pretty,'') AS mom_genotype,
        COALESCE(fm_f.genotype_pretty,'') AS dad_genotype,
        COALESCE(fm_m.fusions,'')         AS mom_fusions,
        COALESCE(fm_f.fusions,'')         AS dad_fusions
      FROM public.crosses cr
      LEFT JOIN public.tank_pairs tp  ON tp.id = cr.tank_pair_id

      -- mother tank + fish
      LEFT JOIN public.tanks tm       ON tm.id = tp.{mom_col}
      LEFT JOIN public.fish  f_m      ON f_m.id = tm.fish_id
      LEFT JOIN fm         fm_m       ON fm_m.fish_code = f_m.fish_code

      -- father tank + fish
      LEFT JOIN public.tanks tf       ON tf.id = tp.{dad_col}
      LEFT JOIN public.fish  f_f      ON f_f.id = tf.fish_id
      LEFT JOIN fm         fm_f       ON fm_f.fish_code = f_f.fish_code

      WHERE (:d1 IS NULL OR cr.created_at::date >= :d1)
        AND (:d2 IS NULL OR cr.created_at::date <= :d2)
        AND (
          :q IS NULL OR
          COALESCE(cr.cross_run_code, '') ILIKE :ql OR
          tp.tank_pair_code ILIKE :ql OR
          COALESCE(tm.tank_code,'') ILIKE :ql OR
          COALESCE(tf.tank_code,'') ILIKE :ql OR
          COALESCE(fm_m.genotype_pretty,'') ILIKE :ql OR
          COALESCE(fm_f.genotype_pretty,'') ILIKE :ql
        )
      ORDER BY cr.created_at DESC NULLS LAST, cr.cross_run_code
      LIMIT :lim
    """)

    qnorm = (q or "").strip()
    params = {
        "q":  (qnorm if qnorm else None),
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

def _load_treated_clutches_for_crosses(cross_ids: List[str]) -> pd.DataFrame:
    """All treated-clutch groups whose clutches belong to any selected cross (with clutch genotype)."""
    if not cross_ids:
        return pd.DataFrame(
            columns=[
                "group_code",
                "clutch_code",
                "dob",
                "treatments_codes",
                "treatments_names",
                "tx_genotype",
                "offspring_genotype",
                "cross_id",
                "cross_code",
            ]
        )

    sql = text("""
      WITH picked AS (
        SELECT unnest(:ids)::uuid AS cross_id
      ),
      cl AS (
        SELECT
          ci.id                    AS clutch_instance_id,
          ci.clutch_instance_code  AS clutch_code,
          ci.clutch_date           AS clutch_date,
          ci.cross_instance_id     AS cross_id
        FROM public.clutch_instances ci
        WHERE ci.cross_instance_id = ANY(SELECT cross_id FROM picked)
      )
      SELECT
        vt.treated_clutch_code           AS group_code,
        vt.clutch_code                   AS clutch_code,
        cl.clutch_date                   AS dob,

        -- UPDATED: use new rollup columns from v_treated_clutches_overview
        COALESCE(vt.treatment_codes_rollup,'') AS treatments_codes,
        COALESCE(vt.treatment_names_rollup,'') AS treatments_names,

        ''::text                                AS tx_genotype,        -- no tx genotype rollup yet
        COALESCE(vt.clutch_genotype,'')        AS offspring_genotype,  -- plain clutch_genotype from view
        cr.id::uuid::text                      AS cross_id,
        cr.cross_run_code                      AS cross_code
      FROM cl
      JOIN public.v_treated_clutches_overview vt
           ON vt.clutch_instance_id::uuid = cl.clutch_instance_id   -- cast text -> uuid
      JOIN public.crosses cr
           ON cr.id = cl.cross_id
      ORDER BY vt.group_created_at DESC NULLS LAST, vt.treated_clutch_code
    """).bindparams(bindparam("ids", type_=ARRAY(UUID())))

    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"ids": cross_ids})

    for c in df.select_dtypes("object").columns:
        df[c] = df[c].astype("string").fillna("")

    return df

# ── filters ──────────────────────────────────────────────────────────────────
with st.form("filters", clear_on_submit=False):
    c1, c2, c3 = st.columns([2,1,1])
    q = c1.text_input("Search crosses (code / TP / parent genotypes)", "")
    d_from = c2.date_input("From", value=None)
    d_to   = c3.date_input("To", value=None)
    limit = int(st.number_input("Limit", min_value=10, max_value=3000, value=500, step=50))
    st.form_submit_button("Apply", use_container_width=True)

# ── Step 1: select crosses ───────────────────────────────────────────────────
df_cross = _load_crosses(q, d_from, d_to, limit)
st.caption(f"{len(df_cross)} cross(es)")

st.subheader("1) Select cross(es)")
cx_sel = "✓ Select"
cx_view = df_cross.copy()
if cx_sel not in cx_view.columns:
    cx_view.insert(0, cx_sel, False)

cx_picker = st.data_editor(
    cx_view[[cx_sel, "cross_code","cross_date","tank_pair_code","mom_tank_code","dad_tank_code","mom_genotype","dad_genotype"]],
    hide_index=True, use_container_width=True,
    column_config={
        cx_sel:               st.column_config.CheckboxColumn("✓", default=False),
        "cross_code":         st.column_config.TextColumn("Cross code", disabled=True),
        "cross_date":         st.column_config.DateColumn("Date", disabled=True),
        "tank_pair_code":     st.column_config.TextColumn("Tank pair", disabled=True),
        "mom_tank_code":      st.column_config.TextColumn("Mother tank", disabled=True),
        "dad_tank_code":      st.column_config.TextColumn("Father tank", disabled=True),
        "mom_genotype":       st.column_config.TextColumn("Mom genotype", disabled=True, width="large"),
        "dad_genotype":       st.column_config.TextColumn("Dad genotype", disabled=True, width="large"),
    },
    key="cross_picker_editor_v6",
)
cx_mask = cx_picker.get(cx_sel, pd.Series(False, index=cx_picker.index)).fillna(False).astype(bool)
chosen_crosses = df_cross.loc[cx_mask].reset_index(drop=True)
st.caption(f"Selected: {len(chosen_crosses)} cross(es)")
if chosen_crosses.empty:
    st.stop()

# ── Step 2: ONLY treated clutches for selected crosses ───────────────────────
st.subheader("2) Select treated clutch group(s) for selected cross(es)")
cross_ids = chosen_crosses["cross_id"].astype(str).tolist()
treat_df  = _load_treated_clutches_for_crosses(cross_ids)

tc_sel = "✓ Select treated"
if not treat_df.empty and tc_sel not in treat_df.columns:
    treat_df.insert(0, tc_sel, False)

treat_picker = st.data_editor(
    treat_df[[tc_sel,"group_code","clutch_code","dob","treatments_codes","treatments_names","tx_genotype","offspring_genotype","cross_code"]] if not treat_df.empty else treat_df,
    hide_index=True, use_container_width=True,
    column_config={
        tc_sel:                   st.column_config.CheckboxColumn("✓", default=False),
        "group_code":             st.column_config.TextColumn("Group code", disabled=True),
        "clutch_code":            st.column_config.TextColumn("Clutch", disabled=True),
        "dob":                    st.column_config.DateColumn("DOB", disabled=True),
        "treatments_codes":       st.column_config.TextColumn("Tx codes", disabled=True),
        "treatments_names":       st.column_config.TextColumn("Tx names", disabled=True, width="large"),
        "tx_genotype":            st.column_config.TextColumn("Tx → genotype", disabled=True, width="large"),
        "offspring_genotype":     st.column_config.TextColumn("Offspring genotype", disabled=True, width="large"),
        "cross_code":             st.column_config.TextColumn("Cross", disabled=True),
    },
    key="treated_clutch_picker_editor_rollup_v2",
)
treat_mask = treat_picker.get(tc_sel, pd.Series(False, index=treat_picker.index)).fillna(False).astype(bool) if not treat_df.empty else pd.Series(dtype=bool)
chosen_treated = treat_df.loc[treat_mask].reset_index(drop=True) if not treat_df.empty else treat_df
st.caption(f"Selected treated clutch groups: {len(chosen_treated)}")

# ── Step 3: label preview (pivot/vertical tables; paginated per cross) ──────
st.subheader("3) Label preview")

n_cross = len(chosen_crosses)
page = 1
if n_cross > 1:
    page = st.number_input("Preview page (one cross + one clutch per page)", min_value=1, max_value=n_cross, value=1, step=1)
idx = int(page) - 1
cx_row = chosen_crosses.iloc[idx].to_dict()

# CROSS preview
mom_g, dad_g = cx_row.get("mom_genotype",""), cx_row.get("dad_genotype","")
fusion_cross = _dedup_rollup(cx_row.get("mom_fusions",""), cx_row.get("dad_fusions",""))
_vert_table(
    f"CROSS {cx_row.get('cross_code','')}",
    [
        ("Cross code",   cx_row.get("cross_code","")),
        ("Date",         str(cx_row.get("cross_date") or "")),
        ("Tank pair",    cx_row.get("tank_pair_code","")),
        ("Mother tank",  cx_row.get("mom_tank_code","")),
        ("Father tank",  cx_row.get("dad_tank_code","")),
        ("Mom genotype", mom_g),
        ("Dad genotype", dad_g),
        ("Fusions",      fusion_cross),
    ]
)

# CLUTCH preview (rollups across selected treated groups tied to THIS cross)
tc_for_cross = (
    chosen_treated.loc[chosen_treated["cross_id"] == cx_row.get("cross_id")]
    if not chosen_treated.empty else pd.DataFrame()
)
if not tc_for_cross.empty:
    # 1) Codes rollup = treatments codes
    all_codes: List[str] = []
    for s in tc_for_cross["treatments_codes"].astype(str).tolist():
        all_codes.extend(_split_tx_codes(s))
    codes_rollup = " + ".join(sorted(set([c for c in all_codes if c])))

    # 2) Fluor rollup = union of fluor codes from tx codes + offspring genotype bases
    flu_from_tx   = _fluors_for_ft_codes(sorted(set([c for c in all_codes if c])))
    bases_offspring: List[str] = []
    for s in tc_for_cross["offspring_genotype"].astype(str).tolist():
        bases_offspring.extend(_bases_from_genotype(s))
    flu_from_offspring = _fluor_names_for_bases(sorted(set(bases_offspring)))
    flu_rollup = _dedup_rollup(flu_from_tx, flu_from_offspring)

    tr = tc_for_cross.iloc[0].to_dict()
    clutch_label   = tr.get("clutch_code") or tr.get("group_code") or ""
    clutch_geno    = tr.get("offspring_genotype","")

    _vert_table(
        f"CLUTCH · GROUP(S) {', '.join(tc_for_cross['group_code'].tolist())}",
        [
            ("Clutch",            clutch_label),
            ("Genotype",          clutch_geno),
            ("DOB",               str(tr.get("dob") or "")),
            ("Tx codes (rollup)", codes_rollup),
            ("Fluors (rollup)",   flu_rollup),
        ]
    )
else:
    st.info("No treated clutch group selected for this cross (choose one in Step 2 to preview).")

# ── Step 4: download / print for ALL selected ────────────────────────────────
st.subheader("4) Download / print for selected")

# Cross label rows
cross_rows: List[Dict] = []
for r in chosen_crosses.to_dict(orient="records"):
    cross_rows.append({
        "cross_code":        r.get("cross_code"),
        "cross_date":        r.get("cross_date"),
        "mother_tank_code":  r.get("mom_tank_code"),
        "father_tank_code":  r.get("dad_tank_code"),
        "mom_genotype":      r.get("mom_genotype"),
        "dad_genotype":      r.get("dad_genotype"),
    })

# Treated clutch groups → petri labels
petri_rows: List[Dict] = []
for r in chosen_treated.to_dict(orient="records"):
    tx_codes  = _split_tx_codes(r.get("treatments_codes",""))
    tx_fluors = _fluors_for_ft_codes(tx_codes)
    offspring_bases = _bases_from_genotype(r.get("offspring_genotype",""))
    offspring_flu   = _fluor_names_for_bases(offspring_bases)
    petri_rows.append({
        "clutch_instance_code": r.get("treated_clutch_code") or r.get("group_code") or "",
        "clutch_name": "",
        "mom_code": "",
        "dad_code": "",
        "clutch_genotype": r.get("tx_genotype") or "",
        "date_birth": str(r.get("dob") or ""),
        "tx_codes":   " + ".join(tx_codes),
        "tx_fluors":  _dedup_rollup(tx_fluors, offspring_flu),
    })

c1, c2 = st.columns(2)
with c1:
    if HAVE_PRINT_HELPER:
        download_button_for_labels(
            rows=cross_rows,
            builder="crossing",
            file_prefix="cross_labels",
            button_text="🖨️ Print / Download CROSS labels (ALL selected)"
        )
    else:
        st.button("🖨️ Print / Download CROSS labels (ALL selected)", disabled=True)

with c2:
    if HAVE_PRINT_HELPER:
        download_button_for_labels(
            rows=petri_rows,
            builder="petri",
            file_prefix="clutch_labels",
            button_text="🖨️ Print / Download CLUTCH labels (ALL selected)"
        )
    else:
        st.button("🖨️ Print / Download CLUTCH labels (ALL selected)", disabled=True)