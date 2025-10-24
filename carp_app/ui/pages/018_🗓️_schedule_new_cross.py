# =============================================================================
# 🗓 Schedule new cross (CX codes, no dates inside the code)
#   - Pick concept (optional) or just pick a tank pair
#   - Insert cross_instances (triggers assign unified CX)
#   - (Optional) also insert clutch_instances; birthday defaults = cross_date + 1 day
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import text

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine

sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="🗓 Schedule new cross", page_icon="🗓", layout="wide")
st.title("🗓 Schedule new cross")

if not os.getenv("DB_URL"):
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

def _safe(cx, sql, params=None):
    return pd.read_sql(text(sql), cx, params=params or {})

# --- filters ---
with st.form("filters"):
    c1, c2 = st.columns([3,1])
    q = c1.text_input("Search tank pairs (code / fish / tank)")
    limit = int(c2.number_input("Limit", min_value=10, max_value=2000, value=200, step=50))
    st.form_submit_button("Apply")

# --- load candidates ---
sql_pairs = text(f"""
  with base as (
    select
      tp.id::uuid          as tank_pair_id,
      tp.tank_pair_code,
      -- prefer view if exists else derive
      coalesce(tp.pair_fish, coalesce(tp.mom_fish_code,'') || ' × ' || coalesce(tp.dad_fish_code,'')) as pair_fish,
      coalesce(tp.pair_tanks, coalesce(tp.mom_tank_code,'') || ' × ' || coalesce(tp.dad_tank_code,'')) as pair_tanks,
      tp.genotype,
      tp.created_at
    from public.v_tank_pairs tp
  )
  select *
  from base
  where (:q = '' OR
         tank_pair_code ilike :ql OR
         pair_fish      ilike :ql OR
         pair_tanks     ilike :ql)
  order by created_at desc nulls last
  limit :lim
""")
with eng.begin() as cx:
    pairs = _safe(cx, sql_pairs, {"q": (q or ""), "ql": f"%{q or ''}%", "lim": limit})

st.subheader("1) Pick a tank pair")
if pairs.empty:
    st.info("No tank pairs. Create some on *Select tank pairings* first.")
    st.stop()

pairs_view = pairs.copy()
pairs_view.insert(0,"✓ Select", False)
pairs_edit = st.data_editor(
    pairs_view[["✓ Select","tank_pair_code","pair_fish","pair_tanks","genotype","created_at"]],
    hide_index=True, width="stretch",
    column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)}
)
mask = pairs_edit["✓ Select"].fillna(False)
picked = pairs_view.loc[mask].head(1)
if picked.empty:
    st.info("Select one tank pair above to continue."); st.stop()

tp_id = str(picked.iloc[0]["tank_pair_id"])
tp_code = str(picked.iloc[0]["tank_pair_code"])
st.success(f"Selected **{tp_code}** — {picked.iloc[0]['pair_fish']}")

st.subheader("2) Choose run date & options")
c1, c2 = st.columns([1,2])
run_date: date = c1.date_input("Run date", value=date.today())
make_clutch = c2.checkbox("Also create clutch now (birthday defaults to run + 1 day)", value=True)
note = st.text_input("Run note (optional)")

if st.button("⏱ Schedule cross (and clutch)", type="primary"):
    try:
        with eng.begin() as cx:
            # Insert a cross row; trigger assigns cross_code = CX(TP)(NN)
            row = _safe(cx, """
              insert into public.cross_instances (id, tank_pair_id, cross_date, created_by, note)
              values (gen_random_uuid(), cast(:tp as uuid), :d, :by, nullif(:note,''))
              returning id, cross_code, cross_date
            """, {"tp": tp_id, "d": str(run_date), "by": (user.get('email') or user.get('id') or 'unknown'), "note": note})
            if row.empty:
                st.error("Insert failed (no cross row returned)."); st.stop()

            cross_id   = str(row.iloc[0]["id"])
            cross_code = str(row.iloc[0]["cross_code"])

            if make_clutch:
                # Insert clutch linked to cross; trigger sets birthday & copies the same CX code
                cl = _safe(cx, """
                  insert into public.clutch_instances (id, cross_instance_id, created_by)
                  values (gen_random_uuid(), cast(:cid as uuid), :by)
                  returning id, clutch_code, birthday
                """, {"cid": cross_id, "by": (user.get('email') or user.get('id') or 'unknown')})
                if cl.empty:
                    st.warning(f"Cross {cross_code} inserted, but clutch insert returned no row.")
                else:
                    st.success(f"Saved: **{cross_code}**; clutch **{cl.iloc[0]['clutch_code']}** (birth {cl.iloc[0]['birthday']:%Y-%m-%d})")
            else:
                st.success(f"Saved cross: **{cross_code}** (run {row.iloc[0]['cross_date']:%Y-%m-%d})")

        # Show last few for confirmation
        with eng.begin() as cx:
            preview = _safe(cx, """
              select
                tp.tank_pair_code,
                ci.cross_code,
                to_char(ci.cross_date,'YYYY-MM-DD') as cross_date,
                cl.clutch_code,
                to_char(cl.birthday,'YYYY-MM-DD')   as birth_date
              from public.cross_instances ci
              join public.tank_pairs tp on tp.id = ci.tank_pair_id
              left join public.clutch_instances cl on cl.cross_instance_id = ci.id
              order by ci.created_at desc nulls last
              limit 5
            """)
        st.subheader("Recent CX events")
        st.dataframe(preview, width="stretch", hide_index=True)
    except Exception as e:
        st.error(f"Schedule failed: {e}")