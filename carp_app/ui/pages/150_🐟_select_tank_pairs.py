# carp_app/ui/pages/150_🧬_select_tank_pairs.py
from __future__ import annotations
import sys, pathlib, os
from typing import List, Optional, Tuple
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ---- path/auth -----------------------------------------------------------
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🧬 FISH → Select tank pairings", page_icon="🧬", layout="wide")
st.title("🧬 Select tank pairings")

# ---- engine --------------------------------------------------------------
_ENGINE: Optional[Engine] = None
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL")
    if not url:
        raise RuntimeError("DB_URL not set")
    from carp_app.ui.lib.app_ctx import get_engine
    return get_engine()

def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = _cached_engine()
    return _ENGINE

# ---- helpers -------------------------------------------------------------
def _since_days(ts) -> Optional[float]:
    if not ts: return None
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None
    if ts.time() and ts.tz_offset is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - ts).total_seconds()/86400, 1)

def _tank_pair_parent_cols() -> Tuple[str, str]:
    with _eng().begin() as cx:
        cols = pd.read_sql(
            text("select column_name from information_schema.columns where table_schema='public' and table_name='tank_pairs'"),
            cx,
        )["column_name"].tolist()
    for a, b in (("mother_tank_id","father_tank_id"), ("tank_id_mother","tank_id_father")):
        if a in cols and b in cols:
            return a, b
    raise RuntimeError("public.tank_pairs must have mother/father UUID columns (mother_tank_id/father_tank_id or tank_id_*)")

# ---- data access ---------------------------------------------------------
@st.cache_data(ttl=60)
def search_fish(q: Optional[str], limit: int) -> pd.DataFrame:
    params = {"lim": int(limit)}
    where = ""
    if q and q.strip():
        params["ql"] = f"%{q.strip()}%"
        where = """
          WHERE
              COALESCE(fish_code,'')          ILIKE :ql
           OR COALESCE(nickname,'')           ILIKE :ql
           OR COALESCE(genetic_background,'') ILIKE :ql
           OR COALESCE(line_building_stage,'')ILIKE :ql
           OR COALESCE(genotype_pretty,'')    ILIKE :ql
        """
    sql = text(f"""
      WITH base AS (
        SELECT
          fish_code,
          COALESCE(nickname,'')            AS fish_name,
          COALESCE(nickname,'')            AS fish_nickname,
          COALESCE(genetic_background,'')  AS genetic_background,
          COALESCE(line_building_stage,'') AS line_building_stage,
          COALESCE(genotype_pretty,'')     AS genotype_pretty,
          COALESCE(created_at, now())      AS created_at
        FROM public.v_fish_unified
        {where}
        ORDER BY created_at DESC NULLS LAST, fish_code
        LIMIT :lim
      ),
      live AS (
        SELECT
          vt.fish_code::text AS fish_code,
          COUNT(*)::int      AS n_live,
          STRING_AGG(DISTINCT vt.tank_code, ', ' ORDER BY vt.tank_code) AS live_tanks
        FROM public.v_tanks vt
        WHERE vt.status = 'active'
        GROUP BY vt.fish_code
      )
      SELECT
        b.fish_code                         AS "fish_code",
        b.fish_name                         AS "name",
        b.fish_nickname                     AS "nickname",
        b.genetic_background                AS "background",
        b.line_building_stage               AS "stage",
        b.genotype_pretty                   AS "genotype",
        COALESCE(live.n_live,0)             AS "live_tanks",
        COALESCE(live.live_tanks,'')        AS "live_tank_codes",
        b.created_at                        AS "created_at"
      FROM base b
      LEFT JOIN live USING (fish_code)
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    for c in df.select_dtypes(["object","string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

@st.cache_data(ttl=60)
def load_active_tanks_for_fish(codes: List[str]) -> pd.DataFrame:
    codes = [c for c in (codes or []) if c]
    if not codes:
        return pd.DataFrame(columns=["fish_code","fish_name","genotype","tank_code","tank_id","status","created_at"])
    sql = text("""
      SELECT
        vt.fish_code,
        COALESCE(vf.nickname,'')            AS fish_name,
        COALESCE(vf.genotype_pretty,'')     AS genotype,
        vt.tank_code,
        vt.tank_uuid::text                  AS tank_id,
        vt.status::text                     AS status,
        vt.created_at
      FROM public.v_tanks vt
      LEFT JOIN public.v_fish_unified vf
        ON vf.fish_code = vt.fish_code
      WHERE vt.fish_code = ANY(:codes)
        AND vt.status = 'active'
      ORDER BY vt.fish_code, vt.created_at DESC NULLS LAST
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    for c in df.select_dtypes(["object","string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def upsert_tank_pair(mother_tank_id: str, father_tank_id: str, created_by: str, note: str) -> Tuple[bool, str]:
    mom_col, dad_col = _tank_pair_parent_cols()
    with _eng().begin() as cx:
        # if same pair exists, update note/timestamp
        row = pd.read_sql(
            text(f"SELECT id::text, tank_pair_code FROM public.tank_pairs WHERE {mom_col} = :m AND {d}:d = {dad_col} LIMIT 1".replace("{d}", "")),
            cx, params={"m": mother_tank_id, "d": father_tank_id}
        )
        if not row.empty:
            tp_id = row.iloc[0]["id"]
            cx.execute(
                text(f"UPDATE public.tank_transfers SET updated_at=now(), note=COALESCE(NULLIF(:note,''), note) WHERE id = :id::uuid"),
                {"note": note, "id": tp_id}
            )
            return False, str(row.iloc[0]["tank_pair_code"])
        tp_code = cx.execute(
            text(f"""
              INSERT INTO public.tank_pairs({mom_col},{dad_col},status,it_created_by,it_created_at, note)
              VALUES (:m,:d,'selected', :by, now(), NULLIF(:note,''))
              RETURNING tank_pair_code
            """),
            {"m": mother_tank_id, "d": father_tank_id, "by": created_by, "note": note},
        ).scalar()
    return True, str(tp_code)

# ---- Page flow -----------------------------------------------------------
with st.form("filters"):
    c1, c2 = st.columns([3,1])
    with c1:
        q_raw = st.text_input("Filter by code/name/nickname/background/genotype", "")
    with c2:
        limit = int(st.number_input("Rows", min_value=50, max_value=2000, value=500, step=100))
    st.form_submit_button("Apply")

df_fish = search_fish(q_raw, limit)
if df_fish.empty:
    st.info("No fish match your search."); st.stop()

st.subheader("Step 1 — Select parents (from fish registry)")
view = df_fish.copy()
view.insert(0, "✓ Parent", False)
cfg = {
    "✓ Parent": st.column_config.CheckboxColumn("✓", default=False),
    "fish_code": st.column_config.TextColumn("fish_code", disabled=True),
    "name":      st.column_config.TextColumn("name", disabled=True),
    "nickname":  st.column_config.TextColumn("nickname", disabled=True),
    "background":st.column_config.TextColumn("background", disabled=True),
    "stage":     st.column_config.TextColumn("stage", disabled=True),
    "genotype":  st.column_config.TextColumn("genotype", disabled=True),
    "live_tanks":st.column_config.NumberColumn("live tanks", format="%d"),
    "live_tank_codes": st.column_config.TextColumn("live tank codes", disabled=True),
    "created_at":st.column_config.DatetimeColumn("created_at", format="YYYY-MM-DD HH:mm", disabled=True),
}
pick = st.data_editor(view, key="parent_pick", width="stretch", hide_index=True, column_config=cfg)
chosen = []
if not pick.empty and "✓ Parent" in pick.columns:
    chosen = pick.loc[pick["✓ Parent"] == True, "fish_code"].dropna().astype(str).tolist()
chosen = list(dict.fromkeys(chosen))[:2]  # first two unique
if len(chosen) < 2:
    st.info("Select two parents above to continue."); st.stop()

mother_code, father_code = chosen[0], chosen[1]
st.success(f"Selected parents: {mother_code} × {father_code}")

st.subheader("Step 2 — Choose Mother and Father tanks (active only)")
live = load_active_tanks_for_fusions([mother_code, father_code])
if live.empty:
    st.warning("No active tanks for selected parents."); st.stop()
live = live.sort_values(["fish_code","created_at"], ascending=[True, False])

# Mother
mdf = live[live["fish_code"] == mother_code].copy()
mdf.insert(0, "✓ Mother", False)
mview = mdf[["✓ Mother","fish_code","fish_name","genotype","tank_code","tank_id","status","created_at"]]
msel = st.data_editor(
    mview, key="mother_table", use_container_width=True, hide_index=True,
    column_config={
        "✓ Mother":  st.column_config.CheckboxColumn("✓", default=False),
        "fish_code": st.column_config.TextColumn("fish", disabled=True),
        "fish_name": st.column_config.TextColumn("name", disabled=True),
        "genotype":  st.column_config.TextColumn("genotype", disabled=True),
        "tank_code": st.column_config.TextColumn("tank", disabled=True),
        "tank_id":   st.column_config.TextColumn("tank_id", disabled=True),
        "status":    st.column_config.TextColumn("status", disabled=True),
        "created_at":st.column_config.DatetimeColumn("created", disabled=True, format="YYYY-MM-DD HH:mm"),
    },
)
selm = msel.loc[msel["✓ Mother"] == True] if not msel.empty else pd.DataFrame()
if selm.empty:
    st.info("Pick a Mother tank above to continue."); st.stop()
mother_row = selm.iloc[0]
mother_tank_id = str(mother_row["tank_id"])
mother_fish    = str(mother_row["fish_code"])

# Father (exclude chosen mother’s fish)
fdf = live[live["fish_code"] != mother_fish].copy()
fdf.insert(0, "✓ Father", False)
fview = fdf[["✓ Father","fish_code","fish_name","genotype","tank_code","tank_id","status","created_at"]]
fsel = st.data_editor(
    fview, key="father_table", use_container_width=True, hide_index=True,
    column_config={
        "✓ Father":  st.column_config.CheckboxColumn("✓", default=False),
        "fish_code": st.column_config.TextColumn("fish", disabled=True),
        "fish_name": st.column_config.TextColumn("name", disabled=True),
        "genotype":  st.column_config.TextColumn("genotype", disabled=True),
        "tank_code": st.column_config.TextColumn("tank", disabled=True),
        "tank_id":   st.column_config.TextColumn("tank_id", disabled=True),
        "status":    st.column_config.TextColumn("status", disabled=True),
        "created_at":st.column_config.DatetimeColumn("created", disabled=True, format="YYYY-MM-DD HH:mm"),
    },
)
selfa = fsel.loc[fsel["✓ Father"] == True] if not fsel.empty else pd.DataFrame()
if selfa.empty:
    st.info("Pick a Father tank above to continue."); st.stop()
father_row   = selfa.iloc[0]
father_tank_id = str(father_row["tank_id"])

if mother_tank_id == father_tank_id:
    st.error("Mother and Father cannot be the same tank."); st.stop()

st.subheader("Step 3 — Save tank pairing")
created_by_val = st.text_input("Created by", value=os.environ.get("USER") or os.environ.get("USERNAME") or "unknown")
note_val = st.text_input("Note (optional)", value="")

if st.button("💾 Save tank pairing", type="primary", use_container_width=True):
    try:
        inserted, tp_code = upsert_tank_pair(mother_tank_id, father_tank_id, created_by_val, note_val)
        st.success(("Created " if inserted else "Updated ") + f" tank_pair {tp_code}")
        for k in ("parent_pick","mother_table","father_table"):
            st.session_state.pop(k, None)
        st.info("Next: open **🗓 Schedule new cross** to add the cross date and clutch genotype(s).")
    except Exception as e:
        st.error(f"Save failed: {e}")