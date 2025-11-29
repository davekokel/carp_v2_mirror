# carp_app/ui/pages/210_🧪_annotate_treated_clutch_groups.py
# 🐣 Annotate treated clutches (v11, clutch_annotations table)

from __future__ import annotations

import sys, pathlib, os
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

# --- project wiring -----------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine

eng = engine()

# --- auth / page --------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🐣 Annotate treated clutches (v11)",
    page_icon="🐣",
    layout="wide",
)
st.title("🐣 Annotate treated clutches (v11)")

with eng.begin() as cx:
    dbg = pd.read_sql(
        text("select current_database() db, inet_server_addr() host, current_user u"),
        cx,
    )
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# --- objects we use -----------------------------------------------------------
V_CLUTCH_STAR = "public.v11_clutch_star"      # canonical clutch view
T_CLUTCH_ANN  = "public.clutch_annotations"   # new annotations table

# --- helpers ------------------------------------------------------------------
def _exists_view(qualified: str) -> bool:
    sch, name = qualified.split(".", 1)
    q = text(
        "SELECT 1 FROM information_schema.views WHERE table_schema=:s AND table_name=:n "
        "UNION ALL SELECT 1 FROM pg_catalog.pg_matviews WHERE schemaname=:s AND matviewname=:n "
        "LIMIT 1"
    )
    with eng.begin() as cx:
        return cx.execute(q, {"s": sch, "n": name}).first() is not None

def _exists_table(qualified: str) -> bool:
    sch, name = qualified.split(".", 1)
    q = text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema=:s AND table_name=:n LIMIT 1"
    )
    with eng.begin() as cx:
        return cx.execute(q, {"s": sch, "n": name}).first() is not None

def _safe(cx, q: str | TextClause, p: Dict[str, Any] | None = None) -> pd.DataFrame:
    q = q if isinstance(q, TextClause) else text(q)
    return pd.read_sql(q, cx, params=p or {})

def _pivot(title: str, rows: List[Tuple[str, Any]]):
    dfp = pd.DataFrame(rows, columns=["Field", "Value"])
    st.markdown(f"**{title}**")
    st.dataframe(dfp, hide_index=True, use_container_width=True)

# --- ensure core objects exist -----------------------------------------------
miss = []
if not _exists_view(V_CLUTCH_STAR):
    miss.append(V_CLUTCH_STAR)
if not _exists_table(T_CLUTCH_ANN):
    miss.append(T_CLUTCH_ANN)

if miss:
    st.error("Required object not found: " + ", ".join(miss))
    st.stop()

# --- filters ------------------------------------------------------------------
today = date.today()
with st.form("filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1:
        d_from = st.date_input("From (clutch date)", value=today - timedelta(days=120))
    with c2:
        d_to = st.date_input("To (clutch date)", value=today + timedelta(days=14))
    with c3:
        qtxt = st.text_input(
            "Search (clutch/genotype/treatments/fluors)",
            value="",
        )
    with c4:
        st.caption("Filters clutches with at least one treatment in v11_clutch_star.")
    r1, r2 = st.columns([1, 1])
    with r1:
        most_recent = st.checkbox("Most recent (ignore dates)", value=False)
    with r2:
        limit = st.number_input("Limit", min_value=1, max_value=1000, value=500, step=50)
    st.form_submit_button("Apply", use_container_width=True)

# --- load treated clutches from v11_clutch_star ------------------------------
def _load_clutches_filtered(
    d1: date, d2: date, q: str, most_recent: bool, limit: int
) -> pd.DataFrame:
    where: list[str] = []
    p: Dict[str, Any] = {}

    # treated clutches only
    where.append("(COALESCE(treat_codes,'') <> '' OR COALESCE(treatment_code,'') <> '')")

    if not most_recent:
        where.append("clutch_date::date BETWEEN :d1 AND :d2")
        p.update({"d1": d1, "d2": d2})

    qnorm = q.strip()
    if qnorm:
        p["q"] = f"%{qnorm}%"
        where.append(
            """(
              COALESCE(clutch_code,'')                 ILIKE :q OR
              COALESCE(genotype_pretty,'')             ILIKE :q OR
              COALESCE(genotype_basecode_code,'')      ILIKE :q OR
              COALESCE(genotype_transgene_allele_code,'') ILIKE :q OR
              COALESCE(treatment_code,'')              ILIKE :q OR
              COALESCE(treat_codes,'')                 ILIKE :q OR
              COALESCE(all_fluor_tag_rollup,'')        ILIKE :q OR
              COALESCE(all_organelle_fluor_rollup,'')  ILIKE :q
            )"""
        )

    wsql = "WHERE " + " AND ".join(where) if where else ""
    p["lim"] = int(limit)

    sql = text(
        f"""
        SELECT *
        FROM {V_CLUTCH_STAR}
        {wsql}
        ORDER BY clutch_date, clutch_code
        LIMIT :lim
        """
    )
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params=p)

    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")

    return df

df = _load_clutches_filtered(d_from, d_to, qtxt, most_recent, limit)
st.caption(f"{len(df)} treated clutch(es)")

if df.empty:
    st.info("No treated clutches with the current filters.")
    st.stop()

# --- picker -------------------------------------------------------------------
cols = [
    "clutch_code",
    "clutch_date",
    "treatment_code",
    "treat_codes",
    "genotype_pretty",
]
dfv = df[cols].copy()
dfv.insert(0, "✓ Select", False)

last_clutch = st.session_state.get("__annot_last_clutch")
if last_clutch:
    dfv.loc[dfv["clutch_code"] == last_clutch, "✓ Select"] = True

st.subheader("Treated clutches")
picker = st.data_editor(
    dfv,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "✓ Select":       st.column_config.CheckboxColumn("✓", default=False),
        "clutch_code":    st.column_config.TextColumn("Clutch", disabled=True),
        "clutch_date":    st.column_config.DateColumn("Clutch date", disabled=True),
        "treatment_code": st.column_config.TextColumn("Primary treatment", disabled=True),
        "treat_codes":    st.column_config.TextColumn("All treatment codes", disabled=True, width="large"),
        "genotype_pretty": st.column_config.TextColumn("Genotype (pretty)", disabled=True, width="large"),
    },
    key="annot_clutch_picker_v11",
)

sel = (
    picker.get("✓ Select", pd.Series(False, index=picker.index))
    .fillna(False)
    .astype(bool)
)
picked = df[sel].reset_index(drop=True)

st.subheader("Details")
if picked.empty:
    st.info("Select a treated clutch to annotate it.")
    st.stop()

if len(picked) > 1:
    st.warning("Multiple rows selected; showing the first one.")

row = picked.iloc[0].to_dict()
clutch_id = str(row.get("clutch_id", "") or "")
clutch_code = str(row.get("clutch_code", "") or "")
st.session_state["__annot_last_clutch"] = clutch_code

summary_rows = [
    ("Clutch id",             clutch_id),
    ("Clutch code",           clutch_code),
    ("Clutch date",           row.get("clutch_date")),
    ("Treatment code",        row.get("treatment_code")),
    ("All treatment codes",   row.get("treat_codes")),
    ("Genotype (pretty)",     row.get("genotype_pretty")),
    ("Genotype basecodes",    row.get("genotype_basecode_code")),
    ("Genotype allele codes", row.get("genotype_transgene_allele_code")),
    ("Tx → fluor::tag(pos)",  row.get("all_fluor_tag_rollup")),
    ("Tx → organelle-fluor",  row.get("all_organelle_fluor_rollup")),
]

_pivot("Clutch summary", summary_rows)

# --- load current (latest) annotation values ---------------------------------
def _load_clutch_latest(clutch_id: str) -> Dict[str, Any]:
    if not clutch_id:
        return {}
    sql = text(
        """
        WITH ranked AS (
          SELECT
            ca.kind_code,
            ca.value_num,
            ca.value_text,
            ca.created_at,
            ROW_NUMBER() OVER (
              PARTITION BY ca.kind_code
              ORDER BY ca.created_at DESC NULLS LAST
            ) rn
          FROM public.clutch_annotations ca
          WHERE ca.clutch_id = CAST(:cid AS uuid)
        )
        SELECT kind_code, value_num, value_text
        FROM ranked WHERE rn = 1
        """
    )
    with eng.begin() as cx:
        df = pd.read_sql(sql, cx, params={"cid": clutch_id})

    out: Dict[str, Any] = {}
    for _, r in df.iterrows():
        k = str(r["kind_code"])
        if k == "notes":
            out[k] = r.get("value_text")
        else:
            out[k] = r.get("value_num")
    return out

current = _load_clutch_latest(clutch_id)

# --- inputs (1–100 scale for intensities/frequencies) ------------------------
st.subheader("Annotate this treated clutch")

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    red_val = st.number_input(
        "red_intensity (1–100)",
        min_value=1,
        max_value=100,
        step=1,
        value=int(round(float(current.get("red_intensity") or 0) or 1)),
    )
with c2:
    green_val = st.number_input(
        "green_intensity (1–100)",
        min_value=1,
        max_value=100,
        step=1,
        value=int(round(float(current.get("green_intensity") or 0) or 1)),
    )
with c3:
    note_txt = st.text_input(
        "notes", value=str(current.get("notes") or ""), placeholder="optional"
    )

c4, c5, c6 = st.columns([1, 1, 1])
with c4:
    gfreq_val = st.number_input(
        "green_frequency (1–100)",
        min_value=1,
        max_value=100,
        step=1,
        value=int(round(float(current.get("green_frequency") or 0) or 1)),
    )
with c5:
    rfreq_val = st.number_input(
        "red_frequency (1–100)",
        min_value=1,
        max_value=100,
        step=1,
        value=int(round(float(current.get("red_frequency") or 0) or 1)),
    )
with c6:
    n_val = st.number_input(
        "n_animals (integer ≥ 0)",
        min_value=0,
        step=1,
        value=int(current.get("n_animals") or 0),
    )

# --- save to clutch_annotations ----------------------------------------------
def _save_annotation_num(cid: str, kind: str, val: int, who: str):
    with eng.begin() as cx:
        cx.execute(
            text(
                """
          INSERT INTO public.clutch_annotations
            (clutch_id, kind_code, value_num, created_at, created_by)
          VALUES (CAST(:cid AS uuid), :k, :v, now(), :who)
        """
            ),
            {"cid": cid, "k": kind, "v": val, "who": who},
        )

def _save_annotation_text(cid: str, kind: str, txt: str, who: str):
    if not (txt or "").strip():
        return
    with eng.begin() as cx:
        cx.execute(
            text(
                """
          INSERT INTO public.clutch_annotations
            (clutch_id, kind_code, value_text, created_at, created_by)
          VALUES (CAST(:cid AS uuid), :k, NULLIF(:v,''), now(), :who)
        """
            ),
            {"cid": cid, "k": kind, "v": txt, "who": who},
        )

if st.button("💾 Save", use_container_width=True):
    who = (
        getattr(user, "email", None)
        or os.getenv("USER")
        or os.getenv("USERNAME")
        or "system"
    )
    _save_annotation_num(clutch_id, "red_intensity", int(red_val), who)
    _save_annotation_num(clutch_id, "green_intensity", int(green_val), who)
    _save_annotation_num(clutch_id, "green_frequency", int(gfreq_val), who)
    _save_annotation_num(clutch_id, "red_frequency", int(rfreq_val), who)
    _save_annotation_num(clutch_id, "n_animals", int(n_val), who)
    _save_annotation_text(clutch_id, "notes", note_txt, who)
    st.success("Annotation saved.")
    st.rerun()

# --- show current after save --------------------------------------------------
st.subheader("Current annotation (latest values)")
latest = _load_clutch_latest(clutch_id)
if latest:
    show = {
        "red_intensity":   latest.get("red_intensity"),
        "green_intensity": latest.get("green_intensity"),
        "green_frequency": latest.get("green_frequency"),
        "red_frequency":   latest.get("red_frequency"),
        "n_animals":       latest.get("n_animals"),
        "notes":           latest.get("notes"),
    }
    df_show = pd.DataFrame([show])
    st.dataframe(df_show, hide_index=True, use_container_width=True)
else:
    st.caption("No annotations recorded yet for this clutch.")