# components/labels.py
import io
import streamlit as st
import pandas as pd
import qrcode  # ensure qrcode[pil] in requirements

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
    try:
        from reportlab.lib.pagesizes import inch
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
    except Exception:
        st.warning(
            "Label PDF generation requires `reportlab`, which isn’t installed on Cloud. "
            "Assigning still works; printing is disabled. "
            "Add `reportlab` to requirements.txt to enable PDFs in Cloud."
        )
        return None

    if "tank" not in df.columns:
        raise ValueError("Input data is missing 'tank' column.")
    missing = df.loc[df["tank"].fillna("").str.strip() == "", "fish_name"].tolist()
    if missing:
        raise ValueError(
            "Tank code is required for all labels. Missing for: "
            + ", ".join(missing[:10]) + (" ..." if len(missing) > 10 else "")
        )

    LABEL_W, LABEL_H = 2.4 * inch, 1.5 * inch
    MARGIN_L = MARGIN_R = MARGIN_T = MARGIN_B = 8

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(LABEL_W, LABEL_H))

    for _, row in df.iterrows():
        tank = str(row.get("tank", "") or "").strip()
        auto = str(row.get("auto_fish_code", "") or "").strip()
        fish_name = str(row.get("fish_name", "") or "").strip()
        nickname = "" if row.get("nickname") is None else str(row.get("nickname")).strip()
        alleles  = "" if row.get("alleles") is None else str(row.get("alleles")).strip()
        stage    = "" if row.get("line_building_stage") is None else str(row.get("line_building_stage")).strip()

        dob = row.get("date_of_birth", "")
        if pd.notna(dob) and str(dob) != "NaT":
            try:
                dob_str = pd.to_datetime(dob).date().isoformat()
            except Exception:
                dob_str = str(dob)
        else:
            dob_str = ""

        y = LABEL_H - MARGIN_T - 2
        c.setFont("Helvetica-Bold", 14); c.drawString(MARGIN_L, y, tank)
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
        from reportlab.lib.pagesizes import inch  # local scope already imported above
        qr_w, qr_h = 0.8 * inch, 0.8 * inch
        c.drawImage(ImageReader(io.BytesIO(qr_png)),
                    LABEL_W - MARGIN_R - qr_w, MARGIN_B,
                    qr_w, qr_h, mask="auto")

        c.showPage()

    c.save(); buf.seek(0)
    return buf.getvalue()