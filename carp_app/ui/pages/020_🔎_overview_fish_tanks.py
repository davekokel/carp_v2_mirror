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
from typing import List
import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

import importlib
from carp_app.lib import queries as Q
importlib.reload(Q)

PAGE_TITLE = "CARP — Overview Search"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🔎", layout="wide")

_ENGINE = None
def _get_engine():
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    url = os.getenv("DB_URL")
    if not url:
        raise RuntimeError("DB_URL is not set")
    _ENGINE = create_engine(url, future=True)
    return _ENGINE

def _stage_choices() -> List[str]:
    sql = """
      select distinct upper(stage) as s
      from public.vw_fish_standard
      where stage is not null and stage <> ''
      order by 1
    """
    with _get_engine().begin() as cx:
        df = pd.read_sql(text(sql), cx)
    return [s for s in df["s"].astype(str).tolist() if s]

def _load_standard_for_codes(codes: List[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame()

    sql = text("""
      with wanted as (
        select id, fish_code
        from public.fish
        where fish_code = any(:codes)
      ),
      live_counts as (
        select m.fish_id, count(*)::int as n_living_tanks
        from public.fish_tank_memberships m
        join public.containers c on c.id_uuid = m.container_id
        where m.left_at is null
          and c.status in ('active','new_tank')
          and m.fish_id in (select id from wanted)
        group by m.fish_id
      )
      select
        s.*,
        coalesce(lc.n_living_tanks, 0) as n_living_tanks
      from public.vw_fish_standard s
      join wanted w on w.fish_code = s.fish_code
      left join live_counts lc on lc.fish_id = w.id
    """)

    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})

    # Ensure unique column names for Streamlit data_editor (keep our live count)
    df = df.loc[:, ~df.columns.duplicated(keep="last")]
    if "n_living_tanks" in df.columns:
        df["n_living_tanks"] = df["n_living_tanks"].fillna(0).astype(int)

    order = {c: i for i, c in enumerate(codes)}
    df["__ord"] = df["fish_code"].map(order).fillna(len(order)).astype(int)
    df = df.sort_values("__ord").drop(columns="__ord")
    return df

def _load_tanks_for_codes(codes: List[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=[
            "fish_code","container_id","label","status","container_type",
            "location","created_at","activated_at","deactivated_at","last_seen_at"
        ])

    # check if containers.location exists
    with _get_engine().begin() as cx:
        has_loc = pd.read_sql(
            text("""
              select 1
              from information_schema.columns
              where table_schema='public'
                and table_name='containers'
                and column_name='location'
              limit 1
            """),
            cx,
        ).shape[0] > 0

    base_sql = """
      select
        f.fish_code,
        c.id_uuid::text            as container_id,
        coalesce(c.label,'')       as label,
        coalesce(c.status,'')      as status,
        c.container_type,
        {loc_expr}                 as location,
        c.created_at,
        c.activated_at,
        c.deactivated_at,
        c.last_seen_at
      from public.fish f
      join public.fish_tank_memberships m
        on m.fish_id = f.id
       and m.left_at is null
      join public.containers c
        on c.id_uuid = m.container_id
      where f.fish_code = ANY(:codes)
      order by f.fish_code, c.created_at
    """
    loc_expr = "coalesce(c.location,'')" if has_loc else "''::text"
    sql = text(base_sql.format(loc_expr=loc_expr))

    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params={"codes": codes})

def main():
    st.title("🔎 Overview Search")

    with st.form("filters"):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            q = st.text_input("Search (multi-term; quotes & -negation supported)", "")
        with col2:
            try:
                stages = st.multiselect("Stage", _stage_choices(), default=[])
            except Exception:
                stages = []
        with col3:
            limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
        submitted = st.form_submit_button("Apply")

    # 1) Multi-term search to get matches
    rows = Q.load_fish_overview(_get_engine(), q=q, stages=stages, limit=limit)
    match_df = pd.DataFrame(rows)
    st.caption(f"{len(match_df)} matches")

    if match_df.empty:
        st.info("No rows match your filters.")
        with st.expander("Debug"):
            st.write({"VIEW": getattr(Q, "VIEW", "auto"), "search_columns": getattr(Q, "SEARCH_COLUMNS", "auto")})
            st.code(q or "", language="text")
        return

    codes_in_order = match_df["fish_code"].astype(str).tolist()

    # 2) Hydrate from canonical standard view (+ live tank counts)
    df = _load_standard_for_codes(codes_in_order)

    # 3) Build selector table (checkbox in the first column)
    base_cols = [
        "fish_code","name","nickname","genotype","genetic_background","stage",
        "date_birth","age_days","created_at","created_by","batch_display",
        "treatments_rollup","n_living_tanks"
    ]
    for c in base_cols:
        if c not in df.columns:
            df[c] = None

    view = df[base_cols].copy()
    view.insert(0, "✓ Select", False)

    # Reset selection when result set changes
    key_sig = "|".join(codes_in_order)
    if st.session_state.get("_ov_sig") != key_sig:
        st.session_state["_ov_sig"] = key_sig
        st.session_state["_ov_table"] = view.copy()

    # Controls
    csa, csb = st.columns([1,1])
    with csa:
        if st.button("Select all"):
            st.session_state["_ov_table"].loc[:, "✓ Select"] = True
    with csb:
        if st.button("Clear all"):
            st.session_state["_ov_table"].loc[:, "✓ Select"] = False

    # Render main table — full width
    edited = st.data_editor(
        st.session_state["_ov_table"],
        use_container_width=True,
        hide_index=True,
        column_config={
            "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
            "fish_code": st.column_config.TextColumn("fish_code", disabled=True),
            "name": st.column_config.TextColumn("name", disabled=True),
            "nickname": st.column_config.TextColumn("nickname", disabled=True),
            "genotype": st.column_config.TextColumn("genotype", disabled=True),
            "genetic_background": st.column_config.TextColumn("genetic_background", disabled=True),
            "stage": st.column_config.TextColumn("stage", disabled=True),
            "date_birth": st.column_config.DateColumn("date_birth", disabled=True),
            "age_days": st.column_config.NumberColumn("age_days", disabled=True),
            "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
            "created_by": st.column_config.TextColumn("created_by", disabled=True),
            "batch_display": st.column_config.TextColumn("batch_display", disabled=True),
            "treatments_rollup": st.column_config.TextColumn("treatments_rollup", disabled=True),
            "n_living_tanks": st.column_config.NumberColumn("n_living_tanks", disabled=True),
        },
        key="ov_editor",
    )
    st.session_state["_ov_table"] = edited.copy()

    # Gather selected fish codes
    selected_codes = edited.loc[edited["✓ Select"], "fish_code"].astype(str).tolist()

    # 4) Tanks table for selected fish
    st.subheader("Tanks for selected fish")
    if not selected_codes:
        st.info("Select one or more fish above to see their current tanks.")
    else:
        tanks_df = _load_tanks_for_codes(selected_codes)
        if tanks_df.empty:
            st.info("No active memberships / tanks for the selected fish.")
        else:
            tanks_df = tanks_df.sort_values(["fish_code", "created_at"], ascending=[True, False])
            tanks_view = tanks_df.rename(columns={
                "fish_code":"fish_code",
                "container_id":"container_id",
                "label":"label",
                "status":"status",
                "container_type":"type",
                "location":"location",
                "created_at":"created_at",
                "activated_at":"activated_at",
                "deactivated_at":"deactivated_at",
                "last_seen_at":"last_seen_at",
            })
            cols = ["fish_code","label","status","type","created_at","activated_at","deactivated_at","last_seen_at","container_id"]
            if "location" in tanks_view.columns:
                cols.insert(4, "location")  # after type
            st.dataframe(tanks_view[cols], use_container_width=True, hide_index=True)

    with st.expander("Debug"):
        st.write({"VIEW": getattr(Q, "VIEW", "auto"), "search_columns": getattr(Q, "SEARCH_COLUMNS", "auto")})
        st.code(q or "", language="text")

if __name__ == "__main__":
    main()

# --- CARP override: use DB_URL for SQLAlchemy engine ---
import os as _carp_os
import streamlit as _st
from sqlalchemy import create_engine as _carp_create_engine

@_st.cache_resource(show_spinner=False)
def _carp_cached_engine():
    url = _carp_os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _carp_create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1200,
        pool_size=1,
        max_overflow=0,
        connect_args={"connect_timeout": 10},
    )

def _get_engine():
    return _carp_cached_engine()
