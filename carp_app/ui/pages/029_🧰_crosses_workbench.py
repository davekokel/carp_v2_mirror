from __future__ import annotations
import sys, pathlib, os
from datetime import date
import pandas as pd
import streamlit as st

# repo root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- Page config
st.set_page_config(page_title="🧰 Crosses & Clutches — Workbench", page_icon="🧰", layout="wide")
st.title("🧰 Crosses & Clutches — Workbench")

# --- Context (shared across tabs & pages)
WB = st.session_state.setdefault("wb", {})
WB.setdefault("clutch_code", "")
WB.setdefault("run_code", "")
WB.setdefault("created_by", os.environ.get("USER") or os.environ.get("USERNAME") or "")
WB.setdefault("date", date.today())

# Accept query params (deep links), if available
try:
    q = st.query_params  # Streamlit ≥1.30
    if "clutch" in q: WB["clutch_code"] = q["clutch"]
    if "run"    in q: WB["run_code"]    = q["run"]
    if "by"     in q: WB["created_by"]  = q["by"]
    if "date"   in q:
        try: WB["date"] = date.fromisoformat(q["date"])
        except Exception: pass
except Exception:
    pass

# --- Chips (always visible)
c1, c2, c3, c4 = st.columns([2,2,2,2])
with c1:
    WB["clutch_code"] = st.text_input("Clutch code", value=WB["clutch_code"], placeholder="CL-…")
with c2:
    WB["run_code"] = st.text_input("Run code", value=WB["run_code"], placeholder="XR-…")
with c3:
    WB["date"] = st.date_input("Date", value=WB["date"])
with c4:
    WB["created_by"] = st.text_input("Created by", value=WB["created_by"])

st.caption("Tip: these chips persist across tabs and are passed to the legacy pages so you don’t have to retype.")

# --- Tabs = the 4 jobs
tab_plan, tab_run, tab_annotate, tab_review = st.tabs(["Plan", "Run", "Annotate", "Review"])

# Small helper for deep-linking into legacy pages while passing state
def _goto(rel_page_path: str, **state):
    # stash any prefill keys the destination understands
    for k, v in (state or {}).items():
        st.session_state[k] = v
    try:
        st.switch_page(rel_page_path)  # relative to main or pages/
    except Exception:
        st.warning(f"Could not switch to {rel_page_path}. Make sure the path is correct and in pages/.")

# -------------------- PLAN --------------------
with tab_plan:
    st.subheader("Plan: clutches & crosses")
    st.write("Create or edit clutch concepts, and plan crosses.")

    cpa, cpb, cpc = st.columns([1,1,2])
    with cpa:
        if st.button("➡️ Enter new clutches", use_container_width=True):
            _goto("pages/030_🐟_enter_new_clutches.py")
    with cpb:
        if st.button("➡️ Enter new crosses", use_container_width=True):
            _goto("pages/031_🐟_enter_new_crosses.py")
    with cpc:
        st.caption("Use these to curate concepts and make them runnable.")

    st.divider()
    st.write("Quick open:")
    colA, colB = st.columns([1,1])
    with colA:
        if st.button("🔎 Overview — Crosses", use_container_width=True):
            _goto("pages/023_🔎_overview_crosses.py")
    with colB:
        if st.button("🔎 Overview — Clutches", use_container_width=True):
            _goto("pages/024_🔎_Overview_Clutches.py")

# -------------------- RUN --------------------
with tab_run:
    st.subheader("Run: schedule / create cross instances (XR)")
    st.write("Pick a concept and schedule run(s). Your chips will prefill where supported.")

    c1, c2 = st.columns([1,1])
    with c1:
        if st.button("➡️ Enter cross instance (schedule & labels)", use_container_width=True):
            # pass creator and (optionally) clutch filter via session_state
            _goto("pages/032_🏷️_enter_cross_instance.py",
                  **{"wb.created_by": WB["created_by"], "wb.clutch_code": WB["clutch_code"], "wb.date": WB["date"]})
    with c2:
        st.caption("After creating XR-…, jump to Annotate to record CI selections.")

    st.divider()
    st.write("Recent helpers")
    st.caption("You can also jump straight into daily overviews:")
    if st.button("📊 Daily Overviews (All)", use_container_width=True):
        _goto("pages/026_🔎_daily_overview.py")

# -------------------- ANNOTATE --------------------
with tab_annotate:
    st.subheader("Annotate: clutch selections (CI)")
    st.write("Select a run, then quick annotate red/green/notes; print tank labels.")

    ca, cb = st.columns([1,1])
    with ca:
        if st.button("➡️ Annotate clutch instances", use_container_width=True):
            # If a run is known, we can nudge the annotate page via prefill key it already supports.
            prefill = {}
            if WB["run_code"]:
                prefill["annotate_prefill_run"] = WB["run_code"]
            _goto("pages/034_🐣_annotate_clutch_instances.py", **prefill)
    with cb:
        st.caption("If you came from a scheduled XR, the run chip should already be set.")

# -------------------- REVIEW --------------------
with tab_review:
    st.subheader("Review: search, KPIs, and exports")
    st.write("Crosses & clutches overviews and daily KPIs.")

    ra, rb, rc = st.columns([1,1,1])
    with ra:
        if st.button("🔎 Overview — Crosses", use_container_width=True):
            _goto("pages/023_🔎_overview_crosses.py")
    with rb:
        if st.button("🔎 Overview — Clutches", use_container_width=True):
            _goto("pages/024_🔎_Overview_Clutches.py")
    with rc:
        if st.button("📊 Daily Overviews (All)", use_container_width=True):
            _goto("pages/026_🔎_daily_overview.py")

st.divider()

# -------------------- Right rail (print panel placeholder) --------------------
st.subheader("Quick Print (labels)")
st.caption("This panel will evolve; for now use the target pages to generate labels. Chips above persist between tabs.")