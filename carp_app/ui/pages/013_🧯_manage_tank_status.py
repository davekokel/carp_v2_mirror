from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from typing import List, Optional
import pandas as pd
import streamlit as st
from sqlalchemy import text

from carp_app.lib.db import get_engine
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp

# ── Auth ─────────────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()

# ── Page ─────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="🧯 Manage Tank Status", page_icon="🧯", layout="wide")
st.title("🧯 Manage Tank Status")

ENG = get_engine()

# ── Helpers ──────────────────────────────────────────────────────────────────
def _as_uuid_or_blank(x) -> str:
    try:
        import uuid
        s = str(x or "").strip()
        uuid.UUID(s)
        return s
    except Exception:
        return ""

def _exists(schema: str, name: str) -> bool:
    q = text("""
      with t as (
        select table_schema as s, table_name as n from information_schema.tables
        union all
        select table_schema as s, table_name as n from information_schema.views
      )
      select exists(select 1 from t where s=:s and n=:n) as ok
    """)
    with ENG.begin() as cx:
        return bool(pd.read_sql(q, cx, params={"s": schema, "n": name})["ok"].iloc[0])

def _distinct_statuses() -> list[str]:
    if not _exists("public","v_tanks"):
        return ["new_tank","active","to_kill","retired","planned"]
    with ENG.begin() as cx:
        df = pd.read_sql(text("select distinct status from public.v_tanks where status is not null order by 1"), cx)
    vals = df["status"].dropna().astype(str).tolist()
    return vals or ["new_tank","active","to_kill","retired","planned"]

def _load_tanks(statuses: List[str], q: str) -> pd.DataFrame:
    if not _exists("public","v_tanks"):
        st.error("Required view public.v_tanks not found."); st.stop()

    where_bits, params = [], {}
    if statuses:
        placeholders = ", ".join([f":st{i}" for i in range(len(statuses))])
        where_bits.append(f"status in ({placeholders})")
        for i, s in enumerate(statuses):
            params[f"st{i}"] = s

    q = (q or "").strip()
    if q:
        where_bits.append(
            "("
            "coalesce(tank_code,'') ilike :qq or "
            "coalesce(fish_code,'') ilike :qq or "
            "tank_uuid::text ilike :qq"
            ")"
        )
        params["qq"] = f"%{q}%"

    where_sql = (" where " + " and ".join(where_bits)) if where_bits else ""
    sql = text(f"""
      select
        tank_uuid::text     as id,
        tank_code::text     as tank_code,
        coalesce(fish_code,'')::text as fish_code,
        coalesce(status::text,'')    as status,
        created_at                    as created_at
      from public.v_tanks
      {where_sql}
      order by created_at desc nulls last, tank_code
      limit 1000
    """)

    with ENG.begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    # normalize expected columns for the grid
    for want in ["label","capacity","tank_code","fish_code","status","created_at","tank_updated_at"]:
        if want not in df.columns:
            df[want] = pd.NA

    df.rename(columns={
        "created_at":      "Created at",
        "tank_updated_at": "Updated at",
        "tank_code":       "Tank code",
        "fish_code":       "Fish",
        "status":          "Status",
        "label":           "Tank label",
        "capacity":        "Capacity",
    }, inplace=True)
    return df

def _load_history(container_id: str) -> pd.DataFrame:
    q = text("""
      select changed_at, old_status, new_status,
             coalesce(changed_by,'') as changed_by,
             coalesce(reason,'')     as reason
      from public.container_status_history
      where container_id = cast(:id as uuid)
      order by changed_at desc
      limit 500
    """)
    with ENG.begin() as cx:
        return pd.read_sql(q, cx, params={"id": container_id})

def _set_status(container_id: str, action: str, by: str, reason: Optional[str]=None):
    fn = {"active":"public.mark_container_active",
          "to_kill":"public.mark_container_to_kill",
          "retired":"public.mark_container_retired"}[action]
    with ENG.begin() as cx:
        if reason is not None:
            cx.execute(text(f"select {fn}(:id, :by, :rsn)"), {"id": container_id, "by": by, "rsn": reason})
        else:
            cx.execute(text(f"select {fn}(:id, :by)"), {"id": container_id, "by": by})

def _bulk_set_status(ids: List[str], action: str, by: str, reason: Optional[str]=None) -> int:
    if not ids: return 0
    fn = {"active":"public.mark_container_active",
          "to_kill":"public.mark_container_to_kill",
          "retired":"public.mark_container_retired"}[action]
    with ENG.begin() as cx:
        for cid in ids:
            if reason is not None:
                cx.execute(text(f"select {fn}(:id, :by, :rsn)"), {"id": cid, "by": by, "rsn": reason})
            else:
                cx.execute(text(f"select {fn}(:id, :by)"), {"id": cid, "by": by})
    return len(ids)

def _touch_last_seen(container_id: str, source: str, also_activate: bool, by: str):
    with ENG.begin() as cx:
        cx.execute(text("""
          update public.containers
             set last_seen_at = now(),
                 last_seen_source = :src
           where id = cast(:id as uuid)
        """), {"id": container_id, "src": (source or "manual")})
        if also_activate:
            cx.execute(text("select public.mark_container_active(:id, :by)"), {"id": container_id, "by": by})

def _bulk_touch_last_seen(ids: List[str], source: str, also_activate: bool, by: str) -> int:
    if not ids: return 0
    with ENG.begin() as cx:
        cx.execute(text("""
          update public.containers
             set last_seen_at = now(),
                 last_seen_source = :src
           where id = any(cast(:ids as uuid[]))
        """), {"ids": ids, "src": (source or "manual")})
        if also_activate:
            for cid in ids:
                cx.execute(text("select public.mark_container_active(:id, :by)"), {"id": cid, "by": by})
    return len(ids)

def _clone_tanks_like(container_id: str, n: int, by: str) -> pd.DataFrame:
    if n <= 0:
        return pd.DataFrame()

    sql = text("""
      with src as (
        select fish_code, status, rack, "position"
        from public.tanks
        where tank_uuid = cast(:cid as uuid)
        limit 1
      ),
      locked as (
        -- serialize per fish to avoid tank_code races
        select fish_code, status, rack, "position",
               pg_advisory_xact_lock(hashtext(fish_code)) as _
        from src
      ),
      next_idx as (
        select l.fish_code,
               coalesce((
                 select max( (regexp_match(t.tank_code, '#([0-9]+)$'))[1]::int )
                 from public.tanks t
                 where t.fish_code = l.fish_code
               ), 0) as base_idx
        from locked l
      ),
      ins as (
        insert into public.tanks (tank_code, fish_code, status, rack, "position", created_by)
        select
          format('TANK(%s)#%s', l.fish_code, ni.base_idx + g.i) as tank_code,
          l.fish_code,
          l.status,
          l.rack,
          l."position",
          nullif(:by,'')::uuid
        from locked l
        join next_idx ni on ni.fish_code = l.fish_code
        cross join generate_series(1, :n) as g(i)
        returning tank_uuid::text as id, tank_code, fish_code, status, created_at
      )
      select * from ins
      order by created_at desc
    """)
    with ENG.begin() as cx:
        return pd.read_sql(sql, cx, params={"cid": container_id, "n": int(n), "by": by})

# ── Filters ──────────────────────────────────────────────────────────────────
user_default = os.environ.get("USER") or os.environ.get("USERNAME") or (getattr(user, "email", "") or "unknown")
all_status  = _distinct_statuses()
default_st  = [s for s in ["new_tank","active"] if s in all_status] or (all_status[:1] if all_status else [])

with st.form("filters"):
    c0, c1 = st.columns([1.2, 3.0])
    with c0:
        statuses = st.multiselect("Status", options=all_status, default=default_st)
    with c1:
        query = st.text_input("Search (label / tank_code / id / fish_code)", value="")
    _ = st.form_submit_button("Apply", width="stretch")

# ── Data load ────────────────────────────────────────────────────────────────
df = _load_tanks(statuses, query)

st.subheader("Recent tanks (filtered)")
if df.empty:
    st.info("No tanks match your filters."); st.stop()

# ── Grid with selection ──────────────────────────────────────────────────────
grid = df.copy()
if "✓ Select" not in grid.columns:
    grid.insert(0, "✓ Select", False)

show_cols = ["✓ Select","id"] + [c for c in ["Tank label","Tank code","Fish","Status","Capacity","Created at","Updated at"] if c in grid.columns]
edited = st.data_editor(
    grid[show_cols],
    hide_index=True,
    width="stretch",
    column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
    key="tank_status_editor",
)
sel_mask = edited.get("✓ Select", pd.Series(False, index=edited.index)).fillna(False).astype(bool)
selected_ids = edited.loc[sel_mask, "id"].astype(str).tolist()
st.caption(f"{len(selected_ids)} selected")

# ── Bulk actions ─────────────────────────────────────────────────────────────
st.markdown("### Bulk actions")
b1, b2, b3, b4 = st.columns([1,1,1,2])
with b1:
    if st.button("Mark Active", width="stretch", disabled=not selected_ids):
        n = _bulk_set_status(selected_ids, "active", user_default); st.success(f"Set {n} tank(s) to active")
with b2:
    rsn_k = st.text_input("Reason (to_kill)", key="rsn_kill")
    if st.button("Mark To-Kill", width="stretch", disabled=not selected_ids):
        n = _bulk_set_status(selected_ids, "to_kill", user_default, (rsn_k or "").strip() or None); st.warning(f"Marked {n} tank(s) to_kill")
with b3:
    rsn_r = st.text_input("Reason (retired)", key="rsn_retire")
    if st.button("Retire", width="stretch", disabled=not selected_ids):
        n = _bulk_set_status(selected_ids, "retired", user_default, (rsn_r or "").strip() or None); st.info(f"Retired {n} tank(s)")
with b4:
    src = st.text_input("Seen source", value="manual", key="seen_src")
    also_act = st.checkbox("Also mark Active", value=True, key="seen_act")
    if st.button("Last seen → now", width="stretch", disabled=not selected_ids):
        n = _bulk_touch_last_seen(selected_ids, (src or "").strip(), also_act, user_default); st.success(f"Stamped last_seen for {n} tank(s)")

# ── Single tank actions ──────────────────────────────────────────────────────
st.markdown("### Single tank")
if not selected_ids:
    st.caption("Select a row above to manage a single tank.")
else:
    tank_id = selected_ids[0]
    row = df.loc[df["id"] == tank_id].iloc[0].to_dict()

    with st.container(border=True):
        cL, cR = st.columns([2,2])
        with cL:
            st.write(f"**Tank code:** {row.get('Tank code') or '—'}")
            st.write(f"**Fish:** {row.get('Fish') or '—'}")
            st.write(f"**Capacity:** {row.get('Capacity') or '—'}")
        with cR:
            st.write(f"**Status:** {row.get('Status') or '—'}")
            st.write(f"**Created:** {row.get('Created at')}")
            st.write(f"**Updated:** {row.get('Updated at')}")
        st.divider()

        a1, a2, a3, a4 = st.columns([1,1,1,2])
        with a1:
            if st.button("Mark Active", key="single_mark_active", width="stretch"):
                _set_status(tank_id, "active", user_default); st.success("Set to active")
        with a2:
            rsn_k2 = st.text_input("Reason (to_kill)", key=f"single_rsn_k_{tank_id}")
            if st.button("Mark To-Kill", key="single_mark_kill", width="stretch"):
                _set_status(tank_id, "to_kill", user_default, (rsn_k2 or "").strip() or None); st.warning("Marked to_kill")
        with a3:
            rsn_r2 = st.text_input("Reason (retired)", key=f"single_rsn_r_{tank_id}")
            if st.button("Retire", key="single_mark_retire", width="stretch"):
                _set_status(tank_id, "retired", user_default, (rsn_r2 or "").strip() or None); st.info("Retired")
        with a4:
            src2 = st.text_input("Seen source (optional)", value="manual", key=f"single_src_{tank_id}")
            if st.button("Last seen → now (and activate)", key="single_seen_now", width="stretch"):
                _touch_last_seen(tank_id, (src2 or "").strip(), True, user_default); st.success("Stamped last_seen_at and activated")

        st.divider()
        st.markdown("**Add new tanks like this**")
        cN, cBtn = st.columns([1,3])
        with cN:
            n_like = st.number_input("How many?", min_value=1, max_value=50, value=3, step=1, key=f"n_like_{tank_id}")
        with cBtn:
            if st.button(f"➕ Add {n_like} like selected", width="stretch", key=f"clone_like_{tank_id}"):
                by_uuid = _as_uuid_or_blank(getattr(user, "id", None) or getattr(user, "uuid", None) or os.environ.get("AUTH_USER_ID"))
                inserted = _clone_tanks_like(tank_id, int(n_like), by_uuid)
                if inserted.empty:
                    st.warning("No rows inserted (check selection).")
                else:
                    st.success(f"Created {len(inserted)} new tank(s).")
                    st.rerun()

    st.markdown("**Status history**")
    hist = _load_history(tank_id)
    if hist.empty:
        st.caption("— no history yet —")
    else:
        showh = hist.rename(columns={
            "changed_at":"When",
            "old_status":"From",
            "new_status":"To",
            "changed_by":"By",
            "reason":"Reason",
        })
        st.dataframe(showh, width="stretch", hide_index=True)
        csv = showh.to_csv(index=False).encode("utf-8")
        fname = f"tank_{(row.get('Tank code') or row.get('id') or 'unknown').split()[0]}_status_history.csv"
        st.download_button("Download history CSV", csv, file_name=fname, mime="text/csv", width="stretch")