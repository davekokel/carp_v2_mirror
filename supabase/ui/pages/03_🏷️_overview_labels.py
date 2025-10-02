from __future__ import annotations

# 03_🏷️_overview_labels.py

import os
from io import BytesIO
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# 🔒 auth (mirror/local)
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

PAGE_TITLE = "CARP — Overview → PDF Labels"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🏷️", layout="wide")
st.title("🏷️ Overview → PDF Labels")
st.caption("Search, select rows, auto-assign tanks if needed, and generate **PDF labels** (2.4″×1.5″, QR included).")

# ------------------------- small helpers -------------------------
def _ellipsize(c, text: str, font_name: str, font_size: float, max_width: float, ellipsis: str = "…") -> str:
    """Trim string to fit max_width using drawString metrics; returns possibly-ellipsized text."""
    text = (text or "").strip()
    if not text:
        return ""
    w = c.stringWidth(text, font_name, font_size)
    if w <= max_width:
        return text
    e_w = c.stringWidth(ellipsis, font_name, font_size)
    avail = max(max_width - e_w, 0)
    if avail <= 0:
        return ellipsis
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi) // 2
        if c.stringWidth(text[:mid], font_name, font_size) <= avail:
            lo = mid + 1
        else:
            hi = mid
    trimmed = text[: max(lo - 1, 0)]
    return (trimmed + ellipsis) if trimmed else ellipsis

def _s(v) -> str:
    """Safe stringify: dates → ISO, None → '', everything else → str()"""
    if v is None:
        return ""
    try:
        import datetime as _dt
        if isinstance(v, (_dt.date, _dt.datetime)):
            return v.isoformat()
    except Exception:
        pass
    return str(v)

def _ensure_sslmode(url: str) -> str:
    u = urlparse(url)
    host = (u.hostname or "").lower() if u.hostname else ""
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    if host in {"localhost", "127.0.0.1", "::1"}:
        q["sslmode"] = "disable"
    else:
        q.setdefault("sslmode", "require")
    return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q), u.fragment))

def build_db_url() -> str:
    raw = (st.secrets.get("DB_URL") or os.getenv("DATABASE_URL") or "").strip()
    if raw:
        return _ensure_sslmode(raw if "://" in raw else raw)
    required = ["PGHOST","PGPORT","PGDATABASE","PGUSER","PGPASSWORD"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError("Missing DB env vars: " + ", ".join(missing))
    return _ensure_sslmode(
        f"postgresql://{os.getenv('PGUSER')}:{os.getenv('PGPASSWORD')}"
        f"@{os.getenv('PGHOST')}:{os.getenv('PGPORT')}/{os.getenv('PGDATABASE')}"
    )

@st.cache_resource(show_spinner=False)
def _engine():
    return create_engine(build_db_url(), pool_pre_ping=True, future=True, connect_args={"prepare_threshold": None})

def _detect_tank_fk(engine) -> Tuple[str, str]:
    """
    Returns (fk_col_on_fish, cast_str) where cast_str is like '::uuid' or '::bigint' or ''.
    """
    with engine.connect() as cx:
        row = cx.execute(text("""
            SELECT att2.attname AS ref_col,
                   format_type(att2.atttypid, att2.atttypmod) AS ref_type
            FROM pg_constraint c
            JOIN pg_class      cl   ON cl.oid  = c.conrelid  AND cl.relname = 'tank_assignments'
            JOIN pg_attribute  att  ON att.attrelid = c.conrelid AND att.attnum = ANY (c.conkey)
            JOIN pg_class      rf   ON rf.oid  = c.confrelid AND rf.relname = 'fish'
            JOIN pg_attribute  att2 ON att2.attrelid = c.confrelid AND att2.attnum = ANY (c.confkey)
            WHERE c.contype = 'f'
              AND att.attname = 'fish_id'
            LIMIT 1
        """)).mappings().first()
    if not row:
        with engine.connect() as cx:
            row = cx.execute(text("""
                SELECT kcu.column_name AS ref_col,
                       (SELECT data_type FROM information_schema.columns
                         WHERE table_schema='public' AND table_name='fish' AND column_name=kcu.column_name) AS ref_type
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tc.constraint_name
                 AND kcu.table_schema    = tc.table_schema
                 AND kcu.table_name      = tc.table_name
                WHERE tc.table_schema='public' AND tc.table_name='fish' AND tc.constraint_type='PRIMARY KEY'
                LIMIT 1
            """)).mappings().first()
    ref_col  = (row or {}).get("ref_col", "id")
    ref_type = ((row or {}).get("ref_type") or "").lower()
    if "uuid" in ref_type:
        cast_str = "::uuid"
    elif "bigint" in ref_type or "int" in ref_type:
        cast_str = "::bigint" if "bigint" in ref_type else "::int"
    else:
        cast_str = ""
    return ref_col, cast_str

# ------------------------- data loader -------------------------
def load_overview_page(
    engine, page: int, page_size: int, q: str | None = None, stage: str | None = None, strain_sub: str | None = None
) -> tuple[int, pd.DataFrame]:
    offset = (page - 1) * page_size
    where, params = [], {}
    if q:
        params["q"] = f"%{q}%"
        where.append(
            "("
            " fish_name ILIKE :q OR nickname ILIKE :q OR strain ILIKE :q "
            " OR transgene_base_code_filled ILIKE :q "
            " OR allele_code_filled ILIKE :q OR allele_name_filled ILIKE :q "
            " OR fish_code ILIKE :q "
            ")"
        )
    if stage and stage != "(any)":
        params["stage"] = stage
        where.append("line_building_stage = :stage")
    if strain_sub:
        params["strain_like"] = f"%{strain_sub}%"
        where.append("strain ILIKE :strain_like")
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sql_count = text(f"SELECT COUNT(*) FROM public.vw_fish_overview_with_label{where_sql}")
    sql_page = text(f"""
        SELECT *
        FROM public.vw_fish_overview_with_label
        {where_sql}
        ORDER BY fish_code NULLS LAST
        LIMIT :limit OFFSET :offset
    """)
    params_page = dict(params, limit=page_size, offset=offset)
    with engine.connect() as cx:
        total = cx.execute(sql_count, params).scalar() or 0
        df = pd.read_sql(sql_page, cx, params=params_page)
    return total, df

# ------------------------- controls -------------------------
q = st.text_input("Global search", placeholder="code, name, strain, allele nickname/code/base…")
with st.expander("Filters", expanded=False):
    c1, c2, c3 = st.columns([1,1,2])
    with c1:
        stage = st.selectbox("Line building stage", ["(any)","founder","F0","F1","F2","F3","unknown"], index=0)
    with c2:
        strain = st.text_input("Strain contains")
    with c3:
        batch_filter = st.text_input("Batch label contains")

assign_mode = st.radio(
    "Tank assignment mode",
    ["Assign if missing (default)", "Force new tank", "Reprint existing only"],
    index=0,
    help="Choose how to handle tanks before printing labels."
)

if "labels_offset" not in st.session_state:
    st.session_state.labels_offset = 0
if "labels_page_size" not in st.session_state:
    st.session_state.labels_page_size = 100

if st.button("🔄 Reset results"):
    st.session_state.labels_offset = 0
page = (st.session_state.labels_offset // st.session_state.labels_page_size) + 1

# ------------------------- load -------------------------
try:
    total, rows = load_overview_page(
        _engine(), page=page, page_size=st.session_state.labels_page_size, q=q, stage=stage, strain_sub=strain
    )
except Exception as e:
    st.error(f"Query failed: {e}")
    st.stop()

if batch_filter and "batch_label" in rows.columns:
    rows = rows[rows["batch_label"].astype(str).str.contains(batch_filter, case=False, na=False)]

st.caption(f"Showing {min(st.session_state.labels_offset + st.session_state.labels_page_size, total):,} of {total:,} rows")

# ------------------------- selection table -------------------------
display_cols = [
    "batch_label",
    "fish_code", "fish_name", "nickname", "strain",
    "line_building_stage", "created_by", "date_of_birth",
    "transgene_base_code_filled",
    "allele_number_filled", "allele_code_filled", "allele_name_filled",
    "transgene_pretty_filled", "transgene_pretty_nickname",
]
available_cols = [c for c in display_cols if c in rows.columns]
df_show = rows[available_cols].copy()
df_show.insert(0, "_select", False)

edited = st.data_editor(
    df_show,
    use_container_width=True,
    num_rows="fixed",
    hide_index=True,
    column_config={
        "_select": st.column_config.CheckboxColumn("Select"),
        "transgene_pretty_filled": st.column_config.TextColumn("Pretty (code)"),
        "transgene_pretty_nickname": st.column_config.TextColumn("Pretty (nickname)"),
    }
)

selected = edited[edited["_select"] == True].copy() if "_select" in edited.columns else pd.DataFrame()
st.caption(f"Selected: {len(selected)}")

# ------------------------- tank assignment SQL templates -------------------------
ASSIGN_IF_MISSING_TMPL = """
WITH ids AS (SELECT UNNEST(:ids){cast} AS fish_id)
INSERT INTO public.tank_assignments(fish_id, tank_label, status)
SELECT i.fish_id, public.next_tank_code('TANK-'), 'inactive'::tank_status
FROM ids i
LEFT JOIN public.tank_assignments t ON t.fish_id = i.fish_id
WHERE t.fish_id IS NULL;
"""

ASSIGN_FORCE_NEW_TMPL = """
WITH ids AS (SELECT UNNEST(:ids){cast} AS fish_id)
UPDATE public.tank_assignments ta
SET tank_label = public.next_tank_code('TANK-'), updated_at = now()
WHERE ta.fish_id IN (SELECT fish_id FROM ids);

INSERT INTO public.tank_assignments(fish_id, tank_label, status)
SELECT i.fish_id, public.next_tank_code('TANK-'), 'inactive'::tank_status
FROM ids i
LEFT JOIN public.tank_assignments t ON t.fish_id = i.fish_id
WHERE t.fish_id IS NULL;
"""

# Fetch printable by fish_code (avoids type issues)
FETCH_PRINTABLE_BY_CODE = text("""
SELECT
  f.id_uuid AS fish_id,
  f.fish_code,
  v.fish_name         AS fish_name,
  v.nickname          AS nickname,
  v.transgene_base_code_filled   AS base,
  v.allele_number_filled         AS allele_num,
  v.allele_code_filled           AS allele_code,
  v.allele_name_filled           AS allele_name,
  v.transgene_pretty_filled      AS pretty_code,
  v.transgene_pretty_nickname    AS pretty_nick,
  f.strain,
  f.line_building_stage,
  f.date_of_birth,
  COALESCE(v.batch_label, '(no batch)') AS batch_label,
  ta.tank_label AS tank
FROM public.fish f
JOIN public.vw_fish_overview_with_label v
  ON UPPER(TRIM(v.fish_code)) = UPPER(TRIM(f.fish_code))
LEFT JOIN public.tank_assignments ta
  ON ta.fish_id = f.id_uuid OR ta.fish_id = f.id
WHERE UPPER(TRIM(f.fish_code)) = ANY(:codes);
""")

# ------------------------- pdf generator -------------------------
def render_labels_pdf(df: pd.DataFrame) -> bytes:
    """
    One label per page, 2.4" x 1.5", margins 6pt, QR ~0.70", lifted close to top.
    Lines: [TANK left + Fish right], Fish name, Nickname, Pretty (nick), Pretty (code), Small details (Strain · Stage · DOB), QR bottom-right.
    Always returns bytes; on error, returns a diagnostic PDF page.
    """
    try:
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.graphics.barcode import qr
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF
    except Exception as e:
        # best-effort empty PDF with error note
        buf = BytesIO()
        from reportlab.pdfgen import canvas as _c
        c = _c.Canvas(buf, pagesize=(172, 108))  # fallback tiny page
        c.setFont("Helvetica", 8)
        c.drawString(10, 90, f"PDF engine error: {e}")
        c.showPage(); c.save()
        return buf.getvalue()

    LABEL_W, LABEL_H = 2.4 * inch, 1.5 * inch
    MARGIN = 8        # tighter margins
    QR_SIZE = 0.70 * inch
    TOP_LIFT = 2     # raise all text upwards

    # styles (reduced fonts)
    style_big   = ParagraphStyle("big",   fontName="Helvetica-Bold", fontSize=9,   leading=10.5)
    style_body  = ParagraphStyle("body",  fontName="Helvetica",      fontSize=7.5, leading=9)
    style_small = ParagraphStyle("small", fontName="Helvetica",      fontSize=6,   leading=7.5, textColor=colors.grey)
    
    # avoid breaking long tokens across lines
    style_big.splitLongWords = 0
    style_body.splitLongWords = 0
    style_small.splitLongWords = 0

    def draw_par(c, txt: str, style: ParagraphStyle, x: float, y: float, max_w: float, max_h: float = 1000, vgap: float = 2) -> float:
        """Wrap and draw a Paragraph; returns new y (moved up by drawn height+vgap)."""
        txt = (txt or "").strip()
        if not txt:
            return y
        p = Paragraph(txt, style)
        w, h = p.wrap(max_w, max_h)
        if h <= 0:
            return y
        p.drawOn(c, x, y - h)
        return y - h - vgap

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(LABEL_W, LABEL_H))

    def draw_label(rec: dict):
        x0, y0 = MARGIN, MARGIN
        w, h = LABEL_W - 2 * MARGIN, LABEL_H - 2 * MARGIN
        text_w = w - QR_SIZE - 2
        x_text = x0
        y      = y0 + h + TOP_LIFT

        # normalize
        tank        = _s(rec.get("tank")).strip()
        fish_code   = _s(rec.get("fish_code")).strip()
        fish_name   = _s(rec.get("fish_name")).strip()
        nickname    = _s(rec.get("nickname")).strip()
        pretty_nick = _s(rec.get("pretty_nick")).strip()
        pretty_code = _s(rec.get("pretty_code")).strip()
        strain      = _s(rec.get("strain")).strip()
        stage       = _s(rec.get("line_building_stage")).strip()
        dob         = _s(rec.get("date_of_birth")).strip()

        if nickname and nickname.lower() == fish_name.lower():
            nickname = ""

        # top row: tank (left) + fish_code (right), no overlap
        tank_font_name, tank_font_size = "Helvetica-Bold", 9
        fish_font_name, fish_font_size = "Helvetica", 7.5
        baseline_y = y - 9
        GAP = 6

        fish_w = c.stringWidth(fish_code, fish_font_name, fish_font_size)
        max_tank_w = max(text_w - fish_w - GAP, 0)
        tank_text  = _ellipsize(c, tank, tank_font_name, tank_font_size, max_tank_w)

        c.setFont(tank_font_name, tank_font_size)
        c.drawString(x_text, baseline_y, tank_text)
        c.setFont(fish_font_name, fish_font_size)
        c.drawString(x_text + text_w - fish_w, baseline_y, fish_code)
        y -= 12

        # name above nickname
        if fish_name:
            y = draw_par(c, fish_name,  style_body, x_text, y, text_w, vgap=1)
        if nickname:
            y = draw_par(c, nickname,   style_body, x_text, y, text_w, vgap=2)

        # both pretties
        # ---- Combined pretties on a single line ----
        y = draw_par(c, pretty_nick, style_body, x_text, y, text_w, vgap=2)

        # small details (no batch)
        small = f"Strain: {strain} · Stage: {stage} · DOB: {dob}"
        y = draw_par(c, small, style_small, x_text, y, text_w, vgap=0)

        # ---- Code128 bottom-right (instead of QR) ----
        from reportlab.graphics.barcode import code128

        bar_data = tank or fish_code or "TANK-UNKNOWN"

        # Target the same footprint as QR_SIZE wide-ish and label height ~ QR_SIZE
        # Tune barWidth to fit your strings; 0.5–0.7 pt works well on 2.4″ labels.
        bar = code128.Code128(bar_data, barHeight=QR_SIZE * 0.4, barWidth=1.0)

        # Right-align in the reserved area
        bar_w = bar.width
        draw_x = x0 + w - bar_w  # flush to the right edge of the text area
        draw_y = y0               # bottom of label content box
        bar.drawOn(c, draw_x, draw_y)

    # empty/diagnostic-safe rendering
    if df is None or df.empty:
        c.showPage(); c.save()
        return buf.getvalue()

    try:
        for rec in df.to_dict(orient="records"):
            draw_label(rec)
            c.showPage()
    except Exception as e:
        # draw a diagnostic page if something fails
        from traceback import format_exc
        c.setFont("Helvetica", 8)
        c.drawString(10, LABEL_H - 12, "Label rendering error:")
        for i, line in enumerate(format_exc().splitlines()[:20], start=1):
            c.drawString(10, LABEL_H - 12 - i*10, line[:90])
        c.showPage()
    finally:
        c.save()
        return buf.getvalue()

# ------------------------- actions -------------------------
st.divider()
st.subheader("Generate PDF")

col_a, col_b = st.columns([1,1])
with col_a:
    gen = st.button("🖨️ Generate PDF labels", type="primary", disabled=selected.empty)
with col_b:
    clear = st.button("Clear selection", disabled=selected.empty)

if clear and not selected.empty:
    st.experimental_rerun()

if gen:
    # selected fish codes
    codes = [str(x).strip().upper() for x in selected.get("fish_code", pd.Series([])).tolist() if str(x).strip()]
    if not codes:
        st.warning("No fish selected."); st.stop()

    # FK target for tank_assignments
    fk_col, cast_str = _detect_tank_fk(_engine())

    # Resolve fish IDs of the correct column/type
    with _engine().connect() as cx:
        ids = cx.execute(
            text(f"SELECT {fk_col}::text FROM public.fish WHERE UPPER(TRIM(fish_code)) = ANY(:codes)"),
            {"codes": codes}
        ).scalars().all()
    if not ids:
        st.warning("Selected rows did not resolve to fish ids."); st.stop()

    # Build assignment SQL with the correct cast
    ASSIGN_SQL_IF_MISSING = text(ASSIGN_IF_MISSING_TMPL.format(cast=cast_str))
    ASSIGN_SQL_FORCE_NEW  = text(ASSIGN_FORCE_NEW_TMPL.format(cast=cast_str))

    # Assign tanks
    try:
        with _engine().begin() as cx:
            if assign_mode.startswith("Assign if missing"):
                cx.execute(ASSIGN_SQL_IF_MISSING, {"ids": ids})
            elif assign_mode.startswith("Force new tank"):
                cx.execute(ASSIGN_SQL_FORCE_NEW, {"ids": ids})
            else:
                # reprint-only → ensure tanks exist
                missing = cx.execute(text(f"""
                    WITH ids AS (SELECT UNNEST(:ids){cast_str} AS fish_id)
                    SELECT COUNT(*)
                    FROM ids i
                    LEFT JOIN public.tank_assignments t ON t.fish_id = i.fish_id
                    WHERE t.fish_id IS NULL
                """), {"ids": ids}).scalar() or 0
                if missing > 0:
                    st.error(f"{missing} selected fish do not have tanks yet — switch mode to 'Assign if missing' or 'Force new tank'.")
                    st.stop()
    except Exception as e:
        st.error(f"Tank assignment failed: {e}")
        st.stop()

    # Fetch printable rows by fish_code
    with _engine().connect() as cx:
        printable = pd.read_sql(FETCH_PRINTABLE_BY_CODE, cx, params={"codes": codes})

    if printable.empty or printable["tank"].fillna("").eq("").any():
        st.error("Some selected fish still have no tank; cannot print. Please try again.")
        st.stop()

    # Render PDF
    pdf_bytes = render_labels_pdf(printable)
    if not isinstance(pdf_bytes, (bytes, bytearray)) or len(pdf_bytes) == 0:
        st.error("PDF generation returned no data.")
    else:
        st.success(f"Generated {len(printable)} labels.")
        st.download_button(
            "⬇️ Download labels.pdf",
            data=pdf_bytes,
            file_name="labels.pdf",
            mime="application/pdf"
        )

# paging
if st.session_state.labels_offset + st.session_state.labels_page_size < total:
    if st.button("⬇️ Load more"):
        st.session_state.labels_offset += st.session_state.labels_page_size
        st.experimental_rerun()