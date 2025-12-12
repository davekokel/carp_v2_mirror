# carp_app/ui/pages/270_🖨️_print_cross_and_clutch_labels.py
# 🖨️ Cross & Clutch labels (v11) — marker_rollup-focused labels

from __future__ import annotations

import sys, pathlib
from typing import List, Dict, Tuple, Optional
from datetime import date

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
    def require_app_unlock(): ...

from carp_app.ui.lib.page_engine import engine as _engine

HAVE_PRINT_HELPER = False
try:
    from carp_app.ui.lib.labels_components import download_button_for_labels
    HAVE_PRINT_HELPER = True
except Exception:
    pass

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🖨️ Cross & Clutch labels (v11)",
    page_icon="🖨️",
    layout="wide",
)
st.title("🖨️ Cross & Clutch labels (v11)")


def eng() -> Engine:
    return _engine()


def _vert_table(title: str, rows: List[Tuple[str, str]]):
    t = pd.DataFrame(rows, columns=["Field", "Value"])
    t["Field"] = t["Field"].astype("string")
    t["Value"] = t["Value"].astype("string").fillna("")
    st.markdown(f"**{title}**")
    st.dataframe(t, hide_index=True, use_container_width=True)


def _marker_rollup(treat_label: str, geno: str, bg: str) -> str:
    t = (treat_label or "").strip()
    g = (geno or "").strip()
    b = (bg or "").strip()
    if t and g:
        return f"{t} > {g}"
    if t:
        return t
    if g:
        return g
    return b


def _sig(initials: str) -> str:
    ini = (initials or "").strip()
    return f"gokul • {ini}" if ini else "gokul"


def _tank_label(tank_code: str, nickname: str) -> str:
    t = (tank_code or "").strip()
    n = (nickname or "").strip()
    if t and n:
        return f"{t} ({n})"
    return t or n


@st.cache_data(show_spinner=False)
def _parent_cols() -> Tuple[str, str]:
    sql = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='tank_pairs'
        ORDER BY ordinal_position;
        """
    )
    with eng().begin() as cx:
        cols = pd.read_sql(sql, cx)["column_name"].tolist()
    for a, b in (("mother_tank_id", "father_tank_id"), ("tank_id_mother", "tank_id_father")):
        if a in cols and b in cols:
            return a, b
    return "mother_tank_id", "father_tank_id"


@st.cache_data(show_spinner=False)
def _load_crosses_marker(q: Optional[str], d_from: Optional[date], d_to: Optional[date], limit: int) -> pd.DataFrame:
    mom_col, dad_col = _parent_cols()
    qnorm = (q or "").strip()
    params = {
        "q": (qnorm if qnorm else None),
        "ql": f"%{qnorm}%",
        "d1": (str(d_from) if d_from else None),
        "d2": (str(d_to) if d_to else None),
        "lim": int(limit),
    }

    sql = text(
        f"""
        WITH lbl AS (
          SELECT
            fish_instance_id::uuid AS fish_instance_id,
            fish_code,
            COALESCE(genetic_background,'') AS genetic_background,
            COALESCE(genotype_tg_style,'') AS genotype_tg_style,
            COALESCE(genotype_fluortag_style,'') AS genotype_fluortag_style,
            COALESCE(treatment_label_tg_style,'') AS treatment_label_tg_style,
            COALESCE(treatment_label_fluortag_style,'') AS treatment_label_fluortag_style
          FROM public.v11_fish_instance_star_labels
        )
        SELECT
          cr.id::uuid::text         AS cross_id,
          COALESCE(cr.cross_run_code, tp.tank_pair_code || ' @ ' || cr.created_at::date::text)
                                   AS cross_code,
          cr.created_at::date       AS cross_date,
          tp.tank_pair_code         AS tank_pair_code,

          tm.tank_code              AS mom_tank_code,
          tf.tank_code              AS dad_tank_code,

          COALESCE(fim.nickname,'') AS mom_instance_nickname,
          COALESCE(fid.nickname,'') AS dad_instance_nickname,

          COALESCE(lm.genetic_background,'') AS mom_background,
          COALESCE(ld.genetic_background,'') AS dad_background,

          COALESCE(lm.genotype_tg_style,'') AS mom_genotype_tg,
          COALESCE(ld.genotype_tg_style,'') AS dad_genotype_tg,
          COALESCE(lm.treatment_label_tg_style,'') AS mom_treat_tg,
          COALESCE(ld.treatment_label_tg_style,'') AS dad_treat_tg,

          COALESCE(lm.genotype_fluortag_style,'') AS mom_genotype_fluortag,
          COALESCE(ld.genotype_fluortag_style,'') AS dad_genotype_fluortag,
          COALESCE(lm.treatment_label_fluortag_style,'') AS mom_treat_fluortag,
          COALESCE(ld.treatment_label_fluortag_style,'') AS dad_treat_fluortag

        FROM public.crosses cr
        LEFT JOIN public.tank_pairs tp ON tp.id = cr.tank_pair_id

        LEFT JOIN public.tanks tm ON tm.id = tp.{mom_col}
        LEFT JOIN public.tanks tf ON tf.id = tp.{dad_col}

        LEFT JOIN public.fish_instances_v10 fim ON fim.id = tm.fish_instance_id
        LEFT JOIN public.fish_instances_v10 fid ON fid.id = tf.fish_instance_id

        LEFT JOIN lbl lm ON lm.fish_instance_id = fim.id
        LEFT JOIN lbl ld ON ld.fish_instance_id = fid.id

        WHERE (:d1 IS NULL OR cr.created_at::date >= :d1)
          AND (:d2 IS NULL OR cr.created_at::date <= :d2)
          AND (
            :q IS NULL OR
            COALESCE(cr.cross_run_code,'')  ILIKE :ql OR
            tp.tank_pair_code               ILIKE :ql OR
            COALESCE(tm.tank_code,'')       ILIKE :ql OR
            COALESCE(tf.tank_code,'')       ILIKE :ql OR
            COALESCE(fim.nickname,'')       ILIKE :ql OR
            COALESCE(fid.nickname,'')       ILIKE :ql OR
            COALESCE(lm.genotype_tg_style,'') ILIKE :ql OR
            COALESCE(ld.genotype_tg_style,'') ILIKE :ql OR
            COALESCE(lm.genotype_fluortag_style,'') ILIKE :ql OR
            COALESCE(ld.genotype_fluortag_style,'') ILIKE :ql
          )
          AND EXISTS (
            SELECT 1
            FROM public.clutches c
            WHERE c.cross_id = cr.id
              AND COALESCE(c.source_system,'') <> 'legacy_imaging'
          )
        ORDER BY cr.created_at DESC NULLS LAST, cr.cross_run_code
        LIMIT :lim;
        """
    )

    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    for c in df.select_dtypes("object").columns:
        df[c] = df[c].astype("string").fillna("")
    df = df.fillna("")

    df["mom_marker_tg"] = df.apply(lambda r: _marker_rollup(r["mom_treat_tg"], r["mom_genotype_tg"], r["mom_background"]), axis=1)
    df["dad_marker_tg"] = df.apply(lambda r: _marker_rollup(r["dad_treat_tg"], r["dad_genotype_tg"], r["dad_background"]), axis=1)
    df["mom_marker_fluortag"] = df.apply(lambda r: _marker_rollup(r["mom_treat_fluortag"], r["mom_genotype_fluortag"], r["mom_background"]), axis=1)
    df["dad_marker_fluortag"] = df.apply(lambda r: _marker_rollup(r["dad_treat_fluortag"], r["dad_genotype_fluortag"], r["dad_background"]), axis=1)

    df["cross_marker_tg"] = df.apply(lambda r: f"{r['mom_marker_tg']} × {r['dad_marker_tg']}".strip(), axis=1)
    df["cross_marker_fluortag"] = df.apply(lambda r: f"{r['mom_marker_fluortag']} × {r['dad_marker_fluortag']}".strip(), axis=1)
    return df


@st.cache_data(show_spinner=False)
def _load_clutch_rows_for_crosses(cross_ids: List[str]) -> pd.DataFrame:
    if not cross_ids:
        return pd.DataFrame()

    sql = text(
        f"""
        WITH picked AS (
          SELECT unnest(:ids)::uuid AS cross_id
        )
        SELECT
          f.clutch_id::text AS clutch_id,
          f.clutch_code,
          f.clutch_date,
          COALESCE(f.treated_clutch_code,'') AS treated_clutch_code,
          COALESCE(f.treatment_code,'') AS treatment_code,
          COALESCE(f.genotype_pretty,'') AS genotype_pretty,
          COALESCE(f.marker_basecode_style,'') AS marker_rollup_tg_style,
          COALESCE(f.marker_fluortag_style,'') AS marker_rollup_fluortag_style,
          c.cross_id::text AS cross_id
        FROM public.v11_clutch_treated_groups_flat f
        JOIN public.clutches c
          ON c.id = CAST(f.clutch_id AS uuid)
        JOIN picked p
          ON p.cross_id = c.cross_id
        WHERE COALESCE(c.source_system,'') <> 'legacy_imaging'
        ORDER BY c.clutch_date DESC NULLS LAST, c.clutch_code, f.treated_clutch_code;
        """
    )

    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"ids": cross_ids})

    for c in df.select_dtypes("object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df.fillna("")


with st.form("filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    q = c1.text_input("Search crosses (code / TP / markers)", "")
    d_from = c2.date_input("From", value=None)
    d_to = c3.date_input("To", value=None)
    initials = c4.text_input("Your initials (optional)", value="")
    limit = int(st.number_input("Limit", min_value=10, max_value=3000, value=500, step=50))
    st.form_submit_button("Apply", use_container_width=True)

sig = _sig(initials)

df_cross = _load_crosses_marker(q, d_from, d_to, limit)
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
            "mom_instance_nickname",
            "dad_instance_nickname",
            "cross_marker_tg",
            "cross_marker_fluortag",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        cx_sel: st.column_config.CheckboxColumn("✓", default=False),
        "cross_code": st.column_config.TextColumn("Cross code", disabled=True),
        "cross_date": st.column_config.DateColumn("Date", disabled=True),
        "tank_pair_code": st.column_config.TextColumn("Tank pair", disabled=True),
        "mom_tank_code": st.column_config.TextColumn("Mother tank", disabled=True),
        "dad_tank_code": st.column_config.TextColumn("Father tank", disabled=True),
        "mom_instance_nickname": st.column_config.TextColumn("Mom nick", disabled=True),
        "dad_instance_nickname": st.column_config.TextColumn("Dad nick", disabled=True),
        "cross_marker_tg": st.column_config.TextColumn("Marker rollup (tg)", disabled=True, width="large"),
        "cross_marker_fluortag": st.column_config.TextColumn("Marker rollup (fluor-tag)", disabled=True, width="large"),
    },
    key="cross_picker_editor_v11",
)

cx_mask = cx_picker.get(cx_sel, pd.Series(False, index=cx_picker.index)).fillna(False).astype(bool)
chosen_crosses = df_cross.loc[cx_mask].reset_index(drop=True)
st.caption(f"Selected: {len(chosen_crosses)} cross(es)")
if chosen_crosses.empty:
    st.stop()

st.subheader("2) Select clutches for labels")

cross_ids = chosen_crosses["cross_id"].astype(str).tolist()
df_clutch = _load_clutch_rows_for_crosses(cross_ids)
st.caption(f"{len(df_clutch)} clutch row(s) for selected cross(es)")

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
            "treated_clutch_code",
            "treatment_code",
            "marker_rollup_tg_style",
            "marker_rollup_fluortag_style",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        cl_sel: st.column_config.CheckboxColumn("✓", default=False),
        "clutch_code": st.column_config.TextColumn("Clutch code", disabled=True),
        "clutch_date": st.column_config.DateColumn("DOB", disabled=True),
        "treated_clutch_code": st.column_config.TextColumn("Treated clutch", disabled=True),
        "treatment_code": st.column_config.TextColumn("Treatment", disabled=True),
        "marker_rollup_tg_style": st.column_config.TextColumn("Marker rollup (tg)", disabled=True, width="large"),
        "marker_rollup_fluortag_style": st.column_config.TextColumn("Marker rollup (fluor-tag)", disabled=True, width="large"),
    },
    key="clutch_picker_editor_v11",
)

cl_mask = cl_picker.get(cl_sel, pd.Series(False, index=cl_picker.index)).fillna(False).astype(bool)
chosen_clutches = df_clutch.loc[cl_mask].reset_index(drop=True)
st.caption(f"Selected: {len(chosen_clutches)} clutch row(s)")

st.subheader("3) Label preview")

n_cross = len(chosen_crosses)
page = 1
if n_cross > 1:
    page = st.number_input("Preview page (per cross)", min_value=1, max_value=n_cross, value=1, step=1)
idx = int(page) - 1
cx_row = chosen_crosses.iloc[idx].to_dict()

mom_label_prev = _tank_label(cx_row.get("mom_tank_code", ""), cx_row.get("mom_instance_nickname", ""))
dad_label_prev = _tank_label(cx_row.get("dad_tank_code", ""), cx_row.get("dad_instance_nickname", ""))

cross_rows_preview: List[Tuple[str, str]] = [
    ("Footer (lower right)", sig),
    ("Cross", f"{cx_row.get('cross_code','')} @ {cx_row.get('cross_date','')}"),
    ("Mother", mom_label_prev),
    ("Father", dad_label_prev),
    ("Marker (tg)", cx_row.get("cross_marker_tg", "")),
    ("Marker (fluor-tag)", cx_row.get("cross_marker_fluortag", "")),
]
_vert_table(f"CROSS {cx_row.get('cross_code','')}", cross_rows_preview)

if chosen_clutches.empty:
    st.info("No selected clutch rows (choose some in Step 2 to preview clutch labels).")
else:
    cl_for_cross = chosen_clutches[chosen_clutches["cross_id"] == cx_row["cross_id"]]
    if cl_for_cross.empty:
        st.info("No selected clutch rows for this cross.")
    else:
        tr = cl_for_cross.iloc[0].to_dict()
        clutch_rows_preview: List[Tuple[str, str]] = [
            ("Footer (lower right)", sig),
            ("Clutch", f"{tr.get('clutch_code','')} {tr.get('treated_clutch_code','')}".strip()),
            ("DOB", str(tr.get("clutch_date") or "")),
            ("Marker (tg)", tr.get("marker_rollup_tg_style", "")),
            ("Marker (fluor-tag)", tr.get("marker_rollup_fluortag_style", "")),
        ]
        _vert_table(f"CLUTCH {tr.get('clutch_code','')}", clutch_rows_preview)

st.subheader("4) Download / print labels for selected")

cross_rows: List[Dict] = []
for r in chosen_crosses.to_dict(orient="records"):
    mom_label = _tank_label(r.get("mom_tank_code", ""), r.get("mom_instance_nickname", ""))
    dad_label = _tank_label(r.get("dad_tank_code", ""), r.get("dad_instance_nickname", ""))

    cross_rows.append(
    {
        "cross_code": f"{r.get('cross_code','')} @ {r.get('cross_date','')}",
        "mother_tank_label": _tank_label(r.get("mom_tank_code",""), r.get("mom_instance_nickname","")),
        "father_tank_label": _tank_label(r.get("dad_tank_code",""), r.get("dad_instance_nickname","")),
        "mom_genotype": r.get("mom_marker_tg"),
        "dad_genotype": r.get("dad_marker_tg"),
        "mom_fluortag": r.get("mom_marker_fluortag"),
        "dad_fluortag": r.get("dad_marker_fluortag"),
        "fusions": r.get("cross_marker_fluortag"),  # optional fallback
        "clutch_label": "",
        "clutch_fluors": "",
        "footer_right": sig,
    }
)

petri_rows: List[Dict] = []
for r in chosen_clutches.to_dict(orient="records"):
    clutch_instance_code = f"{r.get('clutch_code','')}".strip()
    if r.get("treated_clutch_code"):
        clutch_instance_code = f"{clutch_instance_code} {r.get('treated_clutch_code')}".strip()

    petri_rows.append(
        {
            "clutch_instance_code": clutch_instance_code,
            "clutch_name": "",
            "mom_code": "",
            "dad_code": "",
            "clutch_genotype": r.get("marker_rollup_tg_style", ""),
            "date_birth": str(r.get("clutch_date") or ""),
            "tx_codes": r.get("treatment_code", ""),
            "tx_fluors": r.get("marker_rollup_fluortag_style", ""),
            "footer_right": sig,
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