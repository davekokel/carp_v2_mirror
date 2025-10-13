from __future__ import annotations
from supabase.ui.auth_gate import require_auth
sb, session, user = require_auth()

from supabase.ui.email_otp_gate import require_email_otp
require_email_otp()

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

import os, json, uuid
from datetime import datetime
from typing import List, Optional, Dict
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Manage Tank Status", page_icon="🧯")
st.title("🧯 Manage Tank Status")

def _db_url() -> str:
    u = os.environ.get("DB_URL", "")
    if not u:
        raise RuntimeError("DB_URL not set")
    return u

ENGINE = create_engine(_db_url(), pool_pre_ping=True)

# ---------- data loaders ----------
def _load_tanks(container_types: List[str], statuses: List[str], q: str) -> pd.DataFrame:
    type_clause = " = any(:types)" if container_types else " is not null"
    status_clause = " = any(:statuses)" if statuses else " is not null"
    search_clause = ""
    params: Dict = {"types": container_types, "statuses": statuses}
    if q.strip():
        search_clause = """
          and (
            coalesce(label,'') ilike :qq
            or coalesce(tank_code,'') ilike :qq
            or id_uuid::text ilike :qq
          )
        """
        params["qq"] = f"%{q.strip()}%"
    sql = f"""
      select
        id_uuid as id,
        coalesce(label,'') as label,
        tank_code,
        container_type,
        status,
        tank_volume_l,
        created_by,
        created_at,
        status_changed_at,
        activated_at,
        deactivated_at,
        last_seen_at,
        coalesce(note,'') as note
      from public.v_containers_crossing_candidates
      where container_type{type_clause}
        and status{status_clause}
        {search_clause}
      order by created_at desc
      limit 1000
    """
    with ENGINE.begin() as c:
        df = pd.read_sql(text(sql), c, params=params)
    df["id"] = df["id"].astype(str)
    return df

def _load_history(container_id: str) -> pd.DataFrame:
    q = text("""
      select changed_at, old_status, new_status, coalesce(changed_by,'') as changed_by, coalesce(reason,'') as reason
      from public.container_status_history
      where container_id = :id
      order by changed_at desc
      limit 500
    """)
    with ENGINE.begin() as c:
        return pd.read_sql(q, c, params={"id": container_id})

# ---------- actions ----------
def _set_status(container_id: str, action: str, by: str, reason: Optional[str]=None):
    fn = {
        "active": "public.mark_container_active",
        "to_kill": "public.mark_container_to_kill",
        "retired": "public.mark_container_retired",
    }[action]
    with ENGINE.begin() as c:
        if reason is not None:
            c.execute(text(f"select {fn}(:id, :by, :rsn)"), dict(id=container_id, by=by, rsn=reason))
        else:
            c.execute(text(f"select {fn}(:id, :by)"), dict(id=container_id, by=by))

def _touch_last_seen(container_id: str, source: str, also_activate: bool, by: str):
    with ENGINE.begin() as c:
        c.execute(
            text("""
              update public.containers
              set last_seen_at = now(),
                  last_seen_source = :src
              where id_uuid = :id
            """),
            dict(id=container_id, src=source or "manual"),
        )
        if also_activate:
            c.execute(text("select public.mark_container_active(:id, :by)"), dict(id=container_id, by=by))

def _bulk_set_status(ids: List[str], action: str, by: str, reason: Optional[str] = None) -> int:
    if not ids:
        return 0
    fn = {
        "active": "public.mark_container_active",
        "to_kill": "public.mark_container_to_kill",
        "retired": "public.mark_container_retired",
    }[action]
    with ENGINE.begin() as c:
        # call the function once per id (keeps triggers/history correct)
        for cid in ids:
            if reason is not None:
                c.execute(text(f"select {fn}(:id, :by, :rsn)"), dict(id=cid, by=by, rsn=reason))
            else:
                c.execute(text(f"select {fn}(:id, :by)"), dict(id=cid, by=by))
    return len(ids)

def _bulk_touch_last_seen(ids: List[str], source: str, also_activate: bool, by: str) -> int:
    if not ids:
        return 0
    with ENGINE.begin() as c:
        c.execute(
            text("""
                update public.containers
                   set last_seen_at = now(),
                       last_seen_source = :src
                 where id_uuid = any(CAST(:ids as uuid[]))
            """),
            dict(ids=ids, src=(source or "manual")),
        )
        if also_activate:
            for cid in ids:
                c.execute(text("select public.mark_container_active(:id, :by)"), dict(id=cid, by=by))
    return len(ids)

# ---------- UI filters ----------
user_default = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
created_by = st.text_input("You are", value=user_default)

cols = st.columns([1.2, 1.2, 2.6])
with cols[0]:
    types = st.multiselect(
        "Container types",
        ["inventory_tank","crossing_tank","holding_tank","nursery_tank","petri_dish"],
        default=["inventory_tank"],
    )
with cols[1]:
    statuses = st.multiselect(
        "Status",
        ["planned","active","to_kill","retired"],
        default=["active","planned"],
    )
with cols[2]:
    query = st.text_input("Search (label / code / id)", value="")

df = _load_tanks(types, statuses, query)

st.subheader("Recent tanks (filtered)")
if df.empty:
    st.info("No tanks match your filters.")
    st.stop()

table = df.rename(columns={
    "id":"id",
    "label":"Tank label",
    "tank_code":"Code",
    "container_type":"Type",
    "status":"Status",
    "tank_volume_l":"Vol (L)",
    "created_at":"Created at",
    "status_changed_at":"Status changed",
})
st.dataframe(table[["id","Tank label","Code","Type","Status","Vol (L)","Created at","Status changed"]], use_container_width=True, hide_index=True)

# === Bulk actions (on filtered set) — INSERT START ===
st.markdown("### Bulk actions (on filtered set)")

_opts = [f"{r['label'] or '—'} · {r['status']} · {r['id'].split('-')[0]}" for _, r in df.iterrows()]
_opt_to_id = dict(zip(_opts, df["id"].tolist()))

col_sel1, col_sel2 = st.columns([3,1])
with col_sel1:
    picked_opts = st.multiselect("Pick tanks (type to search)", _opts, default=[])
with col_sel2:
    if st.button("Select all shown"):
        picked_opts = _opts  # local var; shows count below

picked_ids = [_opt_to_id[o] for o in picked_opts]
st.caption(f"{len(picked_ids)} selected")

a1, a2, a3, a4 = st.columns([1,1,1,2])
with a1:
    if st.button("Mark Active", use_container_width=True, disabled=not picked_ids):
        n = _bulk_set_status(picked_ids, "active", created_by)
        st.success(f"Set {n} tank(s) to active")
with a2:
    rsn_k = st.text_input("Reason (to_kill)", key="bulk_kill_reason")
    if st.button("Mark To-Kill", use_container_width=True, disabled=not picked_ids):
        n = _bulk_set_status(picked_ids, "to_kill", created_by, (rsn_k or "").strip() or None)
        st.warning(f"Marked {n} tank(s) to_kill")
with a3:
    rsn_r = st.text_input("Reason (retired)", key="bulk_retire_reason")
    if st.button("Retire", use_container_width=True, disabled=not picked_ids):
        n = _bulk_set_status(picked_ids, "retired", created_by, (rsn_r or "").strip() or None)
        st.info(f"Retired {n} tank(s)")
with a4:
    src = st.text_input("Seen source", value="manual", key="bulk_seen_src")
    also_act = st.checkbox("Also mark Active", value=True, key="bulk_seen_act")
    if st.button("Last seen → now", use_container_width=True, disabled=not picked_ids):
        n = _bulk_touch_last_seen(picked_ids, (src or "").strip(), also_act, created_by)
        st.success(f"Stamped last_seen for {n} tank(s)")
# === Bulk actions — INSERT END ===

# ---------- pick a tank ----------
opt_labels = [f"{row['label'] or '—'} · {row['status']} · {row['id'].split('-')[0]}" for _, row in df.iterrows()]
opt_to_id = dict(zip(opt_labels, df["id"].tolist()))
pick = st.selectbox("Pick a tank", [""] + opt_labels)

if pick:
    tank_id = opt_to_id[pick]
    row = df.loc[df["id"] == tank_id].iloc[0]

    with st.container(border=True):
        st.markdown("**Tank details**")
        cL, cR = st.columns([2,2])
        with cL:
            st.write(f"**Label:** {row['label'] or '—'}")
            st.write(f"**Code:** {row.get('tank_code') or '—'}")
            st.write(f"**Type:** {row['container_type']}")
            st.write(f"**Volume:** {row.get('tank_volume_l') or '—'} L")
        with cR:
            st.write(f"**Status:** {row['status']}")
            st.write(f"**Activated:** {row.get('activated_at')}")
            st.write(f"**Deactivated:** {row.get('deactivated_at')}")
            st.write(f"**Last seen:** {row.get('last_seen_at')}")

        st.divider()

        a1, a2, a3, a4 = st.columns([1,1,1,2])
        with a1:
            if st.button("Mark Active", use_container_width=True):
                _set_status(tank_id, "active", created_by)
                st.success("Set to active")
        with a2:
            reason_k = st.text_input("Reason (to_kill)", key=f"rsn_k_{tank_id}")
            if st.button("Mark To-Kill", use_container_width=True):
                _set_status(tank_id, "to_kill", created_by, (reason_k or "").strip() or None)
                st.warning("Marked to_kill")
        with a3:
            reason_r = st.text_input("Reason (retired)", key=f"rsn_r_{tank_id}")
            if st.button("Retire", use_container_width=True):
                _set_status(tank_id, "retired", created_by, (reason_r or "").strip() or None)
                st.info("Retired")
        with a4:
            src = st.text_input("Seen source (optional)", value="manual", key=f"src_{tank_id}")
            if st.button("Last seen → now (and activate)", use_container_width=True):
                _touch_last_seen(tank_id, src.strip(), True, created_by)
                st.success("Stamped last_seen_at and activated")

    st.markdown("**Status history**")
    hist = _load_history(tank_id)
    if hist.empty:
        st.write("— no history yet —")
    else:
        st.dataframe(
            hist.rename(columns={
                "changed_at":"When",
                "old_status":"From",
                "new_status":"To",
                "changed_by":"By",
                "reason":"Reason"
            }),
            use_container_width=True,
            hide_index=True
        )
        st.download_button(
            "Download history CSV",
            hist.to_csv(index=False).encode("utf-8"),
            file_name=f"tank_{row.get('tank_code') or row['label'] or tank_id}_status_history.csv",
            mime="text/csv",
            use_container_width=True
        )
