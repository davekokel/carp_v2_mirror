# 033_🐟_register_new_clutch.py
from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    try:
        from auth_gate import require_app_unlock
    except Exception:
        def require_app_unlock(): ...
require_app_unlock()

import os
from datetime import date, timedelta
from typing import Optional, Dict

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _ensure_sslmode(url: str) -> str:
    from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
    u = urlparse(url)
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    host = (u.hostname or "").lower() if u.hostname else ""
    if host in {"localhost", "127.0.0.1", "::1"}:
        q["sslmode"] = "disable"
    else:
        q.setdefault("sslmode", "require")
    return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q), u.fragment))

@st.cache_resource(show_spinner=False)
def _get_engine():
    url = os.environ.get("DB_URL")
    if not url:
        st.stop()
    return create_engine(_ensure_sslmode(url))

ENGINE = _get_engine()

st.set_page_config(page_title="Register New Clutch", page_icon="🍼")
st.title("🍼 Register Clutches — record size/notes and print Petri labels")

colA, colB = st.columns(2)
with colA:
    clutch_birthday = st.date_input("Clutch birthday", value=date.today())
with colB:
    created_by = st.text_input(
        "Created by",
        value=os.environ.get("USER") or os.environ.get("USERNAME") or "unknown",
    )

colC, colD = st.columns(2)
with colC:
    lookback_days = st.number_input(
        "Show planned crosses within days of birthday", value=3, min_value=0, step=1
    )
with colD:
    lookback_days_cross = st.number_input(
        "Show actual crosses within days of birthday", value=3, min_value=0, step=1
    )

date_min = clutch_birthday - timedelta(days=int(lookback_days))
date_max = clutch_birthday + timedelta(days=int(lookback_days))
date_min_x = clutch_birthday - timedelta(days=int(lookback_days_cross))
date_max_x = clutch_birthday + timedelta(days=int(lookback_days_cross))

with ENGINE.connect() as cx:
    planned = pd.read_sql(
        text(
            """
            select
              pc.id_uuid::text                  as planned_cross_id,
              cp.clutch_code                    as clutch_code,
              cp.planned_name                   as planned_name,
              pc.mom_code                       as mom_code,
              pc.cross_date                     as cross_date,
              pc.created_by
            from public.planned_crosses pc
            join public.clutch_plans cp on cp.id_uuid = pc.clutch_id
            where pc.cross_date between :dmin and :dmax
            order by pc.cross_date desc, cp.clutch_code nulls last
            """
        ),
        cx,
        params={"dmin": date_min, "dmax": date_max},
    )

with ENGINE.connect() as cx:
    has_cross_date = pd.read_sql(
        text(
            """
            select exists(
              select 1 from information_schema.columns
              where table_schema='public' and table_name='crosses' and column_name='cross_date'
            ) as ok
            """
        ),
        cx,
    ).iloc[0, 0]

with ENGINE.connect() as cx:
    if bool(has_cross_date):
        actual = pd.read_sql(
            text(
                """
                select
                  x.id_uuid::text                       as cross_id,
                  coalesce(x.cross_date::date, now()::date) as cross_date,
                  x.created_by
                from public.crosses x
                where coalesce(x.cross_date::date, now()::date) between :dmin and :dmax
                order by cross_date desc
                """
            ),
            cx,
            params={"dmin": date_min_x, "dmax": date_max_x},
        )
    else:
        actual = pd.read_sql(
            text(
                """
                select
                  x.id_uuid::text           as cross_id,
                  x.created_at::date        as cross_date,
                  x.created_by
                from public.crosses x
                where x.created_at::date between :dmin and :dmax
                order by cross_date desc
                """
            ),
            cx,
            params={"dmin": date_min_x, "dmax": date_max_x},
        )

st.subheader("Step 1 — Pick planned cross and actual cross for this clutch")

def _label_plan(r: Dict) -> str:
    cc = r.get("clutch_code") or ""
    nm = r.get("planned_name") or ""
    mm = r.get("mom_code") or ""
    cd = r.get("cross_date")
    return f"{cc} — {nm} — {mm} — {cd}"

def _label_actual(r: Dict) -> str:
    return f"{r.get('cross_id')[:8]}… — {r.get('cross_date')}"

planned_opt = {r["planned_cross_id"]: _label_plan(r) for _, r in planned.iterrows()}
actual_opt = {r["cross_id"]: _label_actual(r) for _, r in actual.iterrows()}

pc_choice: Optional[str] = st.selectbox(
    "Planned cross",
    options=list(planned_opt.keys()),
    format_func=lambda k: planned_opt.get(k, "(missing)"),
    index=0 if planned_opt else None,
    key="pc_sel",
)
x_choice: Optional[str] = st.selectbox(
    "Actual cross",
    options=list(actual_opt.keys()),
    format_func=lambda k: actual_opt.get(k, "(missing)"),
    index=0 if actual_opt else None,
    key="x_sel",
)

st.subheader("Step 2 — Enter clutch fields")
c1, c2, c3 = st.columns(3)
with c1:
    batch_label = st.text_input("Batch label", value="")
with c2:
    seed_batch_id = st.text_input("Seed batch id", value="")
with c3:
    note = st.text_input("Note", value="")

st.caption("Save requires both a planned cross and an actual cross.")

disabled = not (pc_choice and x_choice and clutch_birthday)
save = st.button("✅ Save clutch", type="primary", disabled=disabled)

if save:
    try:
        with ENGINE.begin() as cx:
            new_id = pd.read_sql(
                text(
                    """
                    insert into public.clutches (
                      planned_cross_id, cross_id, batch_label, seed_batch_id, date_birth, created_by, note
                    ) values (
                      :planned_cross_id, :cross_id, :batch_label, :seed_batch_id, :date_birth, :created_by, :note
                    )
                    returning id_uuid::text
                    """
                ),
                cx,
                params={
                    "planned_cross_id": pc_choice,
                    "cross_id": x_choice,
                    "batch_label": batch_label or None,
                    "seed_batch_id": seed_batch_id or None,
                    "date_birth": clutch_birthday,
                    "created_by": created_by,
                    "note": note or None,
                },
            ).iloc[0, 0]
        st.success(f"Clutch saved: {new_id}")
        st.session_state["pc_sel"] = pc_choice
        st.session_state["x_sel"] = x_choice
    except Exception as e:
        st.error(f"Failed to save clutch: {e}")