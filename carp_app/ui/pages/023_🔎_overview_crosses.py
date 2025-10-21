from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from pathlib import Path
from typing import List, Tuple, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.lib.db import get_engine
from carp_app.ui.auth_gate import require_auth

# ── Auth ─────────────────────────────────────────────────────────────────────
sb, session, user = require_auth()
from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Overview — Crosses", page_icon="🔎", layout="wide")
st.title("🔎 Overview — Crosses")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

# ── Helpers ──────────────────────────────────────────────────────────────────
def _status_badge(s: str) -> str:
    s = (s or "").lower().strip()
    return {
        "draft": "🟣 draft",
        "ready": "🟢 ready",
        "scheduled": "🔵 scheduled",
        "closed": "⚫ closed",
    }.get(s, s or "")

def _view_exists(schema: str, name: str) -> bool:
    with eng.begin() as cx:
        return pd.read_sql(
            text("""select 1 from information_schema.views
                     where table_schema=:s and table_name=:t limit 1"""),
            cx, params={"s": schema, "t": name}
        ).shape[0] > 0

# Require canonical view
if not _view_exists("public", "v_cross_concepts_overview"):
    st.error("Required view public.v_cross_concepts_overview not found."); st.stop()

# Discover column set from the view (we never rename in Python)
with eng.begin() as cx:
    cols = pd.read_sql(
        text("""select column_name
                from information_schema.columns
                where table_schema='public' and table_name='v_cross_concepts_overview'
                order by ordinal_position"""),
        cx
    )["column_name"].tolist()
have = {c.lower(): c for c in cols}  # map lower->actual for stable lookup

def pick(*opts: str, default: Optional[str] = None) -> Optional[str]:
    for c in opts:
        if c.lower() in have:
            return have[c.lower()]
    return default

# Candidate keys / fields (we *use* the actual names returned by the view)
col_id        = pick("id","clutch_id","concept_id","plan_id")
col_code      = pick("clutch_code","concept_code","plan_code","code")
col_status    = pick("status")
col_created   = pick("created_at","created_time","created_ts")

# ── Filters ──────────────────────────────────────────────────────────────────
with st.form("filters"):
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    q  = c1.text_input("Search (code/name/nickname/mom/dad)")
    d1 = c2.date_input("From", value=None)
    d2 = c3.date_input("To", value=None)
    status_filter = c4.selectbox("Status", ["(any)","draft","ready","scheduled","closed"], index=0)
    runnable_only = st.toggle("Runnable only (both parents have live tanks)", value=False)
    show_clutch_instances = st.toggle("Show clutch instances under each run", value=False)
    _ = st.form_submit_button("Apply")

where_parts, params = [], {}
# Build a broad search over common textual columns if present
if q:
    q_like = f"%{q.strip()}%"
    sub = []
    for cand in [
        "clutch_code","concept_code","plan_code","code",
        "planned_name","name",
        "planned_nickname","nickname",
        "mom_code","dad_code",
        "mom_genotype","dad_genotype",
        "cross_name","created_by",
    ]:
        c = pick(cand)
        if c: sub.append(f"coalesce(c.{c}::text,'') ilike :q")
    if sub:
        where_parts.append("(" + " OR ".join(sub) + ")")
        params["q"] = q_like

if d1 and col_created:
    where_parts.append(f"c.{col_created} >= :d1"); params["d1"] = str(d1)
if d2 and col_created:
    where_parts.append(f"c.{col_created} <= :d2"); params["d2"] = str(d2)
if status_filter != "(any)" and col_status:
    where_parts.append(f"coalesce(c.{col_status},'draft') = :st"); params["st"] = status_filter
if runnable_only and pick("runnable"):
    where_parts.append(f"c.{pick('runnable')} is true")

where_sql = (" where " + " AND ".join(where_parts)) if where_parts else ""

# Compose and run query (order by created if present)
created_ord = col_created if col_created else (cols[0] if cols else "created_at")
sql = text(f"""
  select c.*
  from public.v_cross_concepts_overview c
  {where_sql}
  order by c.{created_ord} desc nulls last
  limit 500
""")
with eng.begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption("Concepts from v_cross_concepts_overview • Instances via planned_crosses → crosses → cross_instances")
st.caption(f"{len(df)} planned clutch(es)")
if df.empty:
    st.info("No planned clutches match."); st.stop()

# Choose a reliable selection key (prefer code, then id, else first col)
sel_key = next((c for c in [col_code, col_id] if c and c in df.columns), None)
if sel_key is None:
    sel_key = df.columns[0]

# ── Session table (keep raw columns; add UI badge) ───────────────────────────
key = "_cross_concepts"

def _new_session_table() -> pd.DataFrame:
    t = df.copy()
    # keep selection key visible
    vis = [*t.columns]
    if sel_key not in vis:
        vis.insert(0, sel_key)
        t = t[vis]
    t.insert(0, "✓ Select", False)
    # derive a pretty status badge if we have a status column
    if col_status and (col_status in t.columns):
        t.insert(1, "status_badge", t[col_status].map(_status_badge))
    else:
        t.insert(1, "status_badge", "")
    return t

if key not in st.session_state:
    st.session_state[key] = _new_session_table()
else:
    # re-sync to live df while preserving checkboxes
    base = st.session_state[key].set_index(sel_key, drop=False)
    now = df.copy().set_index(sel_key, drop=False)
    # ensure status_badge exists/refreshes
    if col_status and (col_status in now.columns):
        now.insert(0, "status_badge", now[col_status].map(_status_badge))
    else:
        now.insert(0, "status_badge", "")
    # merge/refresh rows
    for i in now.index:
        if i not in base.index:
            base.loc[i] = now.loc[i]
        else:
            for c in now.columns:
                if c not in ("✓ Select",):  # keep selection
                    base.at[i, c] = now.at[i, c]
    # drop rows that disappeared
    base = base.loc[now.index]
    st.session_state[key] = base.reset_index(drop=True)

# ── Top table: show ALL fields from the view (plus status_badge), EXCEPT 'id' ─
visible = ["✓ Select"]
data_cols = [c for c in st.session_state[key].columns if c not in ("✓ Select", "id")]
# ensure selection key remains visible
if sel_key not in data_cols:
    data_cols.insert(0, sel_key)
visible += data_cols

edited = st.data_editor(
    st.session_state[key][visible],
    hide_index=True,
    use_container_width=True,
    column_order=visible,
    column_config={
        "✓ Select":     st.column_config.CheckboxColumn("✓", default=False),
        "status_badge": st.column_config.TextColumn("status_badge", disabled=True),
    },
    key="crosses_editor",
)
if "✓ Select" in edited.columns:
    st.session_state[key].loc[edited.index, "✓ Select"] = edited["✓ Select"]

# Selected keys (use sel_key even if user hides columns)
mask = edited.get("✓ Select", pd.Series(False, index=edited.index)).fillna(False).astype(bool)
sel_keys: List[str] = edited.loc[mask, sel_key].astype(str).tolist()
if not sel_keys:
    st.info("Select one or more planned clutches to show existing instances."); st.stop()

st.divider()
st.subheader("Existing cross instances")

def _fetch_instances_for_concept(row: pd.Series) -> Tuple[pd.DataFrame, Optional[str]]:
    """Prefer concept id, else resolve by clutch_code."""
    with eng.begin() as cx:
        if col_id and (col_id in row.index) and pd.notna(row[col_id]):
            cp = pd.read_sql(
                text("select id from public.clutch_plans where id = cast(:pid as uuid) limit 1"),
                cx, params={"pid": row[col_id]}
            )
        elif col_code and (col_code in row.index) and str(row[col_code]).strip():
            cp = pd.read_sql(
                text("select id from public.clutch_plans where clutch_code = :code limit 1"),
                cx, params={"code": str(row[col_code])}
            )
        else:
            return pd.DataFrame(), "Cannot resolve concept: no usable id/code."

        if cp.empty:
            return pd.DataFrame(), "No clutch_plans row for this concept."

        runs = pd.read_sql(
            text("""
                select
                  ci.cross_run_code,
                  ci.cross_date,
                  x.mother_code  as mom_code,
                  x.father_code  as dad_code,
                  vt_m.tank_code as mom_tank,
                  vt_f.tank_code as dad_tank,
                  coalesce(ci.created_by, pc.created_by) as created_by,
                  coalesce(ci.created_at, pc.created_at) as created_at,
                  coalesce(
                    nullif(to_jsonb(ci)->>'run_note',''),
                    nullif(to_jsonb(ci)->>'note',''),
                    nullif(to_jsonb(ci)->>'notes','')
                  ) as note,
                  ci.id as cross_instance_id
                from public.planned_crosses pc
                join public.crosses x          on x.id = pc.cross_id
                join public.cross_instances ci on ci.cross_id = x.id
                left join public.v_tanks vt_m on vt_m.tank_id = coalesce(ci.mother_tank_id, pc.mother_tank_id)
                left join public.v_tanks vt_f on vt_f.tank_id = coalesce(ci.father_tank_id, pc.father_tank_id)
                where pc.clutch_id = :cid
                order by coalesce(ci.created_at, pc.created_at) desc nulls last,
                         ci.cross_date desc nulls last
                limit 1000
            """),
            cx, params={"cid": cp["id"].iloc[0]}
        )
        if runs.empty:
            return pd.DataFrame(), "No cross_instances yet for this concept."
        return runs, None

any_found = False
for _, row in edited[edited["✓ Select"] == True].iterrows():
    row_key_val = str(row[sel_key])
    st.markdown(f"**{row_key_val}**")
    try:
        runs, warn = _fetch_instances_for_concept(row)
    except Exception as e:
        st.warning(f"Failed for {row_key_val}: {e}")
        st.markdown("---")
        continue

    if warn:
        st.info(warn); st.markdown("---"); continue
    if runs.empty:
        st.caption("No instances."); st.markdown("---"); continue

    any_found = True
    show = ["cross_run_code","cross_date","mom_code","dad_code","mom_tank","dad_tank","created_by","created_at","note"]
    st.dataframe(runs[[c for c in show if c in runs.columns]], use_container_width=True, hide_index=True)
    st.markdown("---")

if not any_found:
    st.info("No instance rows found for selected concept(s).")