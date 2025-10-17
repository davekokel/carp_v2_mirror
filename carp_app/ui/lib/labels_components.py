# carp_app/ui/lib/labels_components.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List, Dict, Any, Optional
from datetime import date, datetime as _dt
import io

__all__ = [
    "build_crossing_tank_labels_pdf",
    "build_petri_labels_pdf",
    "build_tank_labels_pdf",
    "download_button_for_labels",
]

# --------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------

def _safe(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (date, _dt)):
        return v.strftime("%Y-%m-%d")
    return str(v).strip()

def _rl_or_none():
    """
    Try to import ReportLab; return (canvas, stringWidth, inch, mm, TTFont, pdfmetrics)
    or (None, None, None, None, None, None) if not available.
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase.pdfmetrics import stringWidth
        from reportlab.lib.units import inch, mm
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfbase import pdfmetrics
        return canvas, stringWidth, inch, mm, TTFont, pdfmetrics
    except Exception:
        return None, None, None, None, None, None

def _minimal_single_page_pdf(lines: List[str], width_pt: float, height_pt: float) -> bytes:
    """
    Extremely small fallback PDF (no ReportLab). One label per page.
    """
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    y0 = int(height_pt - 18)
    content = [f"BT /F1 12 Tf 10 {y0} Td"]
    for i, ln in enumerate(lines):
        if i > 0:
            content.append("T*")
        content.append(f"( {esc(ln[:120])} ) Tj")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", "replace")

    objs: List[bytes] = []
    # 1: Catalog, 2: Pages, 3: Page, 4: Font, 5: Contents
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append(
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {int(width_pt)} {int(height_pt)}] "
        f"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>".encode()
    )
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")

    out = bytearray()
    out.extend(b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n")
    offsets: List[int] = []

    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode())
        out.extend(body)
        out.extend(b"\nendobj\n")

    xref = len(out)
    out.extend(b"xref\n")
    out.extend(f"0 {len(objs)+1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(b"trailer\n")
    out.extend(f"<< /Size {len(objs)+1} /Root 1 0 R >>\n".encode())
    out.extend(b"startxref\n")
    out.extend(f"{xref}\n".encode())
    out.extend(b"%%EOF\n")
    return bytes(out)

def _labels_pdf_pages(
    pages: List[List[str]],
    width_in: float,
    height_in: float,
    header_pt: float,
    body_pt: float,
    leading_pt: float,
    margin_pt: float = 6.0,
    line_limit: int | None = None,
) -> bytes:
    """
    Generic 1-up label renderer (no QR). Matches your crossing/petri pages:
    - crossing : 2.4x1.0, header/body/leading = 9.2/7.0/7.2
    - petri    : 2.4x0.75, header/body/leading = 10.5/7.0/7.1
    """
    canvas, stringWidth, inch, mm, TTFont, pdfmetrics = _rl_or_none()
    if canvas is None:
        # crude fallback: one PDF page per label
        buf = io.BytesIO()
        for lines in pages:
            buf.write(_minimal_single_page_pdf(lines, width_in*72.0, height_in*72.0))
        return buf.getvalue()

    W = width_in * 72.0
    H = height_in * 72.0
    maxw = W - 2 * margin_pt
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))

    def elide(text: str, maxw: float, font: str, size: float) -> str:
        if not text:
            return ""
        if stringWidth(text, font, size) <= maxw:
            return text
        ell = "…"
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi)//2
            trial = text[:mid] + ell
            if stringWidth(trial, font, size) <= maxw:
                lo = mid + 1
            else:
                hi = mid
        cut = max(0, lo-1)
        return text[:cut] + ell if cut > 0 else ell

    for lines in pages:
        x = margin_pt
        y = H - margin_pt
        if lines:
            c.setFont("Helvetica-Bold", header_pt)
            hdr = elide(lines[0], maxw, "Helvetica-Bold", header_pt)
            y -= header_pt * 0.85
            c.drawString(x, y, hdr)
        c.setFont("Helvetica", body_pt)
        rendered = 0
        for ln in lines[1:]:
            if line_limit is not None and rendered >= line_limit:
                break
            y -= leading_pt
            if y < margin_pt + body_pt:
                break
            ln_fit = elide(str(ln or ""), maxw, "Helvetica", body_pt)
            c.drawString(x, y, ln_fit)
            rendered += 1
        c.showPage()
    c.save()
    return buf.getvalue()

# --------------------------------------------------------------------
#  A) Crossing tank labels (2.4" x 1.0") — exact match
# --------------------------------------------------------------------

def build_crossing_tank_labels_pdf(rows: Iterable[Dict[str, Any]]) -> bytes:
    """
    2.4\" × 1.0\"; header/body/leading = 9.2 / 7.0 / 7.2
    Lines:
      CROSS {cross_code}
      {weekday YYYY-MM-DD}
      M: {mother_tank}
      D: {father_tank}
      ↓
      {clutch_instance_code}
      {clutch_name}
    """
    pages: List[List[str]] = []
    for r in rows:
        cross_code = _safe(r.get("cross_code"))
        cross_date = r.get("cross_date")
        wk = cross_date.strftime("%a %Y-%m-%d") if isinstance(cross_date, (date, _dt)) else _safe(cross_date)
        mom_tank = _safe(r.get("mother_tank_label") or r.get("mother_tank_code"))
        dad_tank = _safe(r.get("father_tank_label") or r.get("father_tank_code"))
        clutch_inst = _safe(r.get("clutch_instance_code"))
        clutch_name = _safe(r.get("clutch_name"))
        pages.append([
            f"CROSS {cross_code}",
            wk,
            f"M: {mom_tank}",
            f"D: {dad_tank}",
            "↓",
            clutch_inst,
            clutch_name,
        ])
    return _labels_pdf_pages(
        pages=pages, width_in=2.4, height_in=1.0,
        header_pt=9.2, body_pt=7.0, leading_pt=7.2
    )

# --------------------------------------------------------------------
#  B) Petri dish labels (2.4" x 0.75") — exact match
# --------------------------------------------------------------------

def build_petri_labels_pdf(rows: Iterable[Dict[str, Any]]) -> bytes:
    """
    2.4\" × 0.75\"; header/body/leading = 10.5 / 7.0 / 7.1
    Lines:
      {clutch_instance_code}
      {clutch_name}
      {mom_code} × {dad_code}
      {DOB or 'DOB TBD'}
    """
    pages: List[List[str]] = []
    for r in rows:
        clutch_inst = _safe(r.get("clutch_instance_code"))
        clutch_name = _safe(r.get("clutch_name"))
        mom_code = _safe(r.get("mom_code"))
        dad_code = _safe(r.get("dad_code"))
        dob = r.get("date_birth")
        dob_text = dob.strftime("%Y-%m-%d") if isinstance(dob, (date, _dt)) else (_safe(dob) or "DOB TBD")
        pages.append([
            clutch_inst,
            clutch_name,
            f"{mom_code} × {dad_code}",
            dob_text,
        ])
    return _labels_pdf_pages(
        pages=pages, width_in=2.4, height_in=0.75,
        header_pt=10.5, body_pt=7.0, leading_pt=7.1
    )

# --------------------------------------------------------------------
#  C) Tank labels with QR (2.4" x 1.5") — exact match
# --------------------------------------------------------------------

def build_tank_labels_pdf(rows: Iterable[Dict[str, Any]]) -> bytes:
    """
    2.4\" × 1.5\"; paddings L/R/T/B = 10/10/8/8 pt; QR = 40 pt; gap = 6 pt.
    Lines (top→bottom):
      nickname (Helvetica-Oblique, 9.0)
      name     (Helvetica-Bold,    10.5)
      tank_code|label|fish_code    (Helvetica-Bold, 11.0)
      genotype (mono 9.2; fall back to Helvetica if mono font not found)
      genetic_background (Helvetica 8.2)
      stage    (Helvetica 8.2)
      dob      (Helvetica 8.2)

    CHANGE: top 4 lines render against FULL width (not QR-reserved), so they print to the right edge.
    Lower lines use QR-reserved width to avoid collision with the QR in the lower-right quadrant.
    """
    canvas, stringWidth, inch, mm, TTFont, pdfmetrics = _rl_or_none()
    W = 2.4 * 72.0
    H = 1.5 * 72.0
    PAD_L, PAD_R, PAD_T, PAD_B = 10.0, 10.0, 8.0, 8.0
    QR_SIZE, QR_GAP = 40.0, 6.0
    TOP_PAD_FRAC = 0.82
    MIN_FS = 7.0

    if canvas is None:
        # fallback: render as generic pages
        pages: List[List[str]] = []
        for r in rows:
            pages.append([
                _safe(r.get("nickname")),
                _safe(r.get("name")),
                _safe(r.get("tank_code") or r.get("label") or r.get("fish_code")),
                _safe(r.get("genotype")),
                _safe(r.get("genetic_background")),
                _safe(r.get("stage")),
                _safe(r.get("dob")),
            ])
        return _labels_pdf_pages(pages, 2.4, 1.5, header_pt=11.0, body_pt=8.2, leading_pt=9.0)

    # Try to register mono font for genotype
    mono_font_name = "Helvetica"
    try:
        pdfmetrics.registerFont(TTFont("LabelMono", "/Library/Fonts/SourceCodePro-Regular.ttf"))
        mono_font_name = "LabelMono"
    except Exception:
        pass

    from reportlab.pdfbase.pdfmetrics import stringWidth as _sw
    from reportlab.graphics.barcode import qr
    from reportlab.graphics import renderPDF
    from reportlab.graphics.shapes import Drawing

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))

    # Two measuring widths:
    text_w_full = W - PAD_L - PAD_R                            # for top 4 lines
    text_w_qr   = W - PAD_L - PAD_R - QR_SIZE - QR_GAP         # for lower lines

    def _ellipsize(txt: str, font_name: str, font_size: float, max_w: float) -> str:
        if not txt:
            return ""
        if _sw(txt, font_name, font_size) <= max_w:
            return txt
        ell = "…"
        lo, hi = 0, len(txt)
        while lo < hi:
            mid = (lo + hi)//2
            if _sw(txt[:mid] + ell, font_name, font_size) <= max_w:
                lo = mid + 1
            else:
                hi = mid
        cut = max(0, lo - 1)
        return txt[:cut] + ell if cut > 0 else ell

    def _draw_qr(payload: str, x: float, y: float, size: float) -> None:
        try:
            code = qr.QrCodeWidget(payload or "")
            bx0, by0, bx1, by1 = code.getBounds()
            bw = max(1.0, bx1 - bx0); bh = max(1.0, by1 - by0)
            sx = size / bw; sy = size / bh
            d = Drawing(size, size, transform=[sx, 0, 0, sy, 0, 0])
            d.add(code)
            renderPDF.draw(d, c, x, y)
        except Exception:
            pass

    for r in rows:
        x0, y0 = PAD_L, PAD_B
        w  = W - PAD_L - PAD_R
        h  = H - PAD_B - PAD_T

        # QR anchored bottom-right
        qr_x, qr_y = x0 + w - QR_SIZE, y0

        nickname = _safe(r.get("nickname"))
        name     = _safe(r.get("name"))
        tankline = _safe(r.get("tank_code") or r.get("label") or r.get("fish_code"))
        genotype = _safe(r.get("genotype"))
        backgrnd = _safe(r.get("genetic_background"))
        stage    = _safe(r.get("stage"))
        dob      = _safe(r.get("dob"))

        lines = [
            ("Helvetica-Oblique",  9.0, nickname, text_w_full),   # 0
            ("Helvetica-Bold",    10.5, name,     text_w_full),   # 1
            ("Helvetica-Bold",    11.0, tankline, text_w_full),   # 2
            (mono_font_name,       9.2, genotype, text_w_full),   # 3  ← now full width
            ("Helvetica",          8.2, backgrnd, text_w_qr),     # 4
            ("Helvetica",          8.2, stage,    text_w_qr),     # 5
            ("Helvetica",          8.2, dob,      text_w_qr),     # 6
        ]

        lane_h = h / len(lines)
        y_top = y0 + h

        for idx, (fn, fs, txt, max_w) in enumerate(lines):
            fs_lane = min(fs, max(MIN_FS, lane_h - 1.0))
            fs_use = fs_lane

            # shrink bold title lines to fit width
            if fn.endswith("Bold") and txt:
                while fs_use > MIN_FS and _sw(txt, fn, fs_use) > max_w:
                    fs_use -= 0.3

            y = y_top - (idx * lane_h) - (fs_use * TOP_PAD_FRAC)
            c.setFont(fn, fs_use)
            c.drawString(x0, y, _ellipsize(txt, fn, fs_use, max_w))

        payload = _safe(r.get("tank_code") or r.get("fish_code") or r.get("label"))
        if payload:
            _draw_qr(payload, qr_x, qr_y, QR_SIZE)

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()

# --------------------------------------------------------------------
#  Optional Streamlit helper
# --------------------------------------------------------------------

def download_button_for_labels(
    rows: Iterable[Dict[str, Any]],
    builder: str,
    file_prefix: str,
    button_text: str,
) -> None:
    """
    Streamlit helper to show a single download button for a set of rows.
      builder: 'crossing' | 'petri' | 'tank'
    """
    try:
        import streamlit as st
    except Exception:
        return
    rows = list(rows)
    if not rows:
        st.caption("Select rows above to enable label printing.")
        return
    if builder == "crossing":
        pdf = build_crossing_tank_labels_pdf(rows)
    elif builder == "petri":
        pdf = build_petri_labels_pdf(rows)
    elif builder == "tank":
        pdf = build_tank_labels_pdf(rows)
    else:
        st.error(f"Unknown builder '{builder}'"); return
    fname = f"{file_prefix}_{_dt.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    st.download_button(button_text, data=pdf, file_name=fname, mime="application/pdf", use_container_width=True)