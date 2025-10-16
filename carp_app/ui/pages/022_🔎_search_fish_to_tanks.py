from __future__ import annotations

# --- repo path shim ---
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- auth gates (match other pages) ---
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

# --- std/3p ---
import os
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# --- engine (URL-first, cached) ---
from carp_app.lib.db import get_engine as _create_engine

@st.cache_resource(show_spinner=False)
def _cached_engine():
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _get_engine() -> Engine:
    return _cached_engine()

# --- helpers ---
from carp_app.lib.queries import load_fish_overview_human

st.set_page_config(page_title="CARP — Search Fish → Tanks", page_icon="🔎", layout="wide")

def _normalize_q(q_raw: str) -> str | None:
    q = (q_raw or "").strip()
    return q or None

def _load_tanks_for_codes(codes: list[str]) -> pd.DataFrame:
    """Current tanks for given fish_code list, resilient to left_at/ended_at schema."""
    if not codes:
        return pd.DataFrame(columns=[
            "fish_code","container_id","label","status","container_type",
            "location","created_at","activated_at","deactivated_at","last_seen_at"
        ])
    # presence of containers.location
    with _get_engine().begin() as cx:
        has_loc = pd.read_sql(
            text("""
              select 1
              from information_schema.columns
              where table_schema='public'
                and table_name='containers'
                and column_name='location'
              limit 1
            """), cx
        ).shape[0] > 0

    base_sql = """
      select
        f.fish_code,
        c.id::text             as container_id,
        coalesce(c.label,'')   as label,
        coalesce(c.status,'')  as status,
        c.container_type,
        {loc_expr}             as location,
        c.created_at,
        c.activated_at,
        c.deactivated_at,
        c.last_seen_at
      from public.fish f
      join public.fish_tank_memberships m
        on m.fish_id = f.id
      join public.containers c
        on c.id = m.container_id
      where f.fish_code = any(:codes)
        and (
          coalesce(
            nullif(to_jsonb(m)->>'left_at','')::timestamptz,
            nullif(to_jsonb(m)->>'ended_at','')::timestamptz
          ) is null
        )
      order by f.fish_code, c.created_at desc nulls last
    """
    loc_expr = "coalesce(c.location,'')" if has_loc else "''::text"
    sql = text(base_sql.format(loc_expr=loc_expr))
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params={"codes": codes})

def main():
    st.title("🔎 Search Fish → Tanks")

    with st.form("filters"):
        c1, c2 = st.columns([3,1])
        with c1:
            q_raw = st.text_input("Search fish (multi-term; quotes & -negation supported)", "")
        with c2:
            limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
        st.form_submit_button("Search")

    q = _normalize_q(q_raw)

    # 1) search fish (human-friendly overview)
    try:
        fish_rows = load_fish_overview_human(_get_engine(), q=q, stages=None, limit=limit)
    except Exception as e:
        st.error(f"Query error: {type(e).__name__}: {e}")
        with st.expander("Debug"):
            st.code(str(e))
        return

    if not fish_rows:
        st.info("No fish match your search.")
        return

    fish_df = pd.DataFrame(fish_rows)
    # Order & relabel for humans
    fish_cols = [c for c in [
        "fish_code","fish_name","fish_nickname","genetic_background",
        "allele_code","transgene","genotype_rollup",
        "tank_code","tank_label","tank_status",
        "date_birth","created_at","created_by"
    ] if c in fish_df.columns]
    fish_view = fish_df[fish_cols].rename(columns={
        "fish_code":"Fish code",
        "fish_name":"Name",
        "fish_nickname":"Nickname",
        "genetic_background":"Background",
        "allele_code":"Allele code",
        "transgene":"Transgene",
        "genotype_rollup":"Genotype rollup",
        "tank_code":"Tank code",
        "tank_label":"Tank label",
        "tank_status":"Tank status",
        "date_birth":"Birth date",
        "created_at":"Created",
        "created_by":"Created by",
    }).copy()

    st.subheader("Fish (select to see tanks)")
    view = fish_view.copy()
    view.insert(0, "✓ Select", False)

    # reset selection when results change
    key_sig = "|".join(fish_df["fish_code"].astype(str).tolist())
    if st.session_state.get("_sft_sig") != key_sig:
        st.session_state["_sft_sig"] = key_sig
        st.session_state["_sft_table"] = view.copy()

    csa, csb, csc = st.columns([1,1,2])
    with csa:
        if st.button("Select all"):
            st.session_state["_sft_table"].loc[:, "✓ Select"] = True
    with csb:
        if st.button("Clear all"):
            st.session_state["_sft_table"].loc[:, "✓ Select"] = False
    with csc:
        st.caption(f"{len(fish_view)} fish")

    edited = st.data_editor(
        st.session_state["_sft_table"],
        use_container_width=True,
        hide_index=True,
        key="sft_editor",
    )
    st.session_state["_sft_table"] = edited.copy()

    selected_codes = edited.loc[edited["✓ Select"], "Fish code"].astype(str).tolist()

    # 2) tanks for selected fish
    st.subheader("Current tanks for selected fish")
    if not selected_codes:
        st.info("Select one or more fish above to see their current tanks.")
        return

    tanks_df = _load_tanks_for_codes(selected_codes)
    if tanks_df.empty:
        st.info("No active memberships / tanks for selected fish.")
        return

    tanks_view = tanks_df.rename(columns={
        "fish_code":"Fish code",
        "container_id":"Container ID",
        "label":"Label",
        "status":"Status",
        "container_type":"Type",
        "location":"Location",
        "created_at":"Created",
        "activated_at":"Activated",
        "deactivated_at":"Deactivated",
        "last_seen_at":"Last seen",
    })

    cols = ["Fish code","Label","Status","Type","Created","Activated","Deactivated","Last seen","Container ID"]
    if "Location" in tanks_view.columns:
        cols.insert(4, "Location")

    st.dataframe(tanks_view[cols], use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()