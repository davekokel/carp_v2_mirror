# supabase/ui/pages/032_🐟_schedule_crosses_and_cross_labels.py
# Unique setups (clutch × mother × father) → history → schedule next cross → date-based report & labels

from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

import os
from datetime import date, timedelta
from io import BytesIO
from typing import Dict, Any, List

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ---------------- Page & DB ----------------
st.set_page_config(page_title="🐟 Crossing history, schedule & labels", page_icon="🐟", layout="wide")
st.title("🐟 Crossing history, schedule & labels")

ENGINE = create_engine(os.environ["DB_URL"], pool_pre_ping=True)

# ---------------- Helpers (genotype formatting) ----------------
import re
def _split_rollup(s: str) -> list[str]:
    if not s: return []
    parts = re.split(r"[;,\|]+", str(s))
    return [p.strip() for p in parts if p and p.strip()]

def _tgify(elems: list[str]) -> str:
    """
    Convert e.g. pDQM005-301 / pDQM005^301 -> Tg(pDQM005)301; ...
    """
    out = []
    for e in elems or []:
        m = re.match(r"^\s*([A-Za-z0-9\-]+)\s*(?:[\-\^])\s*(\d+)\s*$", e or "")
        if m: out.append(f"Tg({m.group(1)}){m.group(2)}")
        elif e: out.append(e)
    return "; ".join(out)

def _clutch_geno_from_planned_name(name: str) -> str:
    if not name: return ""
    parts = name.split(">", 1)
    return _tgify(_split_rollup(parts[1])) if len(parts) == 2 else ""

# ---------------- Loaders ----------------
def _load_unique_setups(q: str, limit: int = 1000) -> pd.DataFrame:
    """
    Show unique (clutch_id, mother_tank_id, father_tank_id) with summary.
    """
    sql = text("""
      with base as (
        select
          pc.clutch_id,
          pc.mother_tank_id,
          pc.father_tank_id,
          count(*)         as n_runs,
          max(pc.cross_date) as last_cross_date,
          max(pc.created_at) as last_created_at
        from public.planned_crosses pc
        group by pc.clutch_id, pc.mother_tank_id, pc.father_tank_id
      )
      select
        b.clutch_id::text                       as clutch_id,
        cp.clutch_code,
        cp.planned_name,
        pc.mom_code,
        pc.dad_code,
        b.mother_tank_id::text                  as mother_tank_id,
        cm.label                                 as mother_tank,
        b.father_tank_id::text                  as father_tank_id,
        cf.label                                 as father_tank,
        b.n_runs,
        b.last_cross_date,
        b.last_created_at
      from base b
      join public.clutch_plans cp on cp.id_uuid = b.clutch_id
      join lateral (
        select *
        from public.planned_crosses pc2
        where pc2.clutch_id = b.clutch_id
          and pc2.mother_tank_id = b.mother_tank_id
          and pc2.father_tank_id = b.father_tank_id
        order by pc2.created_at desc
        limit 1
      ) pc on true
      left join public.containers cm on cm.id_uuid = b.mother_tank_id
      left join public.containers cf on cf.id_uuid = b.father_tank_id
      where (
        :q = '' OR
        cp.clutch_code ilike :qlike OR
        cp.planned_name ilike :qlike OR
        pc.mom_code ilike :qlike OR
        pc.dad_code ilike :qlike OR
        coalesce(cm.label,'') ilike :qlike OR
        coalesce(cf.label,'') ilike :qlike
      )
      order by b.last_cross_date desc nulls last, b.last_created_at desc
      limit :lim
    """)
    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx, params={"q": q or "", "qlike": f"%{q or ''}%", "lim": int(limit)})

def _load_history(clutch_id: str, mother_tank_id: str, father_tank_id: str) -> pd.DataFrame:
    sql = text("""
      select
        coalesce(pc.cross_code, pc.id_uuid::text)    as cross_code,
        pc.cross_date,
        pc.note,
        pc.created_by,
        pc.created_at,
        pc.mother_tank_id::text                      as mother_tank_id,
        pc.father_tank_id::text                      as father_tank_id,
        pc.mom_code,
        pc.dad_code,
        cp.clutch_code,
        cp.planned_name
      from public.planned_crosses pc
      join public.clutch_plans cp on cp.id_uuid = pc.clutch_id
      where pc.clutch_id       = cast(:cid as uuid)
        and pc.mother_tank_id  = cast(:mid as uuid)
        and pc.father_tank_id  = cast(:fid as uuid)
      order by pc.cross_date desc nulls last, pc.created_at desc
    """)
    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx, params={"cid": clutch_id, "mid": mother_tank_id, "fid": father_tank_id})

def _schedule_next_run(clutch_id: str, mom_code: str, dad_code: str,
                       mother_tank_id: str, father_tank_id: str,
                       next_date: date, note: str, created_by: str) -> None:
    sql = text("""
      insert into public.planned_crosses
        (clutch_id, mom_code, dad_code, mother_tank_id, father_tank_id, cross_date, note, created_by)
      values
        (cast(:cid as uuid), :mom, :dad, cast(:mid as uuid), cast(:fid as uuid), :d, :note, :by)
    """)
    with ENGINE.begin() as cx:
        cx.execute(sql, {
            "cid": clutch_id, "mom": mom_code, "dad": dad_code,
            "mid": mother_tank_id, "fid": father_tank_id,
            "d": pd.to_datetime(next_date).date(),
            "note": note, "by": created_by,
        })

def _load_crosses_for_date(d: date, q: str, limit: int = 2000) -> pd.DataFrame:
    sql = text("""
      select
        coalesce(pc.cross_code, pc.id_uuid::text) as cross_code,
        pc.cross_date,
        pc.note,
        pc.created_by,
        pc.created_at,
        pc.mother_tank_id::text as mother_tank_id,
        cm.label                 as mother_tank,     -- NEW
        pc.father_tank_id::text as father_tank_id,
        cf.label                 as father_tank,     -- NEW
        pc.mom_code,
        pc.dad_code,
        cp.clutch_code,
        cp.planned_name
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
      order by pc.created_at asc
      limit :lim
    """)
    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx, params={
            "d0": pd.to_datetime(d).date(), "d1": (pd.to_datetime(d).date() + timedelta(days=1)),
            "q": q or "", "qlike": f"%{q or ''}%", "lim": int(limit)
        })

# ---------------- Unique setups ----------------
with st.form("setup_filters"):
    cc1, cc2 = st.columns([3,1])
    with cc1:
        q_setups = st.text_input("Search setups (clutch / name / mom / dad / tank label)", "")
    with cc2:
        lim_setups = int(st.number_input("Limit", min_value=1, max_value=5000, value=1000, step=100))
    submitted = st.form_submit_button("Apply")

df_setups = _load_unique_setups(q_setups, lim_setups)
st.caption(f"{len(df_setups)} unique setup(s)")
if df_setups.empty:
    st.info("No unique cross setups match.")
    st.stop()

view = df_setups.copy()
view.insert(0, "✓ Select", False)
try:
    view["last_cross_date"] = pd.to_datetime(view["last_cross_date"]).dt.strftime("%Y-%m-%d")
except Exception:
    pass
order = ["✓ Select","clutch_code","planned_name","mom_code","mother_tank","dad_code","father_tank","n_runs","last_cross_date"]
edited_setups = st.data_editor(
    view, use_container_width=True, hide_index=True, column_order=order,
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
        "clutch_code":  st.column_config.TextColumn("clutch_code", disabled=True),
        "planned_name": st.column_config.TextColumn("planned_name", disabled=True),
        "mom_code":     st.column_config.TextColumn("mom_code", disabled=True),
        "mother_tank":  st.column_config.TextColumn("mother_tank", disabled=True),
        "dad_code":     st.column_config.TextColumn("dad_code", disabled=True),
        "father_tank":  st.column_config.TextColumn("father_tank", disabled=True),
        "n_runs":       st.column_config.NumberColumn("n_runs", disabled=True),
        "last_cross_date": st.column_config.TextColumn("last_cross_date", disabled=True),
    },
    key="setup_unique_editor",
)

picked_setups = edited_setups[edited_setups["✓ Select"]].copy()
if picked_setups.empty:
    st.info("Select a cross setup to see history and schedule the next run.")
    st.stop()

sel_row = picked_setups.iloc[0]
sel_combo = {
    "clutch_id":      sel_row["clutch_id"],
    "clutch_code":    sel_row["clutch_code"],
    "planned_name":   sel_row["planned_name"],
    "mom_code":       sel_row["mom_code"],
    "dad_code":       sel_row["dad_code"],
    "mother_tank_id": sel_row["mother_tank_id"],
    "father_tank_id": sel_row["father_tank_id"],
    "mother_tank":    sel_row["mother_tank"],
    "father_tank":    sel_row["father_tank"],
}

# ---------------- History ----------------
st.subheader(f"History — {sel_combo['clutch_code']} • {sel_combo['mother_tank']} × {sel_combo['father_tank']}")
hist = _load_history(sel_combo["clutch_id"], sel_combo["mother_tank_id"], sel_combo["father_tank_id"])
if hist.empty:
    st.info("No previous runs for this setup.")
else:
    h = hist.copy()
    try:
        h["cross_date"] = pd.to_datetime(h["cross_date"]).dt.strftime("%A, %Y/%m/%d")
    except Exception:
        pass
    st.dataframe(h, use_container_width=True, hide_index=True)

# ---------------- Schedule next cross ----------------
st.subheader("Schedule next cross")
c1, c2 = st.columns([1,3])
with c1:
    next_date = st.date_input("Next date", value=pd.Timestamp.today().date())
with c2:
    note = st.text_input("Optional note", value="")
if st.button("➕ Schedule", type="primary", use_container_width=True):
    _schedule_next_run(
        clutch_id      = sel_combo["clutch_id"],
        mom_code       = sel_combo["mom_code"],
        dad_code       = sel_combo["dad_code"],
        mother_tank_id = sel_combo["mother_tank_id"],
        father_tank_id = sel_combo["father_tank_id"],
        next_date      = next_date,
        note           = note,
        created_by     = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
    )
    st.success("Scheduled the next run.")
    # refresh history block
    hist = _load_history(sel_combo["clutch_id"], sel_combo["mother_tank_id"], sel_combo["father_tank_id"])
    if not hist.empty:
        try:
            hist["cross_date"] = pd.to_datetime(hist["cross_date"]).dt.strftime("%A, %Y/%m/%d")
        except Exception:
            pass
        st.dataframe(hist, use_container_width=True, hide_index=True)

# ---------------- Report & labels by date ----------------
st.subheader("Report & labels by date")
rc1, rc2 = st.columns([1,3])
with rc1:
    report_date = st.date_input("Report date", value=pd.Timestamp.today().date(), key="report_date")
with rc2:
    q_report = st.text_input("Optional filter (clutch / name / mom / dad)", "", key="q_report")

df_rundate = _load_crosses_for_date(report_date, q_report)
st.caption(f"{len(df_rundate)} cross(es) scheduled on {report_date}")
if df_rundate.empty:
    st.info("No crosses on that date.")
    st.stop()

# Select rows to print — include both tank LABELS and IDs so they survive the editor round-trip
rv = df_rundate.copy()
rv.insert(0, "✓ Select", False)
col_order = [
    "✓ Select","cross_code","clutch_code","planned_name",
    "mom_code","mother_tank","mother_tank_id",
    "dad_code","father_tank","father_tank_id",
    "cross_date","note"
]
rved = st.data_editor(
    rv,
    use_container_width=True, hide_index=True,
    column_order=col_order,
    column_config={
        "✓ Select":       st.column_config.CheckboxColumn("✓ Select", default=False),
        "cross_code":     st.column_config.TextColumn("cross_code", disabled=True),
        "clutch_code":    st.column_config.TextColumn("clutch_code", disabled=True),
        "planned_name":   st.column_config.TextColumn("planned_name", disabled=True),
        "mom_code":       st.column_config.TextColumn("mom_code", disabled=True),
        "mother_tank":    st.column_config.TextColumn("mother_tank", disabled=True),     # LABEL
        "mother_tank_id": st.column_config.TextColumn("mother_tank_id", disabled=True),  # ID
        "dad_code":       st.column_config.TextColumn("dad_code", disabled=True),
        "father_tank":    st.column_config.TextColumn("father_tank", disabled=True),     # LABEL
        "father_tank_id": st.column_config.TextColumn("father_tank_id", disabled=True),  # ID
        "cross_date":     st.column_config.TextColumn("cross_date", disabled=True),
        "note":           st.column_config.TextColumn("note"),
    },
    key="runs_for_date_editor",
)
sel_for_print = rved[rved["✓ Select"]].copy()
if sel_for_print.empty:
    st.info("Select runs above to print a report or labels.")
    st.stop()

# ----- fetch genotypes for selected rows -----
mom_codes = sorted(set(sel_for_print["mom_code"].dropna().astype(str)))
dad_codes = sorted(set(sel_for_print["dad_code"].dropna().astype(str)))
need_codes = sorted(set(mom_codes + dad_codes))
geno_by_fish: Dict[str, str] = {}
if need_codes:
    with ENGINE.begin() as cx:
        df_g = pd.read_sql(text("""
            select fish_code, genotype
            from public.vw_fish_standard
            where fish_code = any(:codes)
        """), cx, params={"codes": need_codes})
    for _, r in df_g.iterrows():
        geno_by_fish[str(r["fish_code"])] = _tgify(_split_rollup(r.get("genotype") or ""))

# Build report preview — use tank LABELS
st.subheader("Crossing report (preview)")
rep = sel_for_print.copy()
rep["Cross date"] = pd.to_datetime(rep["cross_date"]).dt.strftime("%A, %Y/%m/%d")
rep_show = rep[[
    "clutch_code","planned_name",
    "mom_code","mother_tank",
    "dad_code","father_tank",
    "Cross date","note"
]]
st.dataframe(rep_show, use_container_width=True, hide_index=True)

# ----- Build PDFs -----
from reportlab.pdfgen import canvas as _canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO

# mono font (ok if registration fails)
try:
    pdfmetrics.registerFont(TTFont("LabelMono", "/Library/Fonts/SourceCodePro-Regular.ttf"))
    MONO = "LabelMono"
except Exception:
    MONO = "Courier"

# ---------------- Report PDF (letter) ----------------
def _build_report_pdf(dfrep: pd.DataFrame) -> bytes:
    buf = BytesIO()
    c = _canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    x0, y = 0.7*inch, height - 0.8*inch

    c.setFont("Helvetica-Bold", 14)
    c.drawString(x0, y, "Crossing Report")
    y -= 0.25*inch
    c.setFont("Helvetica", 9)

    headers = ["Clutch", "Name", "Mom tank", "Dad tank", "Date", "Note"]
    colw    = [1.1*inch, 2.6*inch, 2.3*inch, 2.3*inch, 1.2*inch, 1.3*inch]

    # header row
    c.setFont("Helvetica-Bold", 9); x = x0
    for h, w in zip(headers, colw):
        c.drawString(x, y, h); x += w
    y -= 0.18*inch; c.setFont("Helvetica", 9)

    # rows
    for _, r in dfrep.iterrows():
        if y < 0.8*inch:
            c.showPage(); y = height - 0.8*inch; c.setFont("Helvetica", 9)
            c.setFont("Helvetica-Bold", 9); x = x0
            for h, w in zip(headers, colw): c.drawString(x, y, h); x += w
            y -= 0.18*inch; c.setFont("Helvetica", 9)

        x = x0
        cells  = [
            str(r.get("clutch_code", ""))[:85],
            str(r.get("planned_name",""))[:85],
            str(r.get("mother_tank",""))[:85],
            str(r.get("father_tank",""))[:85],
            pd.to_datetime(r.get("cross_date")).strftime("%A, %Y/%m/%d"),
            str(r.get("note",""))[:85]
        ]
        for cell, w in zip(cells, colw):
            c.drawString(x, y, cell); x += w
        y -= 0.16*inch

    c.showPage(); c.save(); buf.seek(0)
    return buf.read()

# ---------------- Labels PDF (2.4 × 1.5) ----------------
PT = 72.0
W, H = 2.4*PT, 1.5*PT
PAD_L, PAD_R, PAD_T, PAD_B = 10, 10, 8, 8

HDR_FS   = 11.0     # CROSS line
DATE_FS  = 9.0      # date line
BODY_FS  = 8.6      # body lines
ARROW_FS = 12.0
STEP     = 10.2     # vertical step

def _clip(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else (s[:max(0, n-1)] + "…")

def _label_pdf(rows: List[Dict[str, Any]]) -> bytes:
    buf = BytesIO()
    c = _canvas.Canvas(buf, pagesize=(W, H))
    max_chars_label = 34   # rough safe width at BODY_FS
    max_chars_geno  = 60

    for t in rows:
        # collect fields
        cross_code  = (t.get("cross_code") or "")[:12]
        cross_date  = pd.to_datetime(t.get("cross_date")).strftime("%a, %Y/%m/%d")
        mom_label   = _clip(t.get("mother_tank") or "", max_chars_label)   # tank LABEL
        dad_label   = _clip(t.get("father_tank") or "", max_chars_label)
        mom_geno    = _clip(t.get("mom_geno") or "", max_chars_geno)
        dad_geno    = _clip(t.get("dad_geno") or "", max_chars_geno)
        clutch_code = t.get("clutch_code") or ""
        clutch_geno = _clip(t.get("clutch_geno") or "", max_chars_geno)

        # 1) CROSS line
        y = H - PAD_T - HDR_FS
        c.setFont("Helvetica-Bold", HDR_FS)
        c.drawString(PAD_L, y, f"CROSS {cross_code}")

        # 2) DATE
        y -= STEP
        c.setFont("Helvetica", DATE_FS)
        c.drawString(PAD_L, y, cross_date)

        # 3) Mom tank label
        y -= STEP
        c.setFont(MONO, BODY_FS)   # mono for readability of tank codes
        c.drawString(PAD_L, y, f"Mom {mom_label}")

        # 4) Mom genotype
        y -= STEP
        c.setFont("Helvetica", BODY_FS)
        c.drawString(PAD_L, y, mom_geno)

        # 5) Dad tank label
        y -= STEP
        c.setFont(MONO, BODY_FS)
        c.drawString(PAD_L, y, f"Dad {dad_label}")

        # 6) Dad genotype
        y -= STEP
        c.setFont("Helvetica", BODY_FS)
        c.drawString(PAD_L, y, dad_geno)

        # 7) arrow
        y -= STEP
        c.setFont("Helvetica-Bold", ARROW_FS)
        c.drawCentredString(W/2.0, y+2, "↓")

        # 8) clutch code
        y -= STEP
        c.setFont("Helvetica", BODY_FS)
        c.drawString(PAD_L, y, str(clutch_code))

        # 9) clutch genotype
        y -= STEP
        c.drawString(PAD_L, y, clutch_geno)

        c.showPage()

    c.save(); buf.seek(0)
    return buf.read()

# assemble label rows (uses tank LABELS)
label_rows = []
for _, r in sel_for_print.iterrows():
    clutch_geno = _clutch_geno_from_planned_name(str(r.get("planned_name") or ""))
    label_rows.append({
        "cross_code":    str(r.get("cross_code") or "")[:12],
        "cross_date":    pd.to_datetime(r.get("cross_date")).date() if r.get("cross_date") else pd.Timestamp.today().date(),
        "mother_tank":   str(r.get("mother_tank") or ""),   # LABEL (human tank code)
        "father_tank":   str(r.get("father_tank") or ""),   # LABEL
        "mom_geno":      geno_by_fish.get(str(r.get("mom_code") or ""), ""),
        "dad_geno":      geno_by_fish.get(str(r.get("dad_code") or ""), ""),
        "clutch_code":   str(r.get("clutch_code") or ""),
        "clutch_geno":   clutch_geno,
    })

# build PDFs
rep_pdf = _build_report_pdf(sel_for_print)
lab_pdf = _label_pdf(label_rows)

st.download_button("📄 Download crossing report (PDF)", data=rep_pdf,
                   file_name=f"crossing_report_{pd.Timestamp.today().strftime('%Y%m%d')}.pdf",
                   mime="application/pdf", use_container_width=True)
st.download_button("🏷️ Download crossing tank labels (PDF)", data=lab_pdf,
                   file_name=f"crossing_tank_labels_{pd.Timestamp.today().strftime('%Y%m%d')}.pdf",
                   mime="application/pdf", use_container_width=True)