# supabase/ui/pages/20_add_treatments.py
from __future__ import annotations

# --- sys.path before local imports ---
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]  # …/carp_v2
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Shared engine + helpers
from supabase.ui.lib_shared import current_engine, connection_info
from carp_app.lib import queries as Q

# 🔒 auth
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

from datetime import datetime, UTC
from typing import List, Dict, Any

import pandas as pd
import streamlit as st
from sqlalchemy import text

PAGE_TITLE = "CARP — Add Treatments"
st.set_page_config(page_title=PAGE_TITLE, page_icon="💉", layout="wide")
st.title("💉 Add Treatments")

# Engine + DB info
eng = current_engine()
dbg = connection_info(eng)
st.caption(f"DB debug → db={dbg['db']} user={dbg['user']}")

# Refresh (clear caches and sticky editor state)
if st.button("🔁 Refresh data", key="treat_refresh"):
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    for k in list(st.session_state.keys()):
        if k in ("treat_picker_grid",):
            st.session_state.pop(k, None)
    st.rerun()

# ---------- Ensure treatment tables (idempotent) ----------
def ensure_treatment_objects(conn) -> None:
    conn.execute(text("""
    do $$
    begin
      if to_regclass('public.injected_plasmid_treatments') is null then
        create table public.injected_plasmid_treatments(
          id uuid primary key default gen_random_uuid(),
          fish_id uuid not null references public.fish(id) on delete cascade,
          plasmid_id uuid not null,
          amount numeric null,
          units text null,
          at_time timestamptz null,
          note text null
        );
      end if;

      if to_regclass('public.injected_rna_treatments') is null then
        create table public.injected_rna_treatments(
          id uuid primary key default gen_random_uuid(),
          fish_id uuid not null references public.fish(id) on delete cascade,
          rna_id uuid not null,
          amount numeric null,
          units text null,
          at_time timestamptz null,
          note text null
        );
      end if;
    end$$;
    """))

# ---------- Fish picker (from canonical view only) ----------
st.subheader("Pick fish to treat")

col_find, col_limit = st.columns([3, 1])
with col_find:
    qfish = st.text_input("Search fish (code or name)", "", placeholder="e.g., FSH-2025-05 or mem-tdmSG")
with col_limit:
    row_limit = st.number_input("Limit", min_value=50, max_value=5000, value=200, step=50)

def load_fish_minimal(q: str, limit: int) -> pd.DataFrame:
    with eng.begin() as conn:
        rows = Q.fish_overview_minimal(conn, q=q, limit=limit, require_links=True)
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
        "id","fish_code","name","created_at","created_by",
        "transgene_base_code_filled","allele_code_filled"
    ])
    # normalize types
    if "id" in df.columns:
        df["id"] = df["id"].astype(str)
    return df[["id", "fish_code", "name"]]

df = load_fish_minimal(qfish, int(row_limit))
if df.empty:
    st.info("No fish matched. Try a different search.")
    st.stop()

grid = df.copy().set_index("id")
grid.insert(0, "select", False)

edited = st.data_editor(
    grid,
    key="treat_picker_grid",
    width="stretch",
    hide_index=False,
    column_config={
        "select": st.column_config.CheckboxColumn("Select"),
        "fish_code": st.column_config.TextColumn("Fish code"),
        "name": st.column_config.TextColumn("Name"),
    },
)
selected_ids = [str(idx) for idx, sel in edited["select"].items() if sel]
sel_df = df[df["id"].isin(selected_ids)]
st.caption(f"Selected: **{len(selected_ids)}** fish")

# Diagnostic: show counts so it's obvious what source contains what
with eng.begin() as conn:
    base_ct  = conn.execute(text("select count(*) from public.v_fish_overview")).scalar()
    label_ct = conn.execute(text("select count(*) from public.vw_fish_overview_with_label")).scalar()
    fish_ct  = conn.execute(text("select count(*) from public.fish")).scalar()
st.caption(f"Diagnostic → v_fish_overview: {base_ct} • vw_with_label: {label_ct} • fish table: {fish_ct}")

# ---------- Treatment forms ----------
st.subheader("Treatment details")

colp, colr = st.columns(2)
with colp:
    st.markdown("**Plasmid treatment**")
    apply_plasmid = st.checkbox("Enable plasmid", value=False)
    plasmid_id = st.text_input("plasmid_id (UUID)", value="")
    plasmid_amount = st.number_input("amount", value=0.0, step=0.1, format="%.3f")
    plasmid_units = st.text_input("units", value="ng")
    plasmid_note = st.text_input("note", value="")
with colr:
    st.markdown("**RNA treatment**")
    apply_rna = st.checkbox("Enable RNA", value=False)
    rna_id = st.text_input("rna_id (UUID)", value="")
    rna_amount = st.number_input("amount (RNA)", value=0.0, step=0.1, format="%.3f")
    rna_units = st.text_input("units (RNA)", value="ng")
    rna_note = st.text_input("note (RNA)", value="")

col_btn1, col_btn2 = st.columns([1, 1])
do_plasmid = col_btn1.button("💉 Apply plasmid to selected", disabled=not (apply_plasmid and selected_ids and plasmid_id.strip()))
do_rna     = col_btn2.button("🧬 Apply RNA to selected",     disabled=not (apply_rna and selected_ids and rna_id.strip()))

# ---------- Apply actions ----------
def _apply_plasmid(ids: List[str]) -> Dict[str, Any]:
    ok, fail = 0, 0
    now = datetime.now(UTC)
    with eng.begin() as conn:
        ensure_treatment_objects(conn)
        for fid in ids:
            try:
                conn.execute(
                    text("""
                        insert into public.injected_plasmid_treatments
                          (id, fish_id, plasmid_id, amount, units, at_time, note)
                        values (gen_random_uuid(), :fish_id, :plasmid_id, :amount, :units, :at_time, :note)
                        on conflict do nothing
                    """),
                    {
                        "fish_id": fid,
                        "plasmid_id": plasmid_id.strip(),
                        "amount": None if plasmid_amount == 0 else plasmid_amount,
                        "units": plasmid_units.strip() or None,
                        "at_time": now,
                        "note": plasmid_note.strip() or None,
                    },
                )
                ok += 1
            except Exception:
                fail += 1
    return {"ok": ok, "fail": fail}

def _apply_rna(ids: List[str]) -> Dict[str, Any]:
    ok, fail = 0, 0
    now = datetime.now(UTC)
    with eng.begin() as conn:
        ensure_treatment_objects(conn)
        for fid in ids:
            try:
                conn.execute(
                    text("""
                        insert into public.injected_rna_treatments
                          (id, fish_id, rna_id, amount, units, at_time, note)
                        values (gen_random_uuid(), :fish_id, :rna_id, :amount, :units, :at_time, :note)
                        on conflict do nothing
                    """),
                    {
                        "fish_id": fid,
                        "rna_id": rna_id.strip(),
                        "amount": None if rna_amount == 0 else rna_amount,
                        "units": rna_units.strip() or None,
                        "at_time": now,
                        "note": rna_note.strip() or None,
                    },
                )
                ok += 1
            except Exception:
                fail += 1
    return {"ok": ok, "fail": fail}

if do_plasmid:
    if not selected_ids:
        st.warning("Select at least one fish.")
    elif not plasmid_id.strip():
        st.warning("Provide a plasmid_id (UUID).")
    else:
        with st.spinner(f"Applying plasmid to {len(selected_ids)} fish…"):
            res = _apply_plasmid(selected_ids)
        st.success(f"Plasmid applied to {res['ok']} fish; {res['fail']} failed.")
        st.toast("Plasmid treatment saved.", icon="✅")

if do_rna:
    if not selected_ids:
        st.warning("Select at least one fish.")
    elif not rna_id.strip():
        st.warning("Provide an rna_id (UUID).")
    else:
        with st.spinner(f"Applying RNA to {len(selected_ids)} fish…"):
            res = _apply_rna(selected_ids)
        st.success(f"RNA applied to {res['ok']} fish; {res['fail']} failed.")
        st.toast("RNA treatment saved.", icon="✅")

# ---------- Review ----------
st.divider()
st.subheader("Review selected")

if sel_df.empty:
    st.info("No fish selected.")
else:
    st.dataframe(sel_df, width="stretch")

st.caption(
    "Picker reads from the canonical view `v_fish_overview` (so no orphan rows). "
    "Treatments are recorded in `injected_plasmid_treatments` / `injected_rna_treatments`."
)