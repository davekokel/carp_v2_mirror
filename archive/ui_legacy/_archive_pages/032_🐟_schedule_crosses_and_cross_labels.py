# supabase/ui/pages/032_🐟_print_crossing_tank_labels.py
# Planned crosses → schedule by day → print crossing report → print tank labels

from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

import os
from io import BytesIO
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ---------------- Page & DB ----------------
st.set_page_config(page_title="🐟 Crossing schedule, report & labels", page_icon="🐟", layout="wide")
st.title("🐟 Crossing schedule, report & labels")

ENGINE = create_engine(os.environ["DB_URL"], pool_pre_ping=True)

# ---------------- Data loaders ----------------
def _load_planned_crosses_range(d0: date, d1_excl: date, q: str, limit: int = 1000) -> pd.DataFrame:
    sql = text("""
      select
        pc.id_uuid::text as cross_id,
        cp.clutch_code,
        cp.planned_name,
        pc.mom_code,
        pc.dad_code,
        cm.id_uuid::text as mother_tank_id,
        coalesce(cm.label,'')  as mother_tank,
        coalesce(cm.status,'') as mother_status,
        cf.id_uuid::text as father_tank_id,
        coalesce(cf.label,'')  as father_tank,
        coalesce(cf.status,'') as father_status,
        pc.cross_date,
        pc.note,
        pc.created_by,
        pc.created_at
      from public.planned_crosses pc
      join public.clutch_plans cp on cp.id_uuid = pc.clutch_id
      left join public.containers cm on cm.id_uuid = pc.mother_tank_id
      left join public.containers cf on cf.id_uuid = pc.father_tank_id
      where pc.cross_date >= :d0 and pc.cross_date < :d1
        and (
          :q = '' OR
          cp.clutch_code ilike :qlike OR
          cp.planned_name ilike :qlike OR
          pc.mom_code ilike :qlike OR
          pc.dad_code ilike :qlike OR
          coalesce(cm.label,'') ilike :qlike OR
          coalesce(cf.label,'') ilike :qlike
        )
      order by pc.cross_date asc, cp.clutch_code asc
      limit :lim
    """)
    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx, params={
            "d0": pd.to_datetime(d0).date(), "d1": pd.to_datetime(d1_excl).date(),
            "q": q or "", "qlike": f"%{q or ''}%", "lim": int(limit),
        })

def _save_schedule_changes(rows: pd.DataFrame) -> int:
    """rows with columns: cross_id, cross_date, note"""
    if rows.empty: return 0
    rows = rows.copy()
    rows["cross_date"] = pd.to_datetime(rows["cross_date"]).dt.date
    with ENGINE.begin() as cx:
        up = text("""
          update public.planned_crosses
             set cross_date = :d, note = :note
           where id_uuid = :id::uuid
        """)
        n = 0
        for _, r in rows.iterrows():
            cx.execute(up, {"id": r["cross_id"], "d": r["cross_date"], "note": r.get("note")})
            n += 1
    return n

def _add_tanks_ok(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    out = df.copy()
    out["Tanks OK"] = out.apply(lambda r: "✓" if r.get("mother_tank") and r.get("father_tank") else "⚠", axis=1)
    return out

# ---------------- Filters ----------------
with st.form("filters"):
    c1, c2, c3 = st.columns([2,2,1])
    with c1:
        date_start = st.date_input("From date", value=pd.Timestamp.today().date())
    with c2:
        date_end   = st.date_input("To date (inclusive)", value=pd.Timestamp.today().date())
    with c3:
        limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=1000, step=100))
    c4, c5 = st.columns([3,1])
    with c4:
        q = st.text_input("Search (clutch_code / planned_name / mom_code / dad_code / tank label)", "")
    with c5:
        by_user = st.text_input("Created by", value=os.environ.get("USER") or os.environ.get("USERNAME") or "unknown")
    submitted = st.form_submit_button("Apply")

# enforce end-exclusive in loader
df = _load_planned_crosses_range(date_start, (pd.to_datetime(date_end).date() + timedelta(days=1)), q, limit)
st.caption(f"{len(df)} planned cross(es) in range")
if df.empty:
    st.info("No planned crosses match your filters.")
    st.stop()

# ---------------- Editable schedule table ----------------
view = df.copy()
view.insert(0, "✓ Select", False)
view["cross_date"] = pd.to_datetime(view["cross_date"]).dt.date  # ensure date type

order = ["✓ Select","cross_id","clutch_code","planned_name",
         "mom_code","mother_tank","mother_status",
         "dad_code","father_tank","father_status",
         "cross_date","note","created_by","created_at"]

edited = st.data_editor(
    view,
    use_container_width=True, hide_index=True, column_order=order,
    column_config={
        "✓ Select":    st.column_config.CheckboxColumn("✓ Select", default=False),
        "cross_id":    st.column_config.TextColumn("cross_id", disabled=True),
        "clutch_code": st.column_config.TextColumn("clutch_code", disabled=True),
        "planned_name":st.column_config.TextColumn("planned_name", disabled=True),
        "mom_code":    st.column_config.TextColumn("mom_code", disabled=True),
        "mother_tank": st.column_config.TextColumn("mother_tank", disabled=True),
        "mother_status": st.column_config.TextColumn("mother_status", disabled=True),
        "dad_code":    st.column_config.TextColumn("dad_code", disabled=True),
        "father_tank": st.column_config.TextColumn("father_tank", disabled=True),
        "father_status": st.column_config.TextColumn("father_status", disabled=True),
        "cross_date":  st.column_config.DateColumn("cross_date"),
        "note":        st.column_config.TextColumn("note"),
        "created_by":  st.column_config.TextColumn("created_by", disabled=True),
        "created_at":  st.column_config.DatetimeColumn("created_at", disabled=True),
    },
    key="planned_crosses_schedule_editor",
)

# ---------------- Bulk date tool & save ----------------
cA, cB, cC = st.columns([2,1,1])
with cA:
    bulk_date = st.date_input("Set date for selected", value=pd.to_datetime(date_start).date())
with cB:
    if st.button("Apply date to selected"):
        mask = edited["✓ Select"] == True
        edited.loc[mask, "cross_date"] = bulk_date
        st.session_state["planned_crosses_schedule_editor"] = edited
with cC:
    save_sched = st.button("💾 Save schedule changes", type="primary", use_container_width=True)

if save_sched:
    rows = edited[["cross_id","cross_date","note"]].copy()
    n = _save_schedule_changes(rows)
    st.success(f"Saved {n} schedule row(s).")

# ---------------- Report & Labels (selected) ----------------
sel = edited[edited["✓ Select"]].copy()
if sel.empty:
    st.info("Select some rows to print a report or labels.")
else:
    st.subheader("Crossing report (preview)")
    rep = sel.copy()
    rep["Cross date"] = pd.to_datetime(rep["cross_date"]).dt.strftime("%A, %Y/%m/%d")
    rep_show = rep[["clutch_code","planned_name","mom_code","mother_tank","dad_code","father_tank","Cross date","note"]]
    st.dataframe(rep_show, use_container_width=True, hide_index=True)

    # -------- Build PDFs --------
    from reportlab.pdfgen import canvas as _canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    try:
        pdfmetrics.registerFont(TTFont("LabelMono", "/Library/Fonts/SourceCodePro-Regular.ttf"))
        MONO = "LabelMono"
    except Exception:
        MONO = "Helvetica"

    # (1) Report PDF
    def _build_report_pdf(dfrep: pd.DataFrame) -> bytes:
        buf = BytesIO()
        c = _canvas.Canvas(buf, pagesize=letter)
        width, height = letter
        x0, y = 0.7*inch, height - 0.8*inch
        c.setFont("Helvetica-Bold", 14); c.drawString(x0, y, "Crossing Report"); y -= 0.25*inch
        c.setFont("Helvetica", 9)

        headers = ["Clutch", "Name", "Mom / Tank", "Dad / Tank", "Date", "Note"]
        colw    = [1.1*inch, 2.3*inch, 2.5*inch, 2.5*inch, 1.2*inch, 1.4*inch]

        c.setFont("Helvetica-Bold", 9)
        x = x0
        for h, w in zip(headers, colw): c.drawString(x, y, h); x += w
        y -= 0.18*inch; c.setFont("Helvetica", 9)

        for _, r in dfrep.iterrows():
            if y < 0.8*inch: c.showPage(); y = height - 0.8*inch; c.setFont("Helvetica", 9)
            x = x0
            momtxt = f"{r['mom_code']} / {r['mother_tank']}"
            dadtxt = f"{r['dad_code']} / {r['father_tank']}"
            cells  = [r["clutch_code"], r["planned_name"], momtxt, dadtxt,
                      pd.to_datetime(r["cross_date"]).strftime("%A, %Y/%m/%d"), r.get("note") or ""]
            for cell, w in zip(cells, colw):
                c.drawString(x, y, str(cell)[:80]); x += w
            y -= 0.16*inch

        c.showPage(); c.save(); buf.seek(0)
        return buf.read()

    # (2) Labels PDF (2.4 x 1.5") — one label per mother/father tank per date, de-duped
    PT = 72.0
    W, H = 2.4*PT, 1.5*PT
    PAD_L, PAD_R, PAD_T, PAD_B = 10, 10, 8, 8

    def _label_pdf(tanks: List[Dict[str,str]]) -> bytes:
        buf = BytesIO()
        c = _canvas.Canvas(buf, pagesize=(W, H))
        for t in tanks:
            label = t["label"][:40]
            code  = t["code"]
            date_str = pd.to_datetime(t["date"]).strftime("%Y/%m/%d")
            x0, y0 = PAD_L, PAD_B
            c.setFont("Helvetica-Bold", 12); c.drawString(x0, H - PAD_T - 12, label)
            c.setFont(MONO, 9);             c.drawString(x0, H - PAD_T - 26, f"{code}  •  {date_str}")
            c.showPage()
        c.save(); buf.seek(0)
        return buf.read()

    # Build labels list (dedupe by id+date)
    label_rows = []
    for _, r in sel.iterrows():
        d = pd.to_datetime(r["cross_date"]).date()
        if r.get("mother_tank_id"):
            label_rows.append({"id": r["mother_tank_id"], "label": r["mother_tank"], "code": r["mom_code"], "date": d})
        if r.get("father_tank_id"):
            label_rows.append({"id": r["father_tank_id"], "label": r["father_tank"], "code": r["dad_code"], "date": d})
    seen = set(); labels = []
    for t in label_rows:
        key = (t["id"], t["date"])
        if key in seen: continue
        seen.add(key); labels.append(t)

    rep_pdf = _build_report_pdf(sel)
    lab_pdf = _label_pdf(labels)

    st.download_button("📄 Download crossing report (PDF)", data=rep_pdf,
                       file_name=f"crossing_report_{pd.Timestamp.today().strftime('%Y%m%d')}.pdf",
                       mime="application/pdf", use_container_width=True)
    st.download_button("🏷️ Download tank labels (PDF)", data=lab_pdf,
                       file_name=f"crossing_tank_labels_{pd.Timestamp.today().strftime('%Y%m%d')}.pdf",
                       mime="application/pdf", use_container_width=True)