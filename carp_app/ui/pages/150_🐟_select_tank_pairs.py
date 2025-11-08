# carp_app/ui/pages/150_🐟_select_tank_pairs.py
from __future__ import annotations
import sys, pathlib, os
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ---- path/auth bootstrap ----------------------------------------------------
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🧬 Select tank pairings", page_icon="🧬", layout="wide")
st.title("🧬 Select tank pairings")

# ---- engine -----------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL")
    if not url:
        raise RuntimeError("DB_URL not set")
    return get_engine()

def _eng() -> Engine:
    return _cached_engine()

# ---- helpers ----------------------------------------------------------------
def _tank_pair_parent_cols() -> Tuple[str, str]:
    with _eng().begin() as cx:
        cols = pd.read_sql(
            text("""
              select column_name
              from information_schema.columns
              where table_schema='public' and table_name='tank_pairs'
            """),
            cx,
        )["column_name"].tolist()
    for a, b in (("mother_tank_id","father_tank_id"),
                 ("tank_id_mother","tank_id_father")):
        if a in cols and b in cols:
            return a, b
    raise RuntimeError("public.tank_pairs must have mother/father tank UUID columns (e.g. mother_tank_id/father_tank_id).")

@st.cache_data(ttl=60, show_spinner=False)
def search_fish(q: Optional[str], limit: int) -> pd.DataFrame:
    """Pull fish from v_fish_unified and join active tank counts from v_tanks."""
    params = {"lim": limit}
    where = ""
    if q and q.strip():
        params["ql"] = f"%{q.strip()}%"
        where = """
          WHERE
              COALESCE(fish_code,'')          ILIKE :ql
           OR COALESCE(nickname,'')           ILIKE :ql
           OR COALESCE(genetic_background,'') ILIKE :ql
           OR COALESCE(genotype_pretty,'')    ILIKE :ql
        """
    sql = text(f"""
      WITH base AS (
        SELECT fish_code, nickname, genetic_background,
               line_building_stage, genotype_pretty, created_at
        FROM public.v_fish_unified
        {where}
        ORDER BY created_at DESC NULLS LAST, fish_code
        LIMIT :lim
      ),
      live AS (
        SELECT fish_code,
               COUNT(*)::int AS n_live,
               STRING_AGG(DISTINCT vt.tank_code, ', ' ORDER BY vt.tank_code) AS live_tanks
        FROM public.v_tanks vt
        WHERE LOWER(TRIM(status))='active'
        GROUP BY fish_code
      )
      SELECT b.fish_code, b.nickname AS name,
             b.genetic_background AS background,
             b.line_building_stage AS stage,
             b.genotype_pretty AS genotype,
             COALESCE(live.n_live,0) AS live_tanks,
             COALESCE(live.live_tanks,'') AS live_tank_codes
      FROM base b
      LEFT JOIN live USING (fish_code)
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return df.fillna("")

# IMPORTANT: do NOT cache — must reflect latest tank state for selected parents
def load_active_tanks_for_fish(codes: List[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame()
    sql = text("""
      SELECT
        vt.fish_code,
        vf.nickname                 AS fish_name,
        vf.genotype_pretty          AS genotype,
        vt.tank_code,
        vt.tank_uuid::text          AS tank_id,
        vt.status,
        vt.created_at
      FROM public.v_tanks vt
      LEFT JOIN public.v_fish_unified vf
        ON vf.fish_code = vt.fish_code
      WHERE vt.fish_code = ANY(:codes)
        AND LOWER(TRIM(vt.status))='active'
      ORDER BY vt.fish_code, vt.created_at DESC
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    return df.fillna("")

def upsert_tank_pair(mother_tank_id: str, father_tank_id: str, created_by: str, note: str) -> Tuple[bool, str]:
    mom_col, dad_col = _tank_pair_parent_cols()
    with _eng().begin() as cx:
        # discover actual columns on tank_pairs
        cols = set(pd.read_sql(
            text("""
                select column_name
                from information_schema.columns
                where table_schema='public' and table_name='tank_pairs'
            """),
            cx
        )["column_name"].tolist())

        # if an identical pair exists, update what we can and return its code
        row = pd.read_sql(
            text(f"""
              select id::text, tank_pair_code
              from public.tank_pairs
              where {mom_col} = :m and {dad_col} = :d
              limit 1
            """),
            cx, params={"m": mother_tank_id, "d": father_tank_id}
        )
        if not row.empty:
            sets = []
            params = {"id": row.iloc[0]["id"], "note": note, "by": created_by}
            if "updated_at" in cols:
                sets.append("updated_at = now()")
            if "note" in cols:
                sets.append("note = coalesce(nullif(:note,''), note)")
            if "updated_by" in cols:
                sets.append("updated_by = coalesce(nullif(:by,''), updated_by)")
            if sets:
                cx.execute(text(f"update public.tank_pairs set {', '.join(sets)} where id = :id::uuid"), params)
            return False, str(row.iloc[0]["tank_pair_code"])

        # build an INSERT only with columns that exist
        insert_cols: List[str] = [mom_col, dad_col]
        placeholders: List[str] = [":m", ":d"]
        params = {"m": mother_tank_id, "d": father_tank_id}

        if "created_by" in cols:
            insert_cols.append("created_by")
            placeholders.append(":by")
            params["by"] = created_by
        if "note" in cols:
            insert_cols.append("note")
            placeholders.append(":note")
            params["note"] = note
        if "status" in cols:
            insert_cols.append("status")
            placeholders.append(":st")
            params["st"] = "selected"
        if "created_at" in cols:
            # if created_at exists but no default, set it explicitly
            insert_cols.append("created_at")
            placeholders.append("now()")

        sql = text(f"""
            insert into public.tank_pairs({', '.join(insert_cols)})
            values ({', '.join(placeholders)})
            returning tank_pair_code
        """)
        tp_code = cx.execute(sql, params).scalar()
        return True, str(tp_code)

# ---- page -------------------------------------------------------------------
with st.form("filters"):
    c1, c2 = st.columns([3,1])
    with c1:
        q = st.text_input("Filter by code/name/nickname/background/genotype","")
    with c2:
        limit = int(st.number_input("Rows",1,2000,500,50))
    st.form_submit_button("Apply")

df = search_fish(q, limit)
if df.empty:
    st.info("No fish match filters."); st.stop()

# Step 1 — pick two parent fish
st.subheader("Step 1 — Select parents (from fish registry)")
view = df.copy()
view.insert(0, "✓ Parent", False)
pick = st.data_editor(
    view,
    key="parent_table",
    width="stretch",
    hide_index=True,
    column_config={
        "✓ Parent":  st.column_config.CheckboxColumn("✓", default=False),
        "fish_code": st.column_config.TextColumn("fish_code", disabled=True),
        "name":      st.column_config.TextColumn("name", disabled=True),
        "background":st.column_config.TextColumn("background", disabled=True),
        "stage":     st.column_config.TextColumn("stage", disabled=True),
        "genotype":  st.column_config.TextColumn("genotype", disabled=True),
        "live_tanks":st.column_config.NumberColumn("live tanks"),
        "live_tank_codes": st.column_config.TextColumn("live tank codes", disabled=True),
    },
)

parents = pick.loc[pick["✓ Parent"], "fish_code"].dropna().astype(str).tolist() if not pick.empty else []
parents = list(dict.fromkeys(parents))[:2]
if len(parents) < 2:
    st.info("Select two parents above to continue."); st.stop()

st.success(f"Selected parents: {parents[0]} × {parents[1]}")

# Step 2 — load both parents' active tanks (fresh each time)
st.subheader("Step 2 — Choose Mother and Father tanks (active only)")
live = load_active_tanks_for_fish(parents)
if live.empty:
    st.warning("No active tanks for selected parents."); st.stop()

# Mother candidates = ALL active tanks for BOTH fish
st.subheader("Mother")
m_candidates = live.copy()
m_candidates.insert(0, "✓ Mother", False)
m_sel = st.data_editor(
    m_candidates[["✓ Mother","fish_code","fish_name","genotype","tank_code","tank_id","status","created_at"]],
    key="mother_table", width="stretch", hide_index=True,
)
m_pick = m_sel.loc[m_sel["✓ Mother"]] if not m_sel.empty else pd.DataFrame()
if m_pick.empty:
    st.info("Pick a Mother tank to continue."); st.stop()

# Identify mother selection (fish & tank)
mother_row    = m_pick.iloc[0]
mother_fish   = str(mother_row["fish_code"])
mother_tank_id= str(mother_row["tank_id"])

# Father candidates = ALL remaining active tanks for the OTHER fish
other_fish = next(f for f in parents if f != mother_fish)
f_candidates = live[live["fish_code"] == other_fish].copy()
if f_candidates.empty:
    st.warning(f"No active tanks for father fish {other_fish}."); st.stop()

st.subheader("Father")
f_candidates.insert(0, "✓ Father", False)
f_sel = st.data_editor(
    f_candidates[["✓ Father","fish_code","fish_name","genotype","tank_code","tank_id","status","created_at"]],
    key="father_table", width="stretch", hide_index=True,
)
f_pick = f_sel.loc[f_sel["✓ Father"]] if not f_sel.empty else pd.DataFrame()
if f_pick.empty:
    st.info("Pick a Father tank to continue."); st.stop()

father_tank_id = str(f_pick.iloc[0]["tank_id"])
if mother_tank_id == father_tank_id:
    st.error("Mother and Father cannot be the same tank."); st.stop()

# Step 3 — save pairing
st.subheader("Step 3 — Save tank pairing")
creator = os.getenv("USER") or os.getenv("USERNAME") or "unknown"
note = st.text_input("Note (optional)","")

if st.button("💾 Save tank pairing", type="primary", use_container_width=True):
    ok, code = upsert_tank_pair(mother_tank_id, father_tank_id, creator, note)
    st.success(f"{'Created' if ok else 'Updated'} tank_pair {code}")