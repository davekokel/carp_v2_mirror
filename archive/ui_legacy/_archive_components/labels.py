# components/labels.py
import io
import streamlit as st
import pandas as pd
import qrcode

def _lazy_reportlab():
    try:
        from reportlab.lib.pagesizes import inch
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        return inch, canvas, ImageReader
    except Exception:
        return None, None, None

def _to_png_bytes(pil_or_wrapper) -> bytes:
    if hasattr(pil_or_wrapper, "get_image"):
        pil = pil_or_wrapper.get_image()
    else:
        pil = pil_or_wrapper
    buf = io.BytesIO()
    if pil.mode not in ("RGB", "RGBA"):
        pil = pil.convert("RGB")
    pil.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()

def generate_labels(df: pd.DataFrame) -> bytes | None:
    inch, canvas, ImageReader = _lazy_reportlab()
    if not canvas:
        st.warning(
            "Label PDF generation requires `reportlab`. "
            "Assigning still works; printing is disabled on Cloud. "
            "If you want labels here, add `reportlab` to requirements.txt."
        )
        return None

    if "tank" not in df.columns:
        raise ValueError("Input data is missing 'tank' column.")
    if (df["tank"].fillna("").str.strip() == "").any():
        raise ValueError("Tank code is required for all labels.")

    LABEL_W, LABEL_H = 2.4 * inch, 1.5 * inch
    MARGIN_L = MARGIN_R = MARGIN_T = MARGIN_B = 8

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(LABEL_W, LABEL_H))

    for _, row in df.iterrows():
        tank = str(row.get("tank", "") or "").strip()
        auto = str(row.get("auto_fish_code", "") or "").strip()
        fish_name = str(row.get("fish_name", "") or "").strip()
        nickname = str(row.get("nickname", "") or "").strip()
        alleles = str(row.get("alleles", "") or "").strip()
        stage = str(row.get("line_building_stage", "") or "").strip()
        dob = row.get("date_of_birth", "")
        dob_str = ""
        if pd.notna(dob) and str(dob) != "NaT":
            try:
                dob_str = pd.to_datetime(dob).date().isoformat()
            except Exception:
                dob_str = str(dob)

        y = LABEL_H - MARGIN_T - 2
        c.setFont("Helvetica-Bold", 14)
        c.drawString(MARGIN_L, y, tank)
        if auto:
            c.setFont("Helvetica", 10)
            w = c.stringWidth(auto, "Helvetica", 10)
            c.drawString(LABEL_W - MARGIN_R - w, y, auto)

        y -= 16
        if fish_name:
            c.setFont("Helvetica", 10); c.drawString(MARGIN_L, y, fish_name)
        if nickname:
            y -= 12; c.setFont("Helvetica-Bold", 10); c.drawString(MARGIN_L, y, nickname)
        if alleles:
            y -= 12; c.setFont("Helvetica", 9); c.drawString(MARGIN_L, y, alleles)
        if stage:
            y -= 12; c.setFont("Helvetica", 9); c.drawString(MARGIN_L, y, stage)
        if dob_str:
            y -= 12; c.setFont("Helvetica", 9); c.drawString(MARGIN_L, y, f"DOB: {dob_str}")

        qr = qrcode.QRCode(box_size=2, border=1)
        qr.add_data(tank); qr.make(fit=True)
        qr_png = _to_png_bytes(qr.make_image(fill_color="black", back_color="white"))
        qr_w = qr_h = 0.8 * inch
        c.drawImage(ImageReader(io.BytesIO(qr_png)),
                    LABEL_W - MARGIN_R - qr_w, MARGIN_B, qr_w, qr_h, mask="auto")

        c.showPage()

    c.save(); buf.seek(0)
    return buf.getvalue()