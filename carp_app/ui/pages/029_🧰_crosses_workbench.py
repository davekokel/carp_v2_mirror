from __future__ import annotations

import os
import re
import io
import sys
import json
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.lib.db import get_engine

# Label builders
from carp_app.ui.lib.labels_components import (
    build_crossing_tank_labels_pdf,
    build_petri_labels_pdf,
)

st.set_page_config(page_title="🧰 Crosses Workbench", page_icon="🧰", layout="wide")
st.title("🧰 Crosses Workbench")

# --- Session "chips" state ---
if "wb" not in st.session_state or not isinstance(st.session_state["wb"], dict):
    st.session_state["wb"] = {}

wb = st.session_state["wb"]
wb.setdefault("date", date.today())
wb.setdefault("created_by", os.getenv("USER") or os.getenv("USERNAME") or "unknown")
wb.setdefault("run_code", "")
wb.setdefault("clutch_code", "")

# --- Engine / env ---
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    st.error("DB_URL not set"); st.stop()
eng = get_engine()

DEFAULT_QUEUE = os.getenv("CUPS_QUEUE", "Brother_QL_1110NWB")
DEFAULT_MEDIA = os.getenv("CUPS_MEDIA", "Custom.61x38mm")

# --- Import helpers from 032_🏷️_enter_cross_instance.py if present ---
def _import_enter_cross_instance_module() -> Optional[Any]:
    try:
        here = Path(__file__).resolve()
        root = here.parents[3]
        target = root / "carp_app" / "ui" / "pages" / "032_🏷️_enter_cross_instance.py"
        if not target.exists():
            return None
        import importlib.util
        spec = importlib.util.spec_from_file_location("enter_cross_instance_032", str(target))
        if not spec or not spec.loader:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["enter_cross_instance_032"] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None

_eci = _import_enter_cross_instance_module()

# --- Runnable concepts loader (reuse SQL from 032 when available) ---
def _fetch_runnable_concepts(
    q: str,
    run_date: date,
    created_by: str,
    limit: int = 500,
) -> pd.DataFrame:
    # Prefer using helper from 032 if provided
    if _eci:
        # Try common function names before falling back
        for fname in ("fetch_runnable_concepts", "_fetch_runnable_concepts", "load_runnable_concepts"):
            fn = getattr(_eci, fname, None)
            if callable(fn):
                try:
                    df = fn(eng, q=q, run_date=run_date, created_by=created_by, limit=limit)
                    return df
                except TypeError:
                    try:
                        df = fn(eng, q, run_date, created_by, limit)  # older sig
                        return df
                    except Exception:
                        pass

        # Try to pull the raw SQL constant if exposed
        sql_text = getattr(_eci, "SQL_RUNNABLE_CONCEPTS", None)
        if isinstance(sql_text, str) and "with live_by_fish" in sql_text.lower():
            return pd.read_sql_query(text(sql_text), eng, params={"q": f"%{q.strip()}%", "limit": limit, "run_date": run_date})

    # Fallback (minimal, intended as placeholder; replace with exact 032 SQL if available)
    # TODO: Replace this block with the exact CTEs from 032_🏷️_enter_cross_instance.py to avoid drift.
    sql_fallback = """
    with latest_runs as (
      select c.id as cross_id, max(ci.cross_date) as latest_run_date
      from public.crosses c
      left join public.cross_instances ci on ci.cross_id = c.id
      group by c.id
    ),
    crosses_base as (
      select
        c.id as cross_id,
        c.cross_code,
        coalesce(nullif(c.cross_name,''), c.cross_code) as cross_name,
        coalesce(nullif(c.cross_nickname,''), '') as cross_nickname,
        c.mom_fish_id,
        c.dad_fish_id
      from public.crosses c
      where c.is_active is true
    ),
    mom as (
      select f.id as fish_id, f.fish_code, t.tank_code as mom_tank_code, t.is_live as mom_live
      from public.fish f
      left join public.tanks t on t.fish_id = f.id and t.is_live is true
    ),
    dad as (
      select f.id as fish_id, f.fish_code, t.tank_code as dad_tank_code, t.is_live as dad_live
      from public.fish f
      left join public.tanks t on t.fish_id = f.id and t.is_live is true
    )
    select
      b.cross_id,
      b.cross_code,
      b.cross_name,
      b.cross_nickname,
      mom.fish_code as mom_code,
      dad.fish_code as dad_code,
      mom.mom_tank_code,
      dad.dad_tank_code,
      coalesce(mom.mom_live, false) as mom_live,
      coalesce(dad.dad_live, false) as dad_live,
      lr.latest_run_date
    from crosses_base b
    left join mom on mom.fish_id = b.mom_fish_id
    left join dad on dad.fish_id = b.dad_fish_id
    left join latest_runs lr on lr.cross_id = b.cross_id
    where
      (coalesce(:q,'') = '' or
       b.cross_code ilike :q or b.cross_name ilike :q or b.cross_nickname ilike :q
       or mom.fish_code ilike :q or dad.fish_code ilike :q
       or mom.mom_tank_code ilike :q or dad.dad_tank_code ilike :q)
      and coalesce(mom_live,false) = true
      and coalesce(dad_live,false) = true
    order by b.cross_code
    limit :limit;
    """
    params = {"q": f"%{q.strip()}%" if q else "", "limit": limit, "run_date": run_date}
    return pd.read_sql_query(text(sql_fallback), eng, params=params)

# --- Schedule insert (prefer 032 helper) ---
def _schedule_instances(
    cross_ids: List[str],
    run_date: date,
    created_by: str,
    note: str = "",
) -> List[Dict[str, Any]]:
    # Try to reuse _schedule_instance from 032
    if _eci and hasattr(_eci, "_schedule_instance"):
        fn = getattr(_eci, "_schedule_instance")
        out = []
        for cid in cross_ids:
            rec = fn(eng, cross_id=cid, cross_date=run_date, created_by=created_by, note=note)
            # Expecting dict with keys id, cross_run_code, clutch_code (if created)
            out.append(rec)
        return out

    # Fallback inline equivalent
    sql = text("""
    insert into public.cross_instances (cross_id, cross_date, note, created_by)
    values (:cross_id, :cross_date, :note, :created_by)
    returning id, cross_run_code;
    """)
    results = []
    with eng.begin() as cx:
        for cid in cross_ids:
            row = cx.execute(sql, {"cross_id": cid, "cross_date": run_date, "note": note, "created_by": created_by}).mappings().first()
            results.append({"id": row["id"], "cross_run_code": row["cross_run_code"], "clutch_code": None})
    return results

# --- CUPS print helper ---
def _send_pdf_to_cups(pdf_bytes: bytes, queue: str, media: str) -> subprocess.CompletedProcess:
    tmp = Path(st.experimental_user().user_id if hasattr(st, "experimental_user") else "._tmp_user")
    tmp.mkdir(exist_ok=True)
    fn = tmp / f"run_labels_{date.today().isoformat()}.pdf"
    fn.write_bytes(pdf_bytes)
    # -o raw rarely needed on QL_1110; media typically Custom.61x38mm
    cmd = ["lp", "-d", queue]
    if media:
        cmd += ["-o", f"media={media}"]
    cmd += [str(fn)]
    return subprocess.run(cmd, capture_output=True, text=True)

# --- UI Tabs (Run implemented inline; others as launchers) ---
tabs = st.tabs(["Run", "Plan", "Annotate", "Review"])
tab_run, tab_plan, tab_annotate, tab_review = tabs

with tab_run:
    st.subheader("Run crosses inline")

    # Filters row
    cols = st.columns([1, 1, 2, 2], vertical_alignment="center")
    with cols[0]:
        wb["date"] = st.date_input("Run date", value=wb["date"], key="run_date", format="YYYY-MM-DD")
    with cols[1]:
        wb["created_by"] = st.text_input("Created by", value=wb["created_by"], key="run_created_by")
    with cols[2]:
        q = st.text_input("Search concepts", value="", key="run_search")
    with cols[3]:
        st.caption("Workbench chips")
        chip_cols = st.columns(2)
        with chip_cols[0]:
            st.write(f"XR: `{wb.get('run_code') or ''}`")
        with chip_cols[1]:
            st.write(f"CL: `{wb.get('clutch_code') or ''}`")

    # Load runnable concepts
    df = _fetch_runnable_concepts(q=q, run_date=wb["date"], created_by=wb["created_by"])
    if df.empty:
        st.info("No runnable concepts found for the current filters.")
    else:
        # Add selection column for data_editor
        df_view = df.copy()
        df_view.insert(0, "✓", False)

        st.caption("Runnable concepts")
        edited = st.data_editor(
            df_view,
            key="run_editor",
            use_container_width=False,
            width=1200,
            hide_index=True,
            column_config={
                "✓": st.column_config.CheckboxColumn(required=False, width="small"),
                "cross_code": st.column_config.TextColumn(width="medium"),
                "cross_name": st.column_config.TextColumn(label="cross_name (code)", width="large"),
                "cross_nickname": st.column_config.TextColumn(label="nick / genotype", width="large"),
                "mom_code": st.column_config.TextColumn(width="medium"),
                "dad_code": st.column_config.TextColumn(width="medium"),
                "mom_tank_code": st.column_config.TextColumn(width="medium"),
                "dad_tank_code": st.column_config.TextColumn(width="medium"),
                "mom_live": st.column_config.CheckboxColumn(disabled=True, width="small"),
                "dad_live": st.column_config.CheckboxColumn(disabled=True, width="small"),
                "latest_run_date": st.column_config.DatetimeColumn(format="YYYY-MM-DD", width="small"),
            }
        )

        chosen = edited.index[edited["✓"] == True].tolist()
        selected_rows = df.iloc[chosen] if len(chosen) else pd.DataFrame()

        st.divider()

        # Schedule panel
        st.markdown("### Schedule")
        scol = st.columns([2, 3, 2, 2, 2, 3], vertical_alignment="center")
        with scol[0]:
            run_date_val = st.date_input("Date", value=wb["date"], key="sched_date", format="YYYY-MM-DD")
        with scol[1]:
            note_val = st.text_input("Note (optional)", value="", key="sched_note")
        with scol[2]:
            st.write("")
            st.write(f"Selected: **{len(selected_rows)}**")
        with scol[3]:
            btn_sched = st.button(
                f"Create {len(selected_rows)} run(s)" if len(selected_rows) else "Create runs",
                key="btn_create_runs",
                disabled=(len(selected_rows) == 0),
                width="stretch",
            )
        with scol[4]:
            btn_clear = st.button("Clear selection", key="btn_clear_sel", width="stretch")
        with scol[5]:
            btn_reload = st.button("Reload list", key="btn_reload_list", width="stretch")

        if btn_clear:
            st.session_state["run_editor"] = df_view  # reset edited table
            st.rerun()

        if btn_reload:
            st.rerun()

        created_runs: List[Dict[str, Any]] = []
        if btn_sched and len(selected_rows):
            try:
                cross_ids = selected_rows["cross_id"].astype(str).tolist()
                created_runs = _schedule_instances(
                    cross_ids=cross_ids,
                    run_date=run_date_val,
                    created_by=wb["created_by"],
                    note=note_val or "",
                )
                if created_runs:
                    # Update chips from most recent record
                    last = created_runs[-1]
                    wb["run_code"] = last.get("cross_run_code") or wb.get("run_code", "")
                    wb["clutch_code"] = last.get("clutch_code") or wb.get("clutch_code", "")
                st.success(f"Created {len(created_runs)} run(s).")
                with st.expander("Created XR codes", expanded=True):
                    st.write(", ".join([r.get("cross_run_code") for r in created_runs if r.get("cross_run_code")]) or "—")
            except Exception as e:
                st.error(f"Failed to create runs: {e}")

        st.divider()

        # Labels panel
        st.markdown("### Labels")
        # Decide which XR codes to print labels for: prefer newly created, else allow selecting prior selection by cross info
        xr_codes_for_labels: List[str] = [r["cross_run_code"] for r in created_runs if r.get("cross_run_code")]
        if not xr_codes_for_labels:
            st.caption("No new XR codes from this action; enter XR codes manually (comma-separated) if you want labels.")
            manual_xr = st.text_input("XR codes", value=wb.get("run_code") or "", key="labels_xr_input")
            if manual_xr.strip():
                xr_codes_for_labels = [s.strip() for s in manual_xr.split(",") if s.strip()]

        # Build PDFs only when asked
        lcols = st.columns([2, 2, 3, 3, 2], vertical_alignment="center")
        with lcols[0]:
            btn_build_cross = st.button("⬇️ Crossing labels (2.4×1.0)", key="btn_dl_cross", disabled=(len(xr_codes_for_labels) == 0), width="stretch")
        with lcols[1]:
            btn_build_petri = st.button("⬇️ Petri labels (2.4×0.75)", key="btn_dl_petri", disabled=(len(xr_codes_for_labels) == 0), width="stretch")
        with lcols[2]:
            queue = st.text_input("CUPS queue", value=DEFAULT_QUEUE, key="cups_queue")
        with lcols[3]:
            media = st.text_input("Media", value=DEFAULT_MEDIA, key="cups_media")
        with lcols[4]:
            btn_send = st.button("🖨️ Send to Brother", key="btn_send_cups", disabled=(len(xr_codes_for_labels) == 0), width="stretch")

        # Crossing labels
        if btn_build_cross and xr_codes_for_labels:
            try:
                pdf_bytes = build_crossing_tank_labels_pdf(engine=eng, cross_run_codes=xr_codes_for_labels)
                st.download_button(
                    "Download Crossing Labels PDF",
                    data=pdf_bytes,
                    file_name=f"crossing_labels_{date.today().isoformat()}.pdf",
                    mime="application/pdf",
                    key="dl_cross_pdf",
                    type="primary",
                )
            except Exception as e:
                st.error(f"Failed to build crossing labels: {e}")

        # Petri labels
        if btn_build_petri and xr_codes_for_labels:
            try:
                pdf_bytes = build_petri_labels_pdf(engine=eng, cross_run_codes=xr_codes_for_labels)
                st.download_button(
                    "Download Petri Labels PDF",
                    data=pdf_bytes,
                    file_name=f"petri_labels_{date.today().isoformat()}.pdf",
                    mime="application/pdf",
                    key="dl_petri_pdf",
                    type="primary",
                )
            except Exception as e:
                st.error(f"Failed to build petri labels: {e}")

        # Send to CUPS
        if btn_send and xr_codes_for_labels:
            try:
                pdf_cross = build_crossing_tank_labels_pdf(engine=eng, cross_run_codes=xr_codes_for_labels)
                r1 = _send_pdf_to_cups(pdf_cross, queue=queue, media=media)
                msg1 = "Crossing labels sent" if r1.returncode == 0 else f"Crossing labels failed: {r1.stderr}"
                # Petri optional
                try:
                    pdf_petri = build_petri_labels_pdf(engine=eng, cross_run_codes=xr_codes_for_labels)
                    r2 = _send_pdf_to_cups(pdf_petri, queue=queue, media=media)
                    msg2 = "Petri labels sent" if r2.returncode == 0 else f"Petri labels failed: {r2.stderr}"
                except Exception as ee:
                    msg2 = f"Petri labels build failed: {ee}"
                st.toast(f"{msg1} · {msg2}", icon="🖨️")
            except FileNotFoundError:
                st.error("Printing requires `lp` (CUPS). Not found on this system.")
            except Exception as e:
                st.error(f"Printing failed: {e}")

        st.divider()

        # CTA: Go to Annotate
        cta = st.columns([3, 2, 2, 3])
        with cta[1]:
            # Prefill annotate with the last XR if available
            prefill_xr = (xr_codes_for_labels[-1] if xr_codes_for_labels else (wb.get("run_code") or "")).strip()
            st.text_input("Annotate prefill XR", value=prefill_xr, key="annotate_prefill_xr")
        with cta[2]:
            if st.button("➡️ Go to Annotate", key="btn_go_annotate", width="stretch"):
                if st.session_state.get("annotate_prefill_xr"):
                    wb["run_code"] = st.session_state["annotate_prefill_xr"]
                # Prefer going straight to the Annotate page
                try:
                    st.switch_page("carp_app/ui/pages/034_🐣_annotate_clutch_instances.py")
                except Exception:
                    st.info("Annotate page not found; staying on Workbench.")

with tab_plan:
    st.caption("Launch dedicated pages while we keep building inline flows:")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("030 🐟 Enter New Clutches", key="btn_launch_030", width="stretch"):
            try:
                st.switch_page("carp_app/ui/pages/030_🐟_enter_new_clutches.py")
            except Exception:
                st.info("Page not found.")
    with c2:
        if st.button("031 🐟 Enter New Crosses", key="btn_launch_031", width="stretch"):
            try:
                st.switch_page("carp_app/ui/pages/031_🐟_enter_new_crosses.py")
            except Exception:
                st.info("Page not found.")

with tab_annotate:
    st.caption("Jump to Annotate page:")
    if st.button("034 🐣 Annotate Clutch Instances", key="btn_launch_034", width="stretch"):
        try:
            st.switch_page("carp_app/ui/pages/034_🐣_annotate_clutch_instances.py")
        except Exception:
            st.info("Page not found.")

with tab_review:
    st.caption("Overviews:")
    r1, r2, r3 = st.columns(3)
    if r1.button("023 🔎 Overview Crosses", key="btn_launch_023", width="stretch"):
        try: st.switch_page("carp_app/ui/pages/023_🔎_overview_crosses.py")
        except Exception: st.info("Page not found.")
    if r2.button("024 🔎 Overview Clutches", key="btn_launch_024", width="stretch"):
        try: st.switch_page("carp_app/ui/pages/024_🔎_Overview_Clutches.py")
        except Exception: st.info("Page not found.")
    if r3.button("026 🔎 Daily Overview", key="btn_launch_026", width="stretch"):
        try: st.switch_page("carp_app/ui/pages/026_🔎_daily_overview.py")
        except Exception: st.info("Page not found.")