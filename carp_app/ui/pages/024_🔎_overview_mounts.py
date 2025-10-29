# carp_app/ui/pages/024_🔎_overview_mounts.py
from __future__ import annotations

import os
import sys
import pathlib
from datetime import datetime
from typing import Optional, List

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ── sys.path prime ────────────────────────────────────────────────────────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── auth gates ────────────────────────────────────────────────────────────────
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

# ── app libs ─────────────────────────────────────────────────────────────────
from carp_app.ui.lib.app_ctx import get_engine as _create_engine
from carp_app.lib.time import utc_today

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="CARP — 🔎 Overview Mounts", page_icon="🔎", layout="wide")
st.title("🔎 Overview Mounts")

# ── engine cache ─────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _eng() -> Engine:
    return _cached_engine()

# ── helpers ──────────────────────────────────────────────────────────────────
def _view_exists(schema: str, name: str) -> bool:
    q = text("""
      select 1
      from information_schema.views
      where table_schema=:s and table_name=:n
      limit 1
    """)
    with _eng().begin() as cx:
        return pd.read_sql(q, cx, params={"s": schema, "n": name}).shape[0] > 0

def _table_exists(schema: str, name: str) -> bool:
    q = text("""
      select 1
      from information_schema.tables
      where table_schema=:s and table_name=:n
      limit 1
    """)
    with _eng().begin() as cx:
        return pd.read_sql(q, cx, params={"s": schema, "n": name}).shape[0] > 0

def _columns(schema: str, name: str) -> list[str]:
    q = text("""
      select column_name
      from information_schema.columns
      where table_schema=:s and table_name=:n
      order by ordinal_position
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(q, cx, params={"s": schema, "n": name})
    return df["column_name"].tolist()

def _fetch_mounts(schema: str, name: str, day: Optional[pd.Timestamp]) -> pd.DataFrame:
    cols = _columns(schema, name)
    # preferred date column order
    date_candidates = ["mounted_at", "time_mounted", "imaged_at", "created_at", "event_at", "date", "timestamp"]
    date_col = next((c for c in date_candidates if c in cols), None)

    ident = f"{schema}.{name}"
    if day is not None and date_col is not None:
        sql = text(f"""
          select *
          from {ident}
          where date({date_col}) = :d
          order by {date_col} desc nulls last
          limit 2000
        """)
        params = {"d": pd.Timestamp(day).date()}
    else:
        sql = text(f"""
          select *
          from {ident}
          order by 1
          limit 2000
        """)
        params = {}

    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    # Normalize common columns we’ll show / print if present
    keep_order = [
        "mount_code", "clutch_code", "mounting_orientation",
        "n_top", "n_bottom", "notes",
        "mounted_at", "time_mounted", "operator", "instrument", "created_at",
    ]
    cols_present = [c for c in keep_order if c in df.columns]
    # if both mounted_at and time_mounted exist, prefer mounted_at
    if "mounted_at" in cols_present and "time_mounted" in cols_present:
        cols_present.remove("time_mounted")
    if cols_present:
        df = df[cols_present + [c for c in df.columns if c not in cols_present]]
    return df

# ── PDF builder (ReportLab if available, minimal fallback otherwise) ─────────
def _build_overview_pdf(rows: List[dict]) -> bytes:
    W, H = 72*8.5, 72*11.0
    left, top, right, bottom = 54, 54, 54, 54  # 3/4" margins
    line_leading = 14.0
    title_fs = 14.0
    body_fs = 10.5

    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfbase.pdfmetrics import stringWidth
    except Exception:
        # minimal fallback single-page text
        def esc(s: str) -> str:
            return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        y0 = int(H - top)
        content = [f"BT /F1 12 Tf {int(left)} {int(y0)} Td"]
        def addln(s: str):
            content.append("T*"); content.append(f"( {esc(s[:120])} ) Tj")
        content.append(f"( Mounts — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ) Tj")
        for r in rows:
            addln(f"{r.get('mount_code','')}  {r.get('clutch_code','')}")
            addln(f"{r.get('mounting_orientation','')}  top:{r.get('n_top','')}  bot:{r.get('n_bottom','')}")
            addln(f"{r.get('mounted_at') or r.get('time_mounted') or ''}  {r.get('operator','')}")
            note = (r.get('notes') or '').strip()
            if note: addln(f"notes: {note}")
            addln(" ")
        stream = "\n".join(content + ["ET"]).encode("latin-1","replace")
        objs = []
        objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {int(W)} {int(H)}] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>".encode())
        objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        out, offsets = bytearray(), []
        out.extend(b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n")
        for i, body in enumerate(objs, start=1):
            offsets.append(len(out)); out.extend(f"{i} 0 obj\n".encode()); out.extend(body); out.extend(b"\nendobj\n")
        xref = len(out); out.extend(b"xref\n"); out.extend(f"0 {len(objs)+1}\n".encode()); out.extend(b"0000000000 65535 f \n")
        for off in offsets: out.extend(f"{off:010d} 00000 n \n".encode())
        out.extend(b"trailer\n"); out.extend(f"<< /Size {len(objs)+1} /Root 1 0 R >>\n".encode())
        out.extend(b"startxref\n"); out.extend(f"{xref}\n".encode()); out.extend(b"%%EOF\n")
        return bytes(out)

    # ReportLab path
    buf = bytearray()
    from io import BytesIO
    bio = BytesIO()
    c = canvas.Canvas(bio, pagesize=(W, H))
    c.setAuthor("CARP Mounts Overview")

    def draw_page(page_rows: List[dict]):
        y = H - top
        c.setFont("Helvetica-Bold", title_fs)
        c.drawString(left, y, f"Mounts — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        y -= title_fs + 6
        c.setFont("Helvetica", body_fs)
        for r in page_rows:
            mount_code = str(r.get("mount_code",""))
            clutch_code = str(r.get("clutch_code",""))
            orient = str(r.get("mounting_orientation",""))
            nt = str(r.get("n_top","")); nb = str(r.get("n_bottom",""))
            when = r.get("mounted_at") or r.get("time_mounted") or r.get("created_at") or ""
            oper = str(r.get("operator","")); instr = str(r.get("instrument",""))
            notes = (r.get("notes") or "").strip()

            lines = [
                f"{mount_code}    {clutch_code}",
                f"{orient}    top:{nt}  bot:{nb}",
                f"{when}    {oper} {('• '+instr) if instr else ''}".rstrip(),
            ]
            if notes: lines.append(f"notes: {notes}")

            for ln in lines:
                if y < bottom + body_fs*2:
                    c.showPage(); draw_page([]); return
                c.drawString(left, y, ln); y -= line_leading
            y -= 4  # gap between records

    # paginate ~50–60 lines per page depending on notes
    page, chunk = [], 0
    for r in rows:
        page.append(r)
        chunk += 1
        # simple heuristic: 8 lines per record worst case
        if chunk >= 25:
            draw_page(page); c.showPage(); page, chunk = [], 0
    draw_page(page)
    c.showPage(); c.save()
    return bio.getvalue()

# ── filters ──────────────────────────────────────────────────────────────────
today = utc_today()
with st.form("filters"):
    c1, c2 = st.columns([1, 1])
    with c1:
        day = st.date_input("Day", value=today)
    with c2:
        source_pref = st.selectbox(
            "Data source preference",
            ["auto (try view, then table)", "view: public.v_overview_mounts", "table: public.mounts"],
            index=0
        )
    submitted = st.form_submit_button("Apply", width="stretch")

# ── source resolution ────────────────────────────────────────────────────────
resolved: Optional[tuple[str, str, str]] = None  # (kind, schema, name)

if source_pref.startswith("view"):
    if _view_exists("public", "v_overview_mounts"):
        resolved = ("view", "public", "v_overview_mounts")
    else:
        st.warning("Requested view `public.v_overview_mounts` not found; falling back to auto.")

if resolved is None and source_pref.startswith("table"):
    if _table_exists("public", "mounts"):
        resolved = ("table", "public", "mounts")
    else:
        st.warning("Requested table `public.mounts` not found; falling back to auto.")

if resolved is None:
    if _view_exists("public", "v_overview_mounts"):
        resolved = ("view", "public", "v_overview_mounts")
    elif _table_exists("public", "mounts"):
        resolved = ("table", "public", "mounts")

if resolved is None:
    st.error("No mounts source found. Expected one of: `public.v_overview_mounts` (view) or `public.mounts` (table).")
    st.stop()

kind, s, n = resolved
st.caption(f"Source: **{kind}** `{s}.{n}`")

# ── data fetch & grid ────────────────────────────────────────────────────────
try:
    df = _fetch_mounts(s, n, day)
except Exception as e:
    st.error(f"Query failed: {type(e).__name__}: {e}")
    st.stop()

if df.empty:
    st.info("No rows for the selected day (or source). Try another day or remove the day filter.")
    st.stop()

# Ensure printable columns exist (fill missing)
for c in ["mount_code","clutch_code","mounting_orientation","n_top","n_bottom","notes","mounted_at","time_mounted","operator","instrument","created_at"]:
    if c not in df.columns:
        df[c] = pd.NA

# Build grid with selection
show_cols = [c for c in [
    "mount_code","clutch_code","mounting_orientation",
    "n_top","n_bottom","notes",
    "mounted_at" if "mounted_at" in df.columns else "time_mounted",
    "operator","instrument",
    "clutch_birthday","genotype_treatment_rollup_effective","treatment_count","treatments_codes",
] if c in df.columns]

tbl = df[show_cols].copy()
tbl.insert(0, "✓ Select", False)
picker = st.data_editor(
    tbl,
    hide_index=True,
    width="stretch",
    num_rows="fixed",
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
    },
    key="overview_mounts_picker_v1",
)

sel_mask = picker.get("✓ Select", pd.Series(False, index=picker.index)).fillna(False)
picked = tbl[sel_mask].reset_index(drop=True)

# ── download PDF of selected mounts ──────────────────────────────────────────
if picked.empty:
    st.caption(f"{len(df)} total row(s) • select rows to enable PDF download")
else:
    rows = picked.to_dict("records")
    pdf_bytes = _build_overview_pdf(rows)
    fname = f"mounts_{pd.Timestamp.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    st.download_button(
        "⬇︎ Download selected as PDF",
        data=pdf_bytes,
        file_name=fname,
        mime="application/pdf",
        type="primary",
        width="stretch",
    )

st.caption(f"{len(df)} row(s) in result")