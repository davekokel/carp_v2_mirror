from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, date
from typing import Iterable, List, Dict, Any, Optional

from reportlab.pdfgen import canvas as _canvas
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_LEFT
from reportlab.graphics.barcode import qr
from reportlab.graphics import renderPDF
from reportlab.pdfbase.pdfmetrics import stringWidth, registerFont
from reportlab.pdfbase.ttfonts import TTFont

# ----- Geometry (2.4" x 1.5") -----
PT_PER_IN = 72.0
LABEL_W   = 2.4 * PT_PER_IN          # 172.8 pt
LABEL_H   = 1.5 * PT_PER_IN          # 108.0 pt
PADDING   = 10.0
QR_SIZE   = 42.0                      # smaller QR → more body height
GAP       = 6.0
QR_GAP_X  = 8.0                       # extra right margin inside bottom band (away from QR)
HAIRLINE  = 0.5                        # crisp half-pixel stroke

# ----- Typography -----
styles = getSampleStyleSheet()

STYLE_BODY = ParagraphStyle(
    "body",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=8.3,                     # slightly smaller for clarity
    leading=10.8,                     # a touch more line spacing
    alignment=TA_LEFT,
    leftIndent=0, firstLineIndent=0, bulletIndent=0, spaceBefore=0, spaceAfter=0,
)

STYLE_SMALL = ParagraphStyle(
    "small",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=7.5,
    leading=9.5,
    alignment=TA_LEFT,
    leftIndent=0, firstLineIndent=0, bulletIndent=0, spaceBefore=0, spaceAfter=0,
)

# Optional mono font (slashed/dotted zero) for fish/genotype
MONO_FONT_NAME = None
for path in [
    os.environ.get("LABELS_MONO_TTF"),
    "/Library/Fonts/SourceCodePro-Regular.ttf",
    "/Library/Fonts/FiraCode-Regular.ttf",
    "/Library/Fonts/DejaVu Sans Mono.ttf",
    "/System/Library/Fonts/Supplemental/Andale Mono.ttf",
    os.path.expanduser("~/.fonts/DejaVuSansMono.ttf"),
    os.path.expanduser("~/.local/share/fonts/DejaVuSansMono.ttf"),
]:
    try:
        if path and os.path.exists(path):
            registerFont(TTFont("LabelMono", path))
            MONO_FONT_NAME = "LabelMono"
            break
    except Exception:
        pass

# Top two single-line strings drawn explicitly (no paragraph overlap)
TOP_FONT    = ("Helvetica-Bold", 11.0)
SECOND_FONT = (MONO_FONT_NAME or "Helvetica", 9.5)  # fish code in mono if available
LINE_GAP    = 1.5

# ----- Helpers -----
def _text(x) -> str:
    """Return a printable string; blank/None becomes 'MISSING'."""
    if x is None:
        return "MISSING"
    if isinstance(x, (datetime, date)):
        return x.strftime("%Y-%m-%d")
    s = str(x).strip()
    return s if s else "MISSING"

def _ellipsize(s: str, max_w: float, font_name: str, font_size: float) -> str:
    if not s:
        s = "MISSING"
    if stringWidth(s, font_name, font_size) <= max_w:
        return s
    ell = "…"
    lo, hi = 0, len(s)
    while lo < hi:
        mid = (lo + hi) // 2
        if stringWidth(s[:mid] + ell, font_name, font_size) <= max_w:
            lo = mid + 1
        else:
            hi = mid
    cut = max(0, lo - 1)
    return (s[:cut] + ell) if cut > 0 else ell

# Crockford base-32 (no I, L, O, U → fewer ambiguous glyphs)
_ALPH = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
def _base32_crockford(n: int) -> str:
    if n == 0:
        return "0"
    out, x = [], abs(n)
    while x:
        x, r = divmod(x, 32)
        out.append(_ALPH[r])
    return "".join(reversed(out))

def tank_code_for(fish_code: str, when: Optional[datetime] = None) -> str:
    """
    TANK-YYXXXX (Crockford base-32 suffix)
    YY: two-digit year (UTC)
    """
    when = when or datetime.utcnow()
    yy = when.strftime("%y")
    # FNV-1a-ish 32-bit stable hash
    h = 2166136261
    for ch in (fish_code or ""):
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    code = _base32_crockford(h)[:4].rjust(4, "0")
    return f"TANK-{yy}{code}"

def _draw_paragraph(c: _canvas.Canvas, text: str, style: ParagraphStyle,
                    x: float, y: float, w: float, h: float) -> float:
    p = Paragraph(text or "", style)
    _, th = p.wrap(w, h)
    p.drawOn(c, x, y + (h - th))
    return th

def _draw_qr(c: _canvas.Canvas, payload: str, x: float, y: float, size: float) -> None:
    code = qr.QrCodeWidget(payload or "")
    bounds = code.getBounds()
    bw = bounds[2] - bounds[0]; bh = bounds[3] - bounds[1]
    sx = size / bw; sy = size / bh
    from reportlab.graphics.shapes import Drawing
    d = Drawing(size, size, transform=[sx, 0, 0, sy, 0, 0])
    d.add(code)
    renderPDF.draw(d, c, x, y)

# ----- Data model -----
@dataclass
class LabelRow:
    fish_code: str
    nickname: Optional[str]
    name: Optional[str]
    base_code: Optional[str]
    tg_nick: Optional[str]     # genetic background (bottom band)
    stage: Optional[str]
    dob: Optional[str]
    genotype: Optional[str]
    tank_code: Optional[str] = None
    qr_payload: Optional[str] = None

# ----- Renderer -----
def render_label(c: _canvas.Canvas, r: LabelRow) -> None:
    """
    Top:   tank code (left) + fish_code (mono if available, right)
    Body:  NAME, GENOTYPE, NICKNAME — always drawn (each ellipsized to width)
    Bottom: genetic background ; stage • DOB (ellipsized), left of QR
    QR:    bottom-right
    """
    tank = r.tank_code or tank_code_for(_text(r.fish_code))
    fish = _text(r.fish_code)

    nm   = _text(r.name)
    gt   = _text(r.genotype)
    nick = _text(r.nickname)

    bg    = _text(r.tg_nick)
    stage = _text(r.stage)
    dob   = _text(r.dob)
    stage_dob = " • ".join([x for x in (stage, dob) if x])

    # Geometry
    x0, y0 = PADDING, PADDING
    w = LABEL_W - 2 * PADDING
    h = LABEL_H - 2 * PADDING

    qr_x = x0 + w - QR_SIZE
    qr_y = y0

    top_x = x0
    top_y = y0 + QR_SIZE + GAP
    top_w = w
    top_h = h - QR_SIZE - GAP

    bot_x = x0
    bot_y = y0
    bot_w = w - QR_SIZE - GAP - QR_GAP_X
    bot_h = QR_SIZE

    # ---- Top: tank left, fish right ----
    tx, ty = top_x, top_y + top_h
    c.setFont(*TOP_FONT)
    y1 = ty - TOP_FONT[1]
    c.drawString(tx, y1, tank)

    c.setFont(*SECOND_FONT)
    y2 = y1 - SECOND_FONT[1] - LINE_GAP
    fish_w = c.stringWidth(fish, *SECOND_FONT)
    c.drawString(max(tx, tx + top_w - fish_w), y2, fish)

    # ---- Body: ALWAYS draw 3 lines (NAME, GENOTYPE, NICKNAME) ----
    line_h = STYLE_BODY.leading
    body_top = y2 - 2.0

    nm_s = _ellipsize(nm,   top_w, STYLE_BODY.fontName, STYLE_BODY.fontSize)
    gt_s = _ellipsize(gt,   top_w, (MONO_FONT_NAME or STYLE_BODY.fontName), STYLE_BODY.fontSize)
    nk_s = _ellipsize(nick, top_w, STYLE_BODY.fontName, STYLE_BODY.fontSize)

    def draw_line(txt: str, y_base: float, mono: bool = False, italic: bool = False, color: str = None):
        style = STYLE_BODY
        if mono and MONO_FONT_NAME:
            style = ParagraphStyle("mono", parent=STYLE_BODY, fontName=MONO_FONT_NAME)
        t = txt
        if italic:
            t = f"<i>{t.replace('&','&amp;') if '<' not in t else t}</i>"
        else:
            t = t.replace("&","&amp;") if "<" not in t else t
        if color:
            t = f'<font color="{color}">{t}</font>'
        p = Paragraph(t, style)
        _, th = p.wrap(top_w, line_h)
        p.drawOn(c, top_x, y_base - th)

    yb1 = body_top
    yb2 = yb1 - line_h
    yb3 = yb2 - line_h
    draw_line(nm_s, yb1, mono=False, italic=False)               # NAME
    draw_line(gt_s, yb2, mono=True,  italic=False)               # GENOTYPE (mono if available)
    draw_line(nk_s, yb3, mono=False, italic=True, color="#444444")  # NICKNAME (italic + dim)

    # ---- Divider at top of bottom band (half-pixel y + white strip) ----
    rule_y = bot_y + bot_h + 1.3
    c.setLineWidth(HAIRLINE)
    c.setFillGray(1.0)
    c.rect(bot_x, rule_y - 1.2, bot_w, 1.2, stroke=0, fill=1)
    c.setFillGray(0.0)
    c.line(bot_x, rule_y, bot_x + bot_w, rule_y)

    # ---- Bottom band (ellipsized; slight left inset so it doesn't glue to nickname) ----
    small_font = STYLE_SMALL.fontName
    small_size = STYLE_SMALL.fontSize
    bg_line = _ellipsize(bg,        bot_w, small_font, small_size)
    sd_line = _ellipsize(stage_dob, bot_w, small_font, small_size)
    bottom_text = "<br/>".join([
        bg_line.replace("&", "&amp;"),
        sd_line.replace("&", "&amp;"),
    ])
    _draw_paragraph(c, bottom_text, STYLE_SMALL, bot_x + 2.0, bot_y, bot_w - 2.0, bot_h)

    # ---- QR ----
    payload = fish or tank
    _draw_qr(c, payload, qr_x, qr_y, QR_SIZE)

def build_pdf(rows: Iterable[Dict[str, Any]], fp) -> None:
    c = _canvas.Canvas(fp, pagesize=(LABEL_W, LABEL_H))
    for row in rows:
        r = LabelRow(
            fish_code=row.get("fish_code"),
            nickname=row.get("nickname"),
            name=row.get("name"),
            base_code=row.get("base_code"),
            tg_nick=row.get("tg_nick"),
            stage=row.get("stage"),
            dob=row.get("dob"),
            genotype=row.get("genotype"),
        )
        r.tank_code  = tank_code_for(_text(r.fish_code))
        r.qr_payload = _text(r.fish_code) or r.tank_code
        render_label(c, r)
        c.showPage()
    c.save()
