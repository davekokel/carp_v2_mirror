# =============================================================================
# 🔎 Overview — Clutch treatments (parents + offspring genotype, pivot drilldown)
#   Uses verified objects in your DB:
#     • public.v_clutch_instances  (enriched clutch fields)
#     • public.clutch_instances
#     • public.crosses
#     • public.v_tank_pairs        (parents codes/genotypes)
#     • (optional) public.v_clutch_annotations_pivot
#   Shows side-by-side:
#     • Cross (parents): mom × dad (codes), mom × dad (genotypes)
#     • Clutch (offspring): genotype codes ; genotype fusions
#     • Tx → Genotype (codes/fusions) + a display column via toggle
#   Drill-down pivot:
#     • Clutch summary (pivot) — key/value listing of linked fields
#     • Annotations (pivot) — if v_clutch_annotations_pivot exists
# =============================================================================
from __future__ import annotations
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy import text as _sql

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine as _create_engine

# ── Auth / page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()
st.set_page_config(page_title="🔎 Overview — Clutch treatments", page_icon="🐣", layout="wide")
st.title("🔎 Overview — Clutch treatments")

# ── Engine (cached) ──────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _eng() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

# ── Config ───────────────────────────────────────────────────────────────────
V_CLUTCH    = "public.v_clutch_instances"   # enriched clutch view (verified)
T_CLUTCH    = "public.clutch_instances"     # verified
T_CROSSES   = "public.crosses"              # verified
V_TANKPAIRS = "public.v_tank_pairs"         # verified
CLUTCH_LINK = "public.join_clutch_treatments"
ANNOT_TABLE = "public.clutch_instance_annotations"  # optional
V_ANN_PIVOT = "public.v_clutch_annotations_pivot"  # optional

# ── Helpers ──────────────────────────────────────────────────────────────────
def _exists_view(qualified: str) -> bool:
    sch, name = qualified.split(".", 1)
    q = _sql("""
      SELECT 1 FROM information_schema.views WHERE table_schema=:s AND table_name=:n
      UNION ALL
      SELECT 1 FROM pg_catalog.pg_matviews WHERE schemaname=:s AND matviewname=:n
      LIMIT 1
    """)
    with _eng().begin() as cx:
        return cx.execute(q, {"s": sch, "n": name}).first() is not None

def _exists_table(qualified: str) -> bool:
    sch, name = qualified.split(".", 1)
    q = _sql("""
      SELECT 1 FROM information_schema.tables WHERE table_schema=:s AND table_name=:n LIMIT 1
    """)
    with _eng().begin() as cx:
        return cx.execute(q, {"s": sch, "n": name}).first() is not None

def _resolve_clutch_instance_id(clutch_code: str) -> str | None:
    sql = text("""
      SELECT id::text
      FROM public.clutch_instances
      WHERE clutch_instance_code = :code
      LIMIT 1
    """)
    with _eng().begin() as cx:
        row = cx.execute(sql, {"code": clutch_code}).scalar()
    return row or None

def _load_detail_rows(clutch_code: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    cid = _resolve_clutch_instance_id(clutch_code)
    if not cid:
        return pd.DataFrame(), pd.DataFrame()
    tdf = pd.DataFrame(columns=["created_at","treatment_type","treatment_code","treatment_name","notes","created_by"])
    adf = pd.DataFrame(columns=["created_at","note","created_by"])
    with _eng().begin() as cx:
        if _exists_table(CLUTCH_LINK):
            tdf = pd.read_sql(text(f"""
              SELECT created_at, treatment_type, treatment_code, treatment_name, notes, created_by
              FROM {CLUTCH_LINK}
              WHERE clutch_instance_id = CAST(:cid AS uuid)
              ORDER BY created_at DESC NULLS LAST
            """), cx, params={"cid": cid})
        if _exists_table(ANNOT_TABLE):
            adf = pd.read_sql(text(f"""
              SELECT created_at, note, created_by
              FROM {ANNOT_TABLE}
              WHERE clutch_instance_id = CAST(:cid AS uuid)
              ORDER BY created_at DESC NULLS LAST
            """), cx, params={"cid": cid})
    for df in (tdf, adf):
        for c in df.select_dtypes(include=["object"]).columns:
            df[c] = df[c].astype("string").fillna("")
    return tdf, adf

def _safe(s) -> str:
    return "" if s is None else str(s).strip()

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1, c2, c3, c4 = st.columns([1,1,1,2])
    with c1: d_from = st.date_input("From", value=today - timedelta(days=60))
    with c2: d_to   = st.date_input("To",   value=today + timedelta(days=7))
    with c3: who    = st.text_input("Created by (plan/instance)", value="")
    with c4: qtxt   = st.text_input("Search (CI/CR/cross/clutch/genotype/treatments)", value="")
    c5, c6 = st.columns([1,1])
    with c5: most_recent = st.checkbox("Most recent only (ignore dates)", value=False)
    with c6: lim = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
    _ = st.form_submit_button("Apply", width="stretch")

# Toggle (codes / names / fusions) for Tx→Genotype display
if hasattr(st, "segmented_control"):
    SHOW_TXG_FORMAT = st.segmented_control(
        "Tx → Genotype display format", options=["codes","names","fusions"], default="codes", key="ov_txg_format"
    )
else:
    SHOW_TXG_FORMAT = st.selectbox(
        "Tx → Genotype display format", options=["codes","names","fusions"], index=0, key="ov_txg_format"
    )

# ── Data loader (only verified objects) ──────────────────────────────────────
def _load_clutches_compact() -> pd.DataFrame:
    # required sources
    if not _exists_view(V_CLUTCH):
        st.error(f"Required view {V_CLUTCH} not found."); st.stop()
    if not (_exists_table(T_CLUTCH) and _exists_table(T_CROSSES) and _exists_view(V_TANKPAIRS)):
        st.error("Required sources for cross parents are missing (clutch_instances, crosses, v_tank_pairs)."); st.stop()

    where, params = [], {}
    if not most_recent:
        where.append("v.created_at_instance::date BETWEEN :d1 AND :d2")
        params.update({"d1": d_from, "d2": d_to})
    if _safe(who):
        where.append("COALESCE(v.created_by_instance,'') ILIKE :who")
        params["who"] = f"%{_safe(who)}%"
    if _safe(qtxt):
        params["q"] = f"%{_safe(qtxt)}%"
        where.append("""(
            v.clutch_code ILIKE :q OR
            v.cross_name_pretty ILIKE :q OR
            COALESCE(x.cross_run_code,'')              ILIKE :q OR
            COALESCE(tp.mom_fish_code,'')              ILIKE :q OR
            COALESCE(tp.dad_fish_code,'')              ILIKE :q OR
            COALESCE(tp.mom_genotype,'')               ILIKE :q OR
            COALESCE(tp.dad_genotype,'')               ILIKE :q OR
            COALESCE(v.clutch_genotype_codes,'')       ILIKE :q OR
            COALESCE(v.clutch_genotype_fusions,'')     ILIKE :q OR
            COALESCE(v.clutch_treatments_codes,'')     ILIKE :q OR
            COALESCE(v.clutch_treatments_names,'')     ILIKE :q OR
            COALESCE(v.clutch_treatments_fusions,'')   ILIKE :q OR
            COALESCE(v.clutch_lineage_pretty,'')       ILIKE :q OR
            COALESCE(v.clutch_lineage_fusions_pretty,'') ILIKE :q OR
            COALESCE(v.clutch_lineage_full_fusions_pretty,'') ILIKE :q
        )""")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    # Parents (codes/genotypes) via crosses → v_tank_pairs; plus enriched clutch fields
    sql = text(f"""
      WITH ci_map AS (
        SELECT id AS clutch_instance_id, clutch_instance_code AS clutch_code, cross_instance_id
        FROM public.clutch_instances
      )
      SELECT
        v.clutch_code,
        v.clutch_birthday,

        -- Cross (parents) — codes & genotypes (× between parents)
        CONCAT(COALESCE(tp.mom_fish_code,''), ' × ', COALESCE(tp.dad_fish_code,'')) AS cross_parents_codes_pretty,
        CONCAT(COALESCE(tp.mom_genotype,''),  ' × ', COALESCE(tp.dad_genotype,''))  AS cross_parents_genotypes_pretty,

        -- Clutch (offspring) genotype — codes & fusions (; within codes)
        v.clutch_genotype_codes,
        v.clutch_genotype_fusions,

        -- Treatments (labels)
        v.clutch_treatments_codes,
        v.clutch_treatments_names,
        v.clutch_treatments_fusions,

        -- Explicit Tx → Genotype fields from the view
        v.clutch_lineage_pretty               AS tx_to_geno_codes,
        v.clutch_lineage_fusions_pretty       AS tx_to_geno_fusions,

        -- carry sources to compose display column here
        v.clutch_genotype_codes    AS _geno_codes_src,
        v.clutch_genotype_fusions  AS _geno_fusions_src,
        v.clutch_treatments_codes  AS _tx_codes_src,
        v.clutch_treatments_names  AS _tx_names_src,
        v.clutch_treatments_fusions AS _tx_fusions_src,

        COALESCE(v.treatments_count_effective,0)::int AS treatments_count_effective,
        v.created_by_instance,
        v.created_at_instance,
        x.cross_run_code

      FROM {V_CLUTCH} v
      LEFT JOIN ci_map m ON m.clutch_code = v.clutch_code
      LEFT JOIN public.crosses       x  ON x.id = m.cross_instance_id
      LEFT JOIN public.v_tank_pairs  tp ON tp.tank_pair_code = x.tank_pair_code
      {where_sql}
      ORDER BY v.created_at_instance DESC NULLS LAST, v.clutch_code
      LIMIT :lim
    """)

    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={**params, "lim": lim})

    # Make strings safe
    for c in df.select_dtypes(include=["object"]).columns:
        df[c] = df[c].astype("string").fillna("")

    # Compose the display column with the intended sources
    if SHOW_TXG_FORMAT == "codes":
        tx = df["_tx_codes_src"]
        ge = df["_geno_codes_src"]
        df["tx_to_geno_display"] = tx.where(tx.eq(""), tx + " > ") + ge
    elif SHOW_TXG_FORMAT == "names":
        tx = df["_tx_names_src"]
        ge = df["_geno_codes_src"]  # keep genotype in codes for 'names' mode
        df["tx_to_geno_display"] = tx.where(tx.eq(""), tx + " > ") + ge
    else:  # fusions
        tx = df["_tx_fusions_src"]
        ge = df["_geno_fusions_src"].fillna(df["_geno_codes_src"])
        df["tx_to_geno_display"] = tx.where(tx.eq(""), tx + " > ") + ge

    return df

# ── Main table (parents + offspring + tx→geno) ───────────────────────────────
df = _load_clutches_compact()
st.caption(f"{len(df)} clutch instance(s)")

if df.empty:
    st.info("No clutch instances with the current filters."); st.stop()

cols = [
    "clutch_code",
    "clutch_birthday",
    # Cross (parents)
    "cross_parents_codes_pretty",
    "cross_parents_genotypes_pretty",
    # Offspring (clutch)
    "clutch_genotype_codes",
    "clutch_genotype_fusions",
    # Treatments
    "clutch_treatments_codes",
    "clutch_treatments_names",
    "clutch_treatments_fusions",
    # Tx→Genotype explicit + display
    "tx_to_geno_codes",
    "tx_to_geno_fusions",
    "tx_to_geno_display",
    # Count
    "treatments_count_effective",
]
for c in cols:
    if c not in df.columns: df[c] = ""

grid_src = df[cols].copy()
grid_src.insert(0, "✓ Select", False)

st.subheader("Clutch instances")
grid = st.data_editor(
    grid_src,
    hide_index=True,
    width="stretch",
    num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
        "clutch_birthday": st.column_config.DateColumn("clutch_birthday", disabled=True, format="YYYY-MM-DD"),
        # Cross (parents)
        "cross_parents_codes_pretty":     st.column_config.TextColumn("Parents (codes)",     disabled=True),
        "cross_parents_genotypes_pretty": st.column_config.TextColumn("Parents (genotypes)", disabled=True),
        # Offspring (clutch)
        "clutch_genotype_codes":          st.column_config.TextColumn("Offspring genotype (codes)",   disabled=True),
        "clutch_genotype_fusions":        st.column_config.TextColumn("Offspring genotype (fusions)", disabled=True),
        # Tx labels
        "clutch_treatments_codes":        st.column_config.TextColumn("Tx (codes)",   disabled=True),
        "clutch_treatments_names":        st.column_config.TextColumn("Tx (names)",   disabled=True),
        "clutch_treatments_fusions":      st.column_config.TextColumn("Tx (fusions)", disabled=True),
        # Tx→Genotype explicit + display
        "tx_to_geno_codes":               st.column_config.TextColumn("Tx → Genotype (codes)",   disabled=True),
        "tx_to_geno_fusions":             st.column_config.TextColumn("Tx → Genotype (fusions)", disabled=True),
        "tx_to_geno_display":             st.column_config.TextColumn("Tx → Genotype (display)", disabled=True),
        # Count
        "treatments_count_effective":     st.column_config.NumberColumn("n treatments", disabled=True),
    },
    key="overview_ci_parents_offspring_v1",
)

sel_mask = grid.get("✓ Select", pd.Series(False, index=grid.index)).fillna(False).astype(bool)
picked_codes = grid_src.loc[sel_mask, "clutch_code"].tolist()
picked = df[df["clutch_code"].isin(picked_codes)].reset_index(drop=True)

# ── Drill-down pivot panels ──────────────────────────────────────────────────
st.subheader("Details")
if picked.empty:
    st.info("Select a row above to view linked treatments and annotations.")
else:
    row = picked.iloc[0]
    code = row.get("clutch_code", "")
    st.caption(f"Clutch: {code}")

    # ---- Clutch summary (pivot) ----
    def _kv(label: str, value: str) -> dict[str,str]:
        v = "" if value is None else str(value).strip()
        return {"Field": label, "Value": v}

    summary_items = [
        _kv("Clutch code", code),
        _kv("Clutch birthday", row.get("clutch_birthday")),
        _kv("Parents (codes)", row.get("cross_parents_codes_pretty")),
        _kv("Parents (genotypes)", row.get("cross_parents_genotypes_pretty")),
        _kv("Offspring genotype (codes)", row.get("clutch_genotype_codes")),
        _kv("Offspring genotype (fusions)", row.get("clutch_genotype_fusions")),
        _kv("Tx (codes)", row.get("clutch_treatments_codes")),
        _kv("Tx (names)", row.get("clutch_treatments_names")),
        _kv("Tx (fusions)", row.get("clutch_treatments_fusions")),
        _kv("Tx → Genotype (codes)", row.get("tx_to_geno_codes")),
        _kv("Tx → Genotype (fusions)", row.get("tx_to_geno_fusions")),
        _kv("Tx → Genotype (display)", row.get("tx_to_geno_display")),
        _kv("n treatments", row.get("treatments_count_effective")),
        _kv("Created by", row.get("created_by_instance")),
        _kv("Created at", row.get("created_at_instance")),
    ]
    summary_df = pd.DataFrame([d for d in summary_items if d["Value"] not in (None, "", "None")])

    cA, cB = st.columns([1,1])
    with cA:
        st.markdown("**Clutch summary (pivot)**")
        if summary_df.empty:
            st.info("No summary values.")
        else:
            st.dataframe(summary_df, hide_index=True, use_container_width=True)

    # ---- Treatments (list) + Annotations (pivot) ----
    tdf, _adf_unused = _load_detail_rows(code)

    with cB:
        st.markdown("**Annotations (pivot)**")
        if _exists_view(V_ANN_PIVOT):
            with _eng().begin() as cx:
                ap = pd.read_sql(text(f"""
                  SELECT * FROM {V_ANN_PIVOT} WHERE clutch_code = :c LIMIT 1
                """), cx, params={"c": code})
            if ap.empty:
                st.caption("No annotation values.")
            else:
                melt_cols = [c for c in ap.columns if c != "clutch_code"]
                long = ap.melt(id_vars=[], value_vars=melt_cols, var_name="Field", value_name="Value")
                long = long[long["Value"].notna() & (long["Value"].astype(str).str.strip() != "")]
                if long.empty:
                    st.caption("No annotation values.")
                else:
                    st.dataframe(long, hide_index=True, use_container_width=True)
        else:
            st.caption("v_clutch_annotations_pivot not installed.")

    # Existing panels below the pivot
    st.markdown("---")
    st.markdown("**Treatments (rows)**")
    if tdf.empty:
        st.info("No treatments linked.")
    else:
        st.dataframe(tdf, width="stretch", hide_index=True)