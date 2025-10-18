from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date, timedelta
from typing import List, Dict

import pandas as pd
import streamlit as st
from sqlalchemy import text

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.lib.config import engine as get_engine

# --- auth ---
sb, session, user = require_auth()
require_email_otp()

# --- page config ---
st.set_page_config(page_title="🧬 Select fish pairings", page_icon="🧬", layout="wide")
st.title("🧬 Select fish pairings")

# --- optional unlock ---
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

# --- db engine ---
_ENGINE = None
def _get_engine():
    global _ENGINE
    if _ENGINE: return _ENGINE
    if not os.getenv("DB_URL"):
        st.error("DB_URL not set"); st.stop()
    _ENGINE = get_engine()
    return _ENGINE

LIVE_STATUSES = ("active","new_tank")
TANK_TYPES    = ("inventory_tank","holding_tank","nursery_tank")

# ---------------- helpers: concepts ----------------
def _load_clutch_concepts(d1: date, d2: date, created_by: str, q: str) -> pd.DataFrame:
    sql = text("""
    WITH mom_live AS (
      SELECT f.fish_code, COUNT(*)::int AS n_live
      FROM public.fish f
      JOIN public.fish_tank_memberships m ON m.fish_id = f.id AND m.left_at IS NULL
      JOIN public.containers c           ON c.id = m.container_id
      WHERE c.status = ANY(:live_statuses) AND c.container_type = ANY(:tank_types)
      GROUP BY f.fish_code
    ),
    dad_live AS (
      SELECT f.fish_code, COUNT(*)::int AS n_live
      FROM public.fish f
      JOIN public.fish_tank_memberships m ON m.fish_id = f.id AND m.left_at IS NULL
      JOIN public.containers c           ON c.id = m.container_id
      WHERE c.status = ANY(:live_statuses) AND c.container_type = ANY(:tank_types)
      GROUP BY f.fish_code
    ),
    tx_counts AS (
      SELECT clutch_id, COUNT(*)::int AS n_treatments
      FROM public.clutch_plan_treatments
      GROUP BY clutch_id
    )
    SELECT
      cp.id::text                          AS clutch_id,
      COALESCE(cp.clutch_code, cp.id::text) AS clutch_code,
      COALESCE(cp.planned_name,'')         AS planned_name,
      COALESCE(cp.planned_nickname,'')     AS planned_nickname,
      cp.mom_code, cp.dad_code,
      COALESCE(ml.n_live,0)                AS mom_live,
      COALESCE(dl.n_live,0)                AS dad_live,
      (COALESCE(ml.n_live,0)*COALESCE(dl.n_live,0))::int AS pairings,
      COALESCE(tx.n_treatments,0)          AS n_treatments,
      cp.created_by, cp.created_at
    FROM public.clutch_plans cp
    LEFT JOIN mom_live ml ON ml.fish_code = cp.mom_code
    LEFT JOIN dad_live dl ON dl.fish_code = cp.dad_code
    LEFT JOIN tx_counts tx ON tx.clutch_id = cp.id
    WHERE (cp.created_at::date BETWEEN :d1 AND :d2)
      AND (:by = '' OR cp.created_by ILIKE :byl)
      AND (
        :q = '' OR
        COALESCE(cp.clutch_code,'') ILIKE :ql OR
        COALESCE(cp.planned_name,'') ILIKE :ql OR
        COALESCE(cp.planned_nickname,'') ILIKE :ql OR
        COALESCE(cp.mom_code,'') ILIKE :ql OR
        COALESCE(cp.dad_code,'') ILIKE :ql
      )
    ORDER BY cp.created_at DESC
    """)
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params={
            "live_statuses": list(LIVE_STATUSES),
            "tank_types": list(TANK_TYPES),
            "d1": d1, "d2": d2,
            "by": created_by or "", "byl": f"%{created_by or ''}%",
            "q": q or "", "ql": f"%{q or ''}%"
        })

# ---------------- genotype token helpers ----------------
def _norm(s: str) -> str:
    import re
    s = (s or "").lower()
    s = s.replace("tg[","tg(").replace("]",")")
    s = s.replace("–","-").replace("—","-").replace("·",":").replace("•",":")
    s = re.sub(r"\s+"," ",s)
    return s.strip()

def _extract_match_tokens(plans_df: pd.DataFrame) -> dict:
    """Return genotype/strain tokens from planned_name/nickname."""
    import re
    texts = []
    for col in ("planned_name","planned_nickname"):
        if col in plans_df.columns:
            texts += plans_df[col].dropna().astype(str).tolist()
    blob = " ".join(texts); U = blob.upper()
    STOP = {"RNA","MRNA","SGRNA","CAS9","PLASMID","VECTOR","MORPHOLINO","MO","DYE",
            "INJECT","INJECTION","TREAT","DOSE","EXPOSE","TRICAINE",
            "UG","µG","MG/ML","NM","µM","UM","%","H","HPF","DPF","WATER","BUFFER"}
    toks = set()
    # canonical chunks
    for m in re.findall(r"Tg[\[\(][A-Za-z0-9:_\-]+[\]\)]\d+", blob): toks.add(_norm(m))
    for m in re.findall(r"[A-Za-z0-9:_\-]+:[A-Za-z0-9:_\-]+", blob):   toks.add(_norm(m))
    for m in re.findall(r"[A-Za-z0-9:_\-]+\^[A-Za-z0-9:_\-]+", blob):  toks.add(_norm(m))
    # compact codes
    for m in re.findall(r"[A-Za-z0-9]{3,}[-_:]?[0-9]{2,3}", blob):     toks.add(_norm(m))
    toks = {t for t in toks if t.upper() not in STOP}
    strain = set()
    for s in ["CASPER","AB","TU","TL","WIK","EK","NACRE","ROY"]:
        if s in U: strain.add(s.lower())
    return {"geno": sorted(toks), "strain": sorted(strain)}

def _tokenize_geno_bg(text: str) -> set:
    import re
    t = _norm(text)
    parts = set()
    parts.update(re.findall(r"tg\([a-z0-9:_\-]+\)\d+", t))
    parts.update(re.findall(r"[a-z0-9:_\-]+:[a-z0-9:_\-]+", t))
    parts.update(re.findall(r"[a-z0-9:_\-]+\^[a-z0-9:_\-]+", t))
    parts.update([p for p in re.split(r"[;\|,/\s]+", t) if len(p) >= 3])
    return parts

def _match_any(geno: str, bg: str, tokens: dict) -> tuple[bool, list]:
    """Return (matches?, hit_list) if any genotype element OR strain matches."""
    bag = _tokenize_geno_bg((geno or "") + " " + (bg or ""))
    req = tokens.get("geno", [])
    hits = [t for t in req if t in bag]
    strain_hits = [s for s in tokens.get("strain", []) if s in bag]
    hits_all = list(dict.fromkeys(hits + strain_hits))
    return (len(hits_all) > 0), hits_all

def _fetch_fish_genotypes_and_bg(codes: List[str]) -> Dict[str, Dict[str,str]]:
    if not codes: return {}
    uniq = list({c for c in codes if c})
    with _get_engine().begin() as cx:
        # prefer overview if available
        has_vw = bool(pd.read_sql(text("""
            select 1 from information_schema.tables
            where table_schema='public' and table_name='vw_fish_overview' limit 1
        """), cx).shape[0])
        if has_vw:
            df = pd.read_sql(text("""
                select fish_code,
                       coalesce(genotype,'') as genotype,
                       coalesce(genetic_background,'') as genetic_background
                from public.vw_fish_overview
                where fish_code = any(:codes)
            """), cx, params={"codes": uniq})
        else:
            cols = pd.read_sql(text("""
                select column_name from information_schema.columns
                where table_schema='public' and table_name='fish'
            """), cx)["column_name"].tolist()
            gcol = "genotype" if "genotype" in cols else None
            bcol = "genetic_background" if "genetic_background" in cols else None
            if gcol and bcol:
                sql = f"""select fish_code, coalesce({gcol},'') as genotype, coalesce({bcol},'') as genetic_background
                          from public.fish where fish_code = any(:codes)"""
            elif gcol:
                sql = f"""select fish_code, coalesce({gcol},'') as genotype, ''::text as genetic_background
                          from public.fish where fish_code = any(:codes)"""
            elif bcol:
                sql = f"""select fish_code, ''::text as genotype, coalesce({bcol},'') as genetic_background
                          from public.fish where fish_code = any(:codes)"""
            else:
                sql = """select fish_code, ''::text as genotype, ''::text as genetic_background
                         from public.fish where fish_code = any(:codes)"""
            df = pd.read_sql(text(sql), cx, params={"codes": uniq})
    return {r["fish_code"]: {"genotype": r.get("genotype","") or "",
                             "genetic_background": r.get("genetic_background","") or ""} for _, r in df.iterrows()}

# ---------------- filters form ----------------
with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1, c2, c3, c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=14))
    with c2: d2 = st.date_input("To", value=today)
    with c3: created_by = st.text_input("Created by", value=os.environ.get("USER") or os.environ.get("USERNAME") or "")
    with c4: q = st.text_input("Omni-search (code / name / nickname / mom / dad)", value="")
    st.form_submit_button("Apply", use_container_width=True)

plans = _load_clutch_concepts(d1, d2, created_by, q)
# genotype-only: hide plans with attached treatments
if "n_treatments" in plans.columns:
    plans = plans[plans["n_treatments"].fillna(0) == 0]

# ---------------- table 1: select concept ----------------
st.markdown("### 1) Select the clutch genotype you want to generate")
st.caption(f"{len(plans)} clutch concept(s). Showing genotype-only (no treatments).")

visible_cols = ["clutch_code","planned_name","planned_nickname","pairings","created_by","created_at"]
plan_df = plans.copy() if not plans.empty else pd.DataFrame(columns=visible_cols)
if "✓ Select" not in plan_df.columns:
    plan_df.insert(0,"✓ Select",False)

plan_table_key = f"plans_{d1}_{d2}_{created_by}_{q}"
plan_edited = st.data_editor(
    plan_df[["✓ Select"] + visible_cols],
    hide_index=True, use_container_width=True,
    column_order=["✓ Select"] + visible_cols,
    column_config={
        "✓ Select":  st.column_config.CheckboxColumn("✓", default=False),
        "pairings":  st.column_config.NumberColumn("pairings", disabled=True, width="small"),
        "created_at":st.column_config.DatetimeColumn("created_at", disabled=True),
    },
    key=plan_table_key,
)
sel_mask  = plan_edited.get("✓ Select", pd.Series(False, index=plan_edited.index)).fillna(False).astype(bool)
sel_plans = plan_df.loc[sel_mask].reset_index(drop=True)

# ---------------- Step 2: TWO TABLES (moms & dads), filtered by genotype elements OR strain ----------------
st.subheader("2) Choose FSH pairings (mother fish × father fish)")

if sel_plans.empty:
    st.info("Select a clutch genotype above to see parent candidates.")
    selected_moms = selected_dads = pd.DataFrame()
else:
    # live fish candidates
    sql_live_fish = text("""
        with live_counts as (
            select f.fish_code, count(*)::int as n_live
            from public.fish f
            join public.fish_tank_memberships m on m.fish_id=f.id and m.left_at is null
            join public.containers c on c.id=m.container_id
            where c.status = any(:live_statuses) and c.container_type = any(:tank_types)
            group by f.fish_code
        )
        select fish_code, n_live from live_counts order by fish_code
    """)
    with _get_engine().begin() as cx:
        live_fish = pd.read_sql(sql_live_fish, cx, params={"live_statuses": list(LIVE_STATUSES), "tank_types": list(TANK_TYPES)})

    tokens = _extract_match_tokens(sel_plans)
    token_caption = ", ".join(tokens["geno"] + tokens["strain"]) if (tokens["geno"] or tokens["strain"]) else "(none)"
    st.caption(f"Auto-filter tokens: {token_caption}")

    # enrich with genotype/background
    fish_pool = live_fish["fish_code"].astype(str).tolist()
    geno_map = _fetch_fish_genotypes_and_bg(fish_pool)
    live_fish["genotype"] = live_fish["fish_code"].map(lambda c: geno_map.get(c,{}).get("genotype",""))
    live_fish["genetic_background"] = live_fish["fish_code"].map(lambda c: geno_map.get(c,{}).get("genetic_background",""))

    # keep rows that match ANY genotype element OR strain
    def _keep_row(r) -> bool:
        ok, _ = _match_any(r.get("genotype",""), r.get("genetic_background",""), tokens)
        return ok

    # Moms table
    st.markdown("**Mother candidates** (match ≥1 genotype element or strain)")
    mf1, mf2 = st.columns([3,1])
    with mf1: mom_text = st.text_input("Filter mothers (contains)", value="")
    with mf2: mom_top  = st.number_input("Limit", min_value=10, max_value=1000, value=200, step=10, key="mom_limit")

    moms = live_fish.copy()
    moms = moms[moms.apply(_keep_row, axis=1)]
    if mom_text:
        moms = moms[moms["fish_code"].str.contains(mom_text, case=False, na=False) |
                    moms["genotype"].str.contains(mom_text, case=False, na=False) |
                    moms["genetic_background"].str.contains(mom_text, case=False, na=False)]
    moms = moms.head(int(mom_top)).reset_index(drop=True)
    if "✓ Select" not in moms.columns:
        moms.insert(0,"✓ Select",False)
    moms_view = moms[["✓ Select","fish_code","n_live","genotype","genetic_background"]].rename(
        columns={"fish_code":"mom_code","n_live":"#mom tanks","genetic_background":"mom background","genotype":"mom genotype"}
    )
    moms_edit = st.data_editor(
        moms_view, hide_index=True, use_container_width=True, num_rows="fixed",
        column_config={
            "✓ Select":     st.column_config.CheckboxColumn("✓", default=False),
            "mom_code":     st.column_config.TextColumn("mom FSH", disabled=True),
            "#mom tanks":   st.column_config.NumberColumn("#tanks", disabled=True, width="small"),
            "mom genotype": st.column_config.TextColumn("genotype", disabled=True, width="large"),
            "mom background": st.column_config.TextColumn("background", disabled=True),
        },
        key="moms_editor",
    )
    selected_moms = moms_edit[moms_edit["✓ Select"]].rename(columns={"mom_code":"fish_code"}).reset_index(drop=True)

    # Dads table
    st.markdown("**Father candidates** (match ≥1 genotype element or strain)")
    df1, df2 = st.columns([3,1])
    with df1: dad_text = st.text_input("Filter fathers (contains)", value="")
    with df2: dad_top  = st.number_input("Limit ", min_value=10, max_value=1000, value=200, step=10, key="dad_limit")

    dads = live_fish.copy()
    dads = dads[dads.apply(_keep_row, axis=1)]
    if dad_text:
        dads = dads[dads["fish_code"].str.contains(dad_text, case=False, na=False) |
                    dads["genotype"].str.contains(dad_text, case=False, na=False) |
                    dads["genetic_background"].str.contains(dad_text, case=False, na=False)]
    dads = dads.head(int(dad_top)).reset_index(drop=True)
    if "✓ Select" not in dads.columns:
        dads.insert(0,"✓ Select",False)
    dads_view = dads[["✓ Select","fish_code","n_live","genotype","genetic_background"]].rename(
        columns={"fish_code":"dad_code","n_live":"#dad tanks","genetic_background":"dad background","genotype":"dad genotype"}
    )
    dads_edit = st.data_editor(
        dads_view, hide_index=True, use_container_width=True, num_rows="fixed",
        column_config={
            "✓ Select":     st.column_config.CheckboxColumn("✓", default=False),
            "dad_code":     st.column_config.TextColumn("dad FSH", disabled=True),
            "#dad tanks":   st.column_config.NumberColumn("#tanks", disabled=True, width="small"),
            "dad genotype": st.column_config.TextColumn("genotype", disabled=True, width="large"),
            "dad background": st.column_config.TextColumn("background", disabled=True),
        },
        key="dads_editor",
    )
    selected_dads = dads_edit[dads_edit["✓ Select"]].rename(columns={"dad_code":"fish_code"}).reset_index(drop=True)

# ---------------- export/save selection (no DB writes) ----------------
st.markdown("### Save / Export selection")
if (isinstance(locals().get("selected_moms", None), pd.DataFrame) and not selected_moms.empty) and \
   (isinstance(locals().get("selected_dads", None), pd.DataFrame) and not selected_dads.empty):
    # Build mom×dad list for downstream use
    pairs = pd.DataFrame(
        [(m.fish_code, d.fish_code) for m in selected_moms.itertuples(index=False) for d in selected_dads.itertuples(index=False)],
        columns=["mom_code","dad_code"]
    )
    st.session_state["selected_fsh_pairs"] = pairs.to_dict("records")

    csv = pairs.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download selected FSH pairs (CSV)", data=csv,
                       file_name="selected_fish_pairs.csv", mime="text/csv", use_container_width=True)
else:
    st.info("Select at least one mother FSH and one father FSH above.")