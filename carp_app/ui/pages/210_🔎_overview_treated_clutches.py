# =============================================================================
# 🔎 Overview — Clutch treatments (parents + offspring genotype, pivot drilldown)
# Requires:
#   • public.v_clutch_instances  (codes/fusions/tokens + lineage fields)
#   • public.clutch_instances
#   • public.crosses
#   • public.v_tank_pairs
# Optional:
#   • public.v_clutch_annotations_pivot  (or public.v_clutch_annotations)
# =============================================================================
from __future__ import annotations
import os, sys, pathlib
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy import text as _sql
from sqlalchemy.engine import Engine

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
from carp_app.ui.lib.app_ctx import get_engine as _create_engine

# --- auth / page --------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🔎 Overview — Clutch treatments",
                   page_icon="🧪", layout="wide")
st.title("🔎 Overview — Clutch treatments")

# --- engine -------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        st.error("DB_URL not set"); st.stop()
    return _create_engine()

# --- object names -------------------------------------------------------------
V_CLUTCH   = "public.v_clutch_instances"
T_CLUTCH   = "public.clutch_instances"
T_CROSSES  = "public.crosses"
V_TPAIRS   = "public.v_tank_pairs"
T_JCT      = "public.join_clutch_treatments"
V_ANN      = "public.v_clutch_annotations_pivot"
V_ANN_ALT  = "public.v_clutch_annotations"

# --- helpers ------------------------------------------------------------------
def _exists_view(qualified: str) -> bool:
    sch, name = qualified.split(".", 1)
    q = _sql(
        "SELECT 1 FROM information_schema.views WHERE table_schema=:s AND table_name=:n "
        "UNION ALL SELECT 1 FROM pg_catalog.pg_matviews WHERE schemaname=:s AND matviewname=:n LIMIT 1"
    )
    with _eng().begin() as cx:
        return cx.execute(q, {"s": sch, "n": name}).first() is not None

def _exists_table(qualified: str) -> bool:
    sch, name = qualified.split(".", 1)
    q = _sql("SELECT 1 FROM information_schema.tables WHERE table_schema=:s AND table_name=:n LIMIT 1")
    with _eng().begin() as cx:
        return cx.execute(q, {"s": sch, "n": name}).first() is not None

def _resolve_clutch_id(clutch_code: str) -> str | None:
    sql = text("SELECT id::text FROM public.clutch_instances WHERE clutch_instance_code=:c LIMIT 1")
    with _eng().begin() as cx:
        return cx.execute(sql, {"c": clutch_code}).scalar()

def _load_detail_rows(clutch_code: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Treatments (rows) + optional annotation pivot for a selected clutch."""
    cid = _resolve_clutch_id(clutch_code)
    if not cid:
        return pd.DataFrame(), pd.DataFrame()

    with _eng().begin() as cx:
        if _exists_table(T_JCT):
            tdf = pd.read_sql(
                text(f"""
                    SELECT created_at,
                           treatment_type  AS tx_type,
                           treatment_code  AS tx_code,
                           treatment_name  AS tx_name,
                           notes,
                           created_by
                    FROM {T_JCT}
                    WHERE clutch_instance_id = CAST(:cid AS uuid)
                    ORDER BY created_at DESC NULLS LAST
                """),
                cx, params={"cid": cid}
            )
        else:
            tdf = pd.DataFrame()

        ann_view = V_ANN if _exists_view(V_ANN) else (V_ANN_ALT if _exists_view(V_ANN_ALT) else None)
        if ann_view:
            ap = pd.read_sql(
                text(f"""
                    SELECT * FROM {ann_view}
                    WHERE clutch_code = (SELECT clutch_instance_code FROM {T_CLUTCH} WHERE id=CAST(:cid AS uuid))
                    LIMIT 1
                """),
                cx, params={"cid": cid}
            )
        else:
            ap = pd.DataFrame()

    for df in (tdf, ap):
        if not df.empty:
            for c in df.select_dtypes(include="object").columns:
                df[c] = df[c].astype("string").fillna("")
    return tdf, ap

# --- filters ------------------------------------------------------------------
with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1: d_from = st.date_input("From", value=today - timedelta(days=60))
    with c2: d_to   = st.date_input("To",   value=today + timedelta(days=7))
    with c3: who    = st.text_input("Created by (plan/instance)", "")
    with c4: qtxt   = st.text_input("Search (CI/CR/cross/clutch/genotype/treatments)", "")
    c5, c6 = st.columns([1, 1])
    with c5: most_recent = st.checkbox("Most recent (ignore dates)", value=False)
    with c6: lim = st.number_input("Limit", min_value=1, max_value=1000, value=500, step=50)
    st.form_submit_button("Apply", use_container_width=True)

# toggle (client-side display only)
if hasattr(st, "segmented_control"):
    show_txg_fmt = st.segmented_control(
        "Tx → Genotype display", options=["codes", "names", "fusions"], default="codes", key="txg_fmt"
    )
else:
    show_txg_fmt = st.selectbox("Tx → Genotype display", ["codes", "names", "fusions"], index=0, key="txg_fmt")

# --- data loader --------------------------------------------------------------
def _load_clutches(show_txg_fmt: str) -> pd.DataFrame:
    for obj in (V_CLUTCH, T_CLUTCH, T_CROSSES, V_TPAIRS):
        ok = _exists_view(obj) if obj.startswith("public.v_") else _exists_table(obj)
        if not ok:
            st.error(f"Required object not found: {obj}"); st.stop()

    where, params = [], {}
    if not most_recent:
        where.append("v.created_at_instance::date BETWEEN :d1 AND :d2")
        params.update({"d1": d_from, "d2": d_to})
    if who.strip():
        where.append("COALESCE(v.created_by_instance,'') ILIKE :by")
        params["by"] = f"%{who.strip()}%"
    if qtxt.strip():
        params["q"] = f"%{qtxt.strip()}%"
        where.append("""
          (
            v.clutch_code ILIKE :q OR
            v.cross_name_pretty ILIKE :q OR
            COALESCE(x.cross_run_code,'') ILIKE :q OR
            COALESCE(tp.mom_fish_code,'') ILIKE :q OR
            COALESCE(tp.dad_fish_code,'') ILIKE :q OR
            COALESCE(tp.mom_genotype,'') ILIKE :q OR
            COALESCE(tp.dad_genotype,'') ILIKE :q OR
            COALESCE(v.clutch_genotype_codes,'') ILIKE :q OR
            COALESCE(v.clutch_genotype_tokens,'') ILIKE :q OR
            COALESCE(v.clutch_genotype_fusions,'') ILIKE :q OR
            COALESCE(v.clutch_treatments_codes,'') ILIKE :q OR
            COALESCE(v.clutch_treatments_names,'') ILIKE :q OR
            COALESCE(v.clutch_treatments_fusions,'') ILIKE :q OR
            COALESCE(v.clutch_lineage_pretty,'') ILIKE :q OR
            COALESCE(v.clutch_lineage_fusions_pretty,'') ILIKE :q OR
            COALESCE(v.clutch_lineage_full_fusions_pretty,'') ILIKE :q OR
            COALESCE(v.clutch_lineage_tokens_pretty,'') ILIKE :q OR
            COALESCE(v.clutch_lineage_codes_to_fusions_pretty,'') ILIKE :q
          )
        """)

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    sql = text(f"""
      WITH ci_map AS (
        SELECT id AS clutch_id,
               clutch_instance_code AS clutch_code,
               cross_instance_id
        FROM {T_CLUTCH}
      )
      SELECT
        v.clutch_code,
        v.clutch_birthday,

        -- parents
        CONCAT(COALESCE(tp.mom_fish_code,''), ' × ', COALESCE(tp.dad_fish_code,'')) AS cross_parents_codes_pretty,
        CONCAT(COALESCE(tp.mom_genotype,''),  ' × ', COALESCE(tp.dad_genotype,''))  AS cross_parents_genotypes_pretty,

        -- offspring (codes / fusions / tokens)
        v.clutch_genotype_codes,
        v.clutch_genotype_fusions,
        v.clutch_genotype_tokens,

        -- treatments
        v.clutch_treatments_codes,
        v.clutch_treatments_names,
        v.clutch_treatments_fusions,

        -- lineage (explicit from the view)
        v.clutch_lineage_pretty                  AS tx_to_geno_codes,
        v.clutch_lineage_fusions_pretty          AS tx_to_geno_fusions,
        v.clutch_lineage_full_fusions_pretty     AS tx_to_geno_full_fusions,
        v.clutch_lineage_tokens_pretty           AS tx_to_geno_tokens,
        v.clutch_lineage_codes_to_fusions_pretty AS tx_codes_to_geno_fusions,

        -- client-side display sources
        v.clutch_genotype_codes     AS _tgt_codes,
        v.clutch_genotype_fusions   AS _tgt_fusions,
        v.clutch_treatments_codes   AS _tx_codes,
        v.clutch_treatments_names   AS _tx_names,
        v.clutch_treatments_fusions AS _tx_fusions,

        COALESCE(v.treatments_count_effective,0)::int AS treatments_count_effective,
        v.created_by_instance,
        v.created_at_instance,
        x.cross_run_code

      FROM {V_CLUTCH} v
      LEFT JOIN ci_map m  ON m.clutch_code = v.clutch_code
      LEFT JOIN {T_CROSSES} x ON x.id = m.cross_instance_id
      LEFT JOIN {V_TPAIRS}  tp ON tp.tank_pair_code = x.tank_pair_code
      {where_sql}
      ORDER BY v.created_at_instance DESC NULLS LAST, v.clutch_code
      LIMIT :lim
    """)
    params["lim"] = int(lim)

    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    # strings → string dtype & nulls
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")

    # client-side convenience display
    if show_txg_fmt == "codes":
        tx, ge = df["_tx_codes"], df["_tgt_codes"]
    elif show_txg_fmt == "names":
        tx, ge = df["_tx_names"], df["_tgt_codes"]
    else:
        tx, ge = df["_tx_fusions"], df["_tgt_fusions"].fillna(df["_tgt_codes"])
    df["tx_to_geno_display"] = tx.where(tx.eq(""), tx + " > " + ge)

    return df

df = _load_clutches(show_txg_fmt)
st.caption(f"{len(df)} clutch instance(s)")
if df.empty:
    st.info("No clutch instances with the current filters."); st.stop()

# --- main grid ----------------------------------------------------------------
cols = [
    "clutch_code", "clutch_birthday",
    "cross_parents_codes_pretty", "cross_parents_genotypes_pretty",
    "clutch_genotype_codes", "clutch_genotype_fusions", "clutch_genotype_tokens",
    "clutch_treatments_codes", "clutch_treatments_names", "clutch_treatments_fusions",
    "tx_codes_to_geno_fusions", "tx_to_geno_codes", "tx_to_geno_fusions", "tx_to_geno_full_fusions",
    "tx_to_geno_tokens", "tx_to_geno_display",
    "treatments_count_effective",
]
for c in cols:
    if c not in df.columns:
        df[c] = ""

grid_src = df[cols].copy()
if "✓ Select" not in grid_src.columns:
    grid_src.insert(0, "✓ Select", False)

st.subheader("Clutch instances")
grid = st.data_editor(
    grid_src,
    hide_index=True, width="stretch", num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True, format="YYYY-MM-DD"),
        "cross_parents_codes_pretty":     st.column_config.TextColumn("Parents (codes)", disabled=True),
        "cross_parents_genotypes_pretty": st.column_config.TextColumn("Parents (genotypes)", disabled=True),
        "clutch_genotype_codes":   st.column_config.TextColumn("Offspring genotype (codes)", disabled=True),
        "clutch_genotype_fusions": st.column_config.TextColumn("Offspring genotype (fusions)", disabled=True),
        "clutch_genotype_tokens":  st.column_config.TextColumn("Offspring genotype (tokens)", disabled=True),
        "clutch_treatments_codes":   st.column_config.TextColumn("Tx (codes)", disabled=True),
        "clutch_treatments_names":   st.column_config.TextColumn("Tx (names)", disabled=True),
        "clutch_treatments_fusions": st.column_config.TextColumn("Tx (fusions)", disabled=True),
        "tx_codes_to_geno_fusions":  st.column_config.TextColumn("Tx(codes) → Genotype (fusions)", disabled=True),
        "tx_to_geno_codes":          st.column_config.TextColumn("Tx → Genotype (codes)", disabled=True),
        "tx_to_geno_fusions":        st.column_config.TextColumn("Tx(fusions) → Genotype (codes)", disabled=True),
        "tx_to_geno_full_fusions":   st.column_config.TextColumn("Tx(fusions) → Genotype (fusions)", disabled=True),
        "tx_to_geno_tokens":         st.column_config.TextColumn("Tx → Genotype (tokens)", disabled=True),
        "tx_to_geno_display":        st.column_config.TextColumn("Tx → Genotype (display)", disabled=True),
        "treatments_count_effective": st.column_config.NumberColumn("n treatments", format="%d", step=1, disabled=True),
    },
    key="overview_ci_parents_offspring_v3",
)

sel_mask = grid.get("✓ Select", pd.Series(False, index=grid.index)).fillna(False).astype(bool)
picked_codes = grid.loc[sel_mask, "clutch_code"].tolist()
picked = df[df["clutch_code"].isin(picked_codes)].reset_index(drop=True)

st.subheader("Details")
if picked.empty:
    st.info("Select a row above to view linked details."); st.stop()

row = picked.iloc[0]
code = row.get("clutch_code", "")
st.caption(f"Clutch: {code}")

def kv(label: str, value) -> dict[str, str]:
    s = "" if value is None else (value.strip() if isinstance(value, str) else str(value))
    return {"Field": label, "Value": s}

summary = [
    kv("Clutch code", code),
    kv("Clutch birthday", row.get("clutch_birthday")),
    kv("Parents (codes)", row.get("cross_parents_codes_pretty")),
    kv("Parents (genotypes)", row.get("cross_parents_genotypes_pretty")),
    kv("Offspring genotype (codes)",   row.get("clutch_genotype_codes")),
    kv("Offspring genotype (fusions)", row.get("clutch_genotype_fusions")),
    kv("Offspring genotype (tokens)",  row.get("clutch_genotype_tokens")),
    kv("Tx (codes)",   row.get("clutch_treatments_codes")),
    kv("Tx (names)",   row.get("clutch_treatments_names")),
    kv("Tx (fusions)", row.get("clutch_treatments_fusions")),
    kv("Tx(codes) → Genotype (fusions)",  row.get("tx_codes_to_geno_fusions")),
    kv("Tx(fusions) → Genotype (codes)",  row.get("tx_to_geno_fusions")),
    kv("Tx(fusions) → Genotype (fusions)",row.get("tx_to_geno_full_fusions")),
    kv("Tx(codes) → Genotype (tokens)",   row.get("tx_to_geno_tokens")),
    kv("Tx(codes) → Genotype (codes)",    row.get("tx_to_geno_codes")),
    kv("Tx → Genotype (display)",         row.get("tx_to_geno_display")),
    kv("n treatments",  row.get("treatments_count_effective")),
]
summary_df = pd.DataFrame([d for d in summary if d["Value"] not in ("", "None")])

cA, cB = st.columns([1, 1])
with cA:
    st.markdown("**Clutch summary (pivot)**")
    st.dataframe(summary_df, hide_index=True, use_container_width=True)

with cB:
    st.markdown("**Annotations (pivot)**")
    ann_view = V_ANN if _exists_view(V_ANN) else (V_ANN_ALT if _exists_view(V_ANN_ALT) else None)
    if ann_view:
        with _eng().begin() as cx:
            ap = pd.read_sql(text(f"SELECT * FROM {ann_view} WHERE clutch_code=:c LIMIT 1"), cx, params={"c": code})
    else:
        ap = pd.DataFrame()
    if ap.empty:
        st.caption("No annotation values.")
    else:
        melt_cols = [c for c in ap.columns if c != "clutch_code"]
        long = ap.melt(id_vars=[], value_vars=melt_cols, var_name="Field", value_name="Value")
        long = long[long["Value"].notna() & (long["Value"].astype(str).str.strip() != "")]
        st.dataframe(long, hide_index=True, use_container_width=True)

st.markdown("---")
st.markdown("**Treatments (rows)**")
tdf, _ = _load_detail_rows(code)
if tdf.empty:
    st.info("No treatments linked.")
else:
    st.dataframe(tdf, hide_index=True, use_container_width=True)