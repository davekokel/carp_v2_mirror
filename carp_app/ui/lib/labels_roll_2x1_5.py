from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, date
from typing import Iterable, Dict, Any, Optional

from reportlab.pdfgen import canvas as _canvas
from reportlab.pdfbase.pdfmetrics import stringWidth, registerFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.barcode import qr
from reportlab.graphics import renderPDF

# --------- Page geometry (2.4in × 1.5in) ---------
PT_PER_IN = 72.0
LABEL_W   = 2.4 * PT_PER_IN            # 172.8 pt
LABEL_H   = 1.5 * PT_PER_IN            # 108.0 pt

# Margins & QR block
PAD_L = 10.0
PAD_R = 10.0
PAD_T = 8.0
PAD_B = 8.0

QR_SIZE   = 40.0                       # QR block height (also width)
QR_GAP    = 6.0                        # gap between text column and QR block

# Optional mono font for genotype / fish code
MONO_FONT_NAME = None
for path in [
    os.environ.get("LABELS_MONO_TTF"),
    "/Library/Fonts/SourceCodePro-Regular.ttf",
    "/Library/Fonts/FiraCode-Regular.ttf",
    "/Library/Fonts/DejaVu Sans Mono.ttf",
    "/System/Library/Fonts/Supplemental/Andale Mono.ttf",
]:
    try:
        if path and os.path.exists(path):
            registerFont(TTFont("LabelMono", path))
            MONO_FONT_NAME = "LabelMono"
            break
    except Exception:
        pass

def _safe(s: Any) -> str:
    if s is None:
        return ""
    if isinstance(s, (datetime, date)):
        return s.strftime("%Y-%m-%d")
    t = str(s).strip()
    return t

def _ellipsize(txt: str, max_w: float, font_name: str, font_size: float) -> str:
    if not txt:
        return ""
    if stringWidth(txt, font_name, font_size) <= max_w:
        return txt
    ell = "…"
    lo, hi = 0, len(txt)
    while lo < hi:
        mid = (lo + hi) // 2
        if stringWidth(txt[:mid] + ell, font_name, font_size) <= max_w:
            lo = mid + 1
        else:
            hi = mid
    cut = max(0, lo - 1)
    return (txt[:cut] + ell) if cut > 0 else ell

# --------- Tank code helper ---------
_ALPH32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford (no I, L, O, U)
def _base32(n: int) -> str:
    if n == 0:
        return "0"
    out = []
    n = abs(n)
    while n:
        n, r = divmod(n, 32)
        out.append(_ALPH32[r])
    return "".join(reversed(out))

def tank_code_for(fish_code: str, when: Optional[datetime] = None) -> str:
    when = when or datetime.utcnow()
    yy = when.strftime("%y")
    h = 2166136261
    for ch in (fish_code or ""):
        h ^= ord(ch); h = (h * 16777619) & 0xFFFFFFFF
    return f"TANK-{yy}{_base32(h)[:4].rjust(4,'0')}"

def _draw_qr(c: _canvas.Canvas, payload: str, x: float, y: float, size: float) -> None:
    code = qr.QrCodeWidget(payload or "")
    bounds = code.getBounds()
    bw = max(1.0, bounds[2] - bounds[0])
    bh = max(1.0, bounds[3] - bounds[1])
    sx = size / bw
    sy = size / bh
    from reportlab.graphics.shapes import Drawing
    d = Drawing(size, size, transform=[sx, 0, 0, sy, 0, 0])
    d.add(code)
    renderPDF.draw(d, c, x, y)

# --------- Data model ---------
@dataclass
class LabelRow:
    fish_code: str
    name: str
    genotype: str
    nickname: str
    tg_nick: str
    stage: str
    dob: str
    tank_code: Optional[str] = None
    qr_payload: Optional[str] = None

# --------- Renderer (8 equal lanes; one field per lane) ---------
def render_label(c: _canvas.Canvas, r: LabelRow) -> None:
    # Inner box
    x0 = PAD_L
    y0 = PAD_B
    w  = LABEL_W - PAD_L - PAD_R
    h  = LABEL_H - PAD_B - PAD_T

    # QR block at bottom-right (you can shrink margins per your last tweak if desired)
    qr_x = x0 + w - QR_SIZE
    qr_y = y0
    # text column stays to the left of QR with a gap
    text_w = w - QR_SIZE - QR_GAP
    col_x  = x0

    # Build the rows in requested order:
    # Nickname, Name, Tank code, Fish code, Genotype, Genetic background, Stage, Date
    tank = r.tank_code or tank_code_for(r.fish_code)
    fish = r.fish_code

    rows = [
        # (row_key, font_name, size, text, color_gray)
        ("nick", "Helvetica-Oblique", 9.0,  _safe(r.nickname), 0.35),           # NICKNAME (priority; smart fit)
        ("name", "Helvetica-Bold",    10.5, _safe(r.name),     0.0),             # NAME
        ("tank", "Helvetica-Bold",    11.0, tank,              0.0),             # TANK
        ("fish", MONO_FONT_NAME or "Helvetica", 9.5, fish,     0.0),             # FISH (mono if available)
        ("geno", MONO_FONT_NAME or "Helvetica", 9.2, _safe(r.genotype), 0.0),    # GENOTYPE
        ("bg",   "Helvetica",         8.2,  _safe(r.tg_nick),  0.0),             # GENETIC BACKGROUND
        ("stg",  "Helvetica",         8.2,  _safe(r.stage),    0.0),             # STAGE
        ("dob",  "Helvetica",         8.2,  _safe(r.dob),      0.0),             # DATE
    ]

    # 8 uniform lanes (no overlap)
    lanes  = len(rows)
    lane_h = h / lanes                        # each lane height
    MIN_FS = 7.0                              # never go below this font size
    TOP_PAD_FRACTION = 0.82                   # baseline position inside lane

    # Draw lines top→bottom, evenly spaced
    for i, (key, fn, fs, txt, gray) in enumerate(rows):
        lane_top = y0 + h - i * lane_h
        # Clamp size to lane height (ensure a bit of vertical padding)
        fs_lane = min(fs, max(MIN_FS, lane_h - 1.0))
        # For nickname only: try to shrink font to fit width before ellipsizing
        fs_use = fs_lane
        if key == "nick" and txt:
            while fs_use > MIN_FS and stringWidth(txt, fn, fs_use) > text_w:
                fs_use -= 0.3
        # Ellipsize if still too long
        line = _ellipsize(txt, text_w, fn, fs_use)
        baseline = lane_top - (fs_use * TOP_PAD_FRACTION)

        c.setFont(fn, fs_use)
        c.setFillGray(gray)
        c.drawString(col_x, baseline, line)

    # Draw QR last
    payload = r.qr_payload or f"{r.fish_code}|{tank}"
    _draw_qr(c, payload, qr_x, qr_y, QR_SIZE)

def build_pdf(rows: Iterable[Dict[str, Any]], fp) -> None:
    """Render a PDF of 2.4×1.5 in labels. rows = dicts with:
       fish_code, name, genotype, nickname, tg_nick, stage, dob [, tank_code, qr_payload]"""
    c = _canvas.Canvas(fp, pagesize=(LABEL_W, LABEL_H))
    for row in rows:
        r = LabelRow(
            fish_code=_safe(row.get("fish_code")),
            name=_safe(row.get("name")),
            genotype=_safe(row.get("genotype")),
            nickname=_safe(row.get("nickname")),
            tg_nick=_safe(row.get("tg_nick")),
            stage=_safe(row.get("stage")),
            dob=_safe(row.get("dob")),
            tank_code=_safe(row.get("tank_code")) or None,
            qr_payload=_safe(row.get("qr_payload")) or None,
        )
        if not r.tank_code:
            r.tank_code = tank_code_for(r.fish_code)
        render_label(c, r)
        c.showPage()
    c.save()