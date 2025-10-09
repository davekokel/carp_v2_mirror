# supabase/ui/pages/032_🐟_schedule_crosses_and_cross_labels.py
from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

import os, re
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

# ---------------- tiny DB helpers (needed by petri creation) ----------------
def _table_has_columns(table: str, *cols: str) -> bool:
    sql = text("""
      select array_agg(column_name)::text[]
      from information_schema.columns
      where table_schema='public' and table_name=:t
    """)
    with ENGINE.begin() as cx:
        got = cx.execute(sql, {"t": table}).scalar() or []
    return all(c in got for c in list(cols))

def _first_existing_column(table: str, candidates: list[str]) -> str | None:
    sql = text("""
      select column_name
      from information_schema.columns
      where table_schema='public' and table_name=:t and column_name = any(:cands)
      order by array_position(:cands, column_name)
      limit 1
    """)
    with ENGINE.begin() as cx:
        row = cx.execute(sql, {"t": table, "cands": candidates}).fetchone()
    return row[0] if row else None

# ---------------- Genotype helpers ----------------
def _split_rollup(s: str) -> list[str]:
    if not s: return []
    parts = re.split(r"[;,\|]+", str(s))
    return [p.strip() for p in parts if p and p.strip()]

def _tg_tokens(tokens: list[str]) -> list[str]:
    out = []
    for e in tokens or []:
        m = re.match(r"^\s*([A-Za-z0-9\-]+)\s*(?:[\-\^])\s*(\d+)\s*$", e or "")
        out.append(f"Tg({m.group(1)}){m.group(2)}" if m else e)
    return out

def _tgify(s: str) -> str:
    return "; ".join(_tg_tokens(_split_rollup(s or "")))

def _summarize_list(elems: list[str], max_total: int = 48, sep: str = "; ") -> str:
    if not elems: return ""
    out, used = [], 0
    for i, p in enumerate(elems):
        tok = (sep if out else "") + p
        if used + len(tok) <= max_total:
            out.append(p); used += len(tok)
        else:
            rem = len(elems) - i
            return (sep.join(out) + (f" (+{rem})" if rem > 0 else "")).strip()
    return sep.join(out)

def _clutch_geno_from_planned_name(name: str) -> str:
    if not name: return ""
    parts = name.split(">", 1)
    if len(parts) != 2: return ""
    tokens = _tg_tokens(_split_rollup(parts[1]))
    return _summarize_list(tokens, max_total=46, sep="; ")

# ---------------- Loaders ----------------
def _load_unique_setups(q: str, limit: int = 1000) -> pd.DataFrame:
    sql = text("""
      with base as (
        select
          pc.clutch_id,
          pc.mother_tank_id,
          pc.father_tank_id,
          count(*)            as n_runs,
          max(pc.cross_date)  as last_cross_date,
          max(pc.created_at)  as last_created_at
        from public.planned_crosses pc
        group by pc.clutch_id, pc.mother_tank_id, pc.father_tank_id
      )
      select
        b.clutch_id::text as clutch_id,
        cp.clutch_code,
        cp.planned_name,
        pc.mom_code,
        pc.dad_code,
        b.mother_tank_id::text as mother_tank_id,
        cm.label               as mother_tank,
        b.father_tank_id::text as father_tank_id,
        cf.label               as father_tank,
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
        coalesce(pc.cross_code, pc.id_uuid::text) as cross_code,
        pc.cross_date,
        pc.note,
        pc.created_by,
        pc.created_at,
        pc.mother_tank_id::text as mother_tank_id,
        pc.father_tank_id::text as father_tank_id,
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
        pc.id_uuid::text                           as cross_id,
        coalesce(pc.cross_code, pc.id_uuid::text)  as cross_code,
        pc.cross_date,
        pc.note,
        pc.created_by,
        pc.created_at,
        pc.mother_tank_id::text as mother_tank_id,
        cm.label                 as mother_tank,
        pc.father_tank_id::text as father_tank_id,
        cf.label                 as father_tank,
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

# Select rows to print (keep cross_id so we can create clutches too)
rv = df_rundate.copy()
rv.insert(0, "✓ Select", False)
col_order = [
    "✓ Select","cross_id","cross_code","clutch_code","planned_name",
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
        "cross_id":       st.column_config.TextColumn("cross_id", disabled=True),
        "cross_code":     st.column_config.TextColumn("cross_code", disabled=True),
        "clutch_code":    st.column_config.TextColumn("clutch_code", disabled=True),
        "planned_name":   st.column_config.TextColumn("planned_name", disabled=True),
        "mom_code":       st.column_config.TextColumn("mom_code", disabled=True),
        "mother_tank":    st.column_config.TextColumn("mother_tank", disabled=True),
        "mother_tank_id": st.column_config.TextColumn("mother_tank_id", disabled=True),
        "dad_code":       st.column_config.TextColumn("dad_code", disabled=True),
        "father_tank":    st.column_config.TextColumn("father_tank", disabled=True),
        "father_tank_id": st.column_config.TextColumn("father_tank_id", disabled=True),
        "cross_date":     st.column_config.TextColumn("cross_date", disabled=True),
        "note":           st.column_config.TextColumn("note"),
    },
    key="runs_for_date_editor",
)
sel_for_print = rved[rved["✓ Select"]].copy()
if sel_for_print.empty:
    st.info("Select runs above to print a report or labels.")
    st.stop()

# mom/dad genotypes for selected rows
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
    for _, rr in df_g.iterrows():
        geno_by_fish[str(rr["fish_code"])] = rr.get("genotype") or ""

# -------- report preview
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

# ----- Build PDFs (report + crossing labels)
from reportlab.pdfgen import canvas as _canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

try:
    pdfmetrics.registerFont(TTFont("LabelMono", "/Library/Fonts/SourceCodePro-Regular.ttf"))
    MONO = "LabelMono"
except Exception:
    MONO = "Courier"

def _build_report_pdf(dfrep: pd.DataFrame) -> bytes:
    buf = BytesIO()
    c = _canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    x0, y = 0.7*inch, height - 0.8*inch
    c.setFont("Helvetica-Bold", 14); c.drawString(x0, y, "Crossing Report"); y -= 0.25*inch
    c.setFont("Helvetica", 9)
    headers = ["Clutch", "Name", "Mom tank", "Dad tank", "Date", "Note"]
    colw    = [1.1*inch, 2.6*inch, 2.3*inch, 2.3*inch, 1.2*inch, 1.3*inch]
    c.setFont("Helvetica-Bold", 9); x = x0
    for h, w in zip(headers, colw): c.drawString(x, y, h); x += w
    y -= 0.18*inch; c.setFont("Helvetica", 9)
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
        for cell, w in zip(cells, colw): c.drawString(x, y, cell); x += w
        y -= 0.16*inch
    c.showPage(); c.save(); buf.seek(0); return buf.getvalue()

# Crossing tank Labels PDF (2.4 × 1.5; one field per line)
PT = 72.0; W, H = 2.4*PT, 1.5*PT
PAD_L, PAD_R, PAD_T, PAD_B = 10, 10, 8, 8
HDR_FS, DATE_FS, BODY_FS, ARROW_FS, STEP = 11.0, 9.0, 8.6, 12.0, 10.2

def _clip(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else (s[:max(0, n-1)] + "…")

def _label_pdf(rows: List[Dict[str, Any]]) -> bytes:
    buf = BytesIO(); c = _canvas.Canvas(buf, pagesize=(W, H))
    max_chars_label, max_chars_geno = 34, 60
    for t in rows:
        cross_code  = (t.get("cross_code") or "")[:12]
        cross_date  = pd.to_datetime(t.get("cross_date")).strftime("%a, %Y/%m/%d")
        mom_label   = _clip(t.get("mother_tank") or "", max_chars_label)
        dad_label   = _clip(t.get("father_tank") or "", max_chars_label)
        mom_geno    = _clip(_tgify(t.get("mom_geno") or ""), max_chars_geno)
        dad_geno    = _clip(_tgify(t.get("dad_geno") or ""), max_chars_geno)
        clutch_geno = _clip(t.get("clutch_geno") or "", max_chars_geno)

        y = H - PAD_T - HDR_FS
        c.setFont("Helvetica-Bold", HDR_FS); c.drawString(PAD_L, y, f"CROSS {cross_code}")
        y -= STEP; c.setFont("Helvetica", DATE_FS); c.drawString(PAD_L, y, cross_date)
        y -= STEP; c.setFont(MONO, BODY_FS);       c.drawString(PAD_L, y, f"Mom {mom_label}")
        y -= STEP; c.setFont("Helvetica", BODY_FS);c.drawString(PAD_L, y, mom_geno)
        y -= STEP; c.setFont(MONO, BODY_FS);       c.drawString(PAD_L, y, f"Dad {dad_label}")
        y -= STEP; c.setFont("Helvetica", BODY_FS);c.drawString(PAD_L, y, dad_geno)
        y -= STEP; c.setFont("Helvetica-Bold", ARROW_FS); c.drawCentredString(W/2.0, y+2, "↓")

        # Instance code (preferred) or fallback to plan code
        y -= STEP
        inst = (t.get("clutch_instance_code") or "").strip()
        fallback = (t.get("clutch_code") or "").strip()
        c.setFont("Helvetica", BODY_FS); c.drawString(PAD_L, y, inst if inst else fallback)

        y -= STEP; c.setFont("Helvetica", BODY_FS); c.drawString(PAD_L, y, clutch_geno)
        c.showPage()
    c.save(); buf.seek(0); return buf.getvalue()

# assemble crossing label rows (ensure clutch instance; print its code)
label_rows = []
user_name = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"

def _ensure_cross_for_planned(planned_cross_id: str, created_by: str) -> str:
    # returns crosses.id_uuid (text); used by _ensure_clutch_for_planned
    sql_load = text("""
      select mom_code, dad_code, cross_date
      from public.planned_crosses
      where id_uuid = cast(:pid as uuid) limit 1
    """)
    with ENGINE.begin() as cx:
        row = cx.execute(sql_load, {"pid": planned_cross_id}).mappings().first()
    if not row:
        raise RuntimeError(f"planned_cross not found: {planned_cross_id}")
    mom_code, dad_code = row["mom_code"], row["dad_code"]
    planned_for = pd.to_datetime(row["cross_date"]).date() if row["cross_date"] else None
    with ENGINE.begin() as cx:
        found = cx.execute(text("""
          select id_uuid::text from public.crosses
          where mother_code=:m and father_code=:f and planned_for is not distinct from :d
          order by created_at desc limit 1
        """), {"m": mom_code, "f": dad_code, "d": planned_for}).scalar()
    if found: return str(found)
    with ENGINE.begin() as cx:
        return cx.execute(text("""
          insert into public.crosses (mother_code, father_code, planned_for, created_by)
          values (:m,:f,:d,:by) returning id_uuid::text
        """), {"m": mom_code, "f": dad_code, "d": planned_for, "by": created_by}).scalar()

def _ensure_clutch_for_planned(planned_cross_id: str, date_birth: date, created_by: str) -> dict:
    # requires clutches(planned_cross_id uuid, cross_id uuid, date_birth date)
    if not _table_has_columns("clutches","planned_cross_id","cross_id","date_birth"):
        raise RuntimeError("public.clutches requires planned_cross_id, cross_id, date_birth.")
    cross_fk = _ensure_cross_for_planned(planned_cross_id, created_by=created_by)
    with ENGINE.begin() as cx:
        cid = cx.execute(text("""
          select id_uuid::text from public.clutches
          where planned_cross_id = cast(:pid as uuid) and date_birth = :bd
          limit 1
        """), {"pid": planned_cross_id, "bd": pd.to_datetime(date_birth).date()}).scalar()
    if not cid:
        with ENGINE.begin() as cx:
            cid = cx.execute(text("""
              insert into public.clutches (planned_cross_id, cross_id, date_birth, created_by)
              values (cast(:pid as uuid), cast(:cid as uuid), :bd, :by)
              returning id_uuid::text
            """), {"pid": planned_cross_id, "cid": cross_fk,
                   "bd": pd.to_datetime(date_birth).date(), "by": created_by}).scalar()
    # nice, short instance code for labels
    yy = f"{date_birth.year%100:02d}"
    clutch_instance_code = f"CLUTCH-{yy}{cid[:4].upper()}"
    return {"id": cid, "code": clutch_instance_code}

label_rows = []
for _, r in sel_for_print.iterrows():
    cross_dt = pd.to_datetime(r.get("cross_date")).date() if r.get("cross_date") else pd.Timestamp.today().date()
    planned_id = str(r.get("cross_id") or "")  # required for ensure()
    # ensure/create the clutch instance for this run/date
    try:
        ensured = _ensure_clutch_for_planned(planned_id, cross_dt, created_by=user_name)
        clutch_instance_code = ensured["code"]  # ← THIS is what we’ll print on the crossing label
    except Exception as e:
        # if anything fails, fall back to plan code (still prints something)
        clutch_instance_code = str(r.get("clutch_code") or "")

    clutch_geno = _clutch_geno_from_planned_name(str(r.get("planned_name") or ""))
    label_rows.append({
        "cross_code":    str(r.get("cross_code") or "")[:12],
        "cross_date":    cross_dt,
        "mother_tank":   str(r.get("mother_tank") or ""),
        "father_tank":   str(r.get("father_tank") or ""),
        "mom_geno":      geno_by_fish.get(str(r.get("mom_code") or ""), ""),
        "dad_geno":      geno_by_fish.get(str(r.get("dad_code") or ""), ""),
        "clutch_instance_code": clutch_instance_code,   # ← NEW field
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

# ---------------- Ensure clutch instances + paired labels (optional) ----------------
st.subheader("Create clutches + Petri dish labels (optional)")
st.caption("Creates one clutch per selected cross (date = report date), prints Petri labels, and pairs codes.")

def _ensure_cross_for_planned(planned_cross_id: str, created_by: str) -> str:
    sql_load = text("""
      select mom_code, dad_code, cross_date
      from public.planned_crosses
      where id_uuid = cast(:pid as uuid) limit 1
    """)
    with ENGINE.begin() as cx:
        row = cx.execute(sql_load, {"pid": planned_cross_id}).mappings().first()
    if not row: raise RuntimeError(f"planned_cross not found: {planned_cross_id}")
    mom_code, dad_code = row["mom_code"], row["dad_code"]
    planned_for = pd.to_datetime(row["cross_date"]).date() if row["cross_date"] else None
    with ENGINE.begin() as cx:
        found = cx.execute(text("""
          select id_uuid::text from public.crosses
          where mother_code=:m and father_code=:f and planned_for is not distinct from :d
          order by created_at desc limit 1
        """), {"m": mom_code, "f": dad_code, "d": planned_for}).scalar()
    if found: return str(found)
    with ENGINE.begin() as cx:
        return cx.execute(text("""
          insert into public.crosses (mother_code, father_code, planned_for, created_by)
          values (:m,:f,:d,:by) returning id_uuid::text
        """), {"m": mom_code, "f": dad_code, "d": planned_for, "by": (os.environ.get("USER") or "unknown")}).scalar()

def _ensure_clutch_for_planned(planned_cross_id: str, date_birth: date, created_by: str) -> dict:
    # requires clutches(planned_cross_id uuid, cross_id uuid, date_birth date)
    if not _table_has_columns("clutches","planned_cross_id","cross_id","date_birth"):
        raise RuntimeError("public.clutches requires planned_cross_id, cross_id, date_birth.")
    cross_fk = _ensure_cross_for_planned(planned_cross_id, created_by=created_by)
    with ENGINE.begin() as cx:
        cid = cx.execute(text("""
          select id_uuid::text from public.clutches
          where planned_cross_id = cast(:pid as uuid) and date_birth = :bd limit 1
        """), {"pid": planned_cross_id, "bd": pd.to_datetime(date_birth).date()}).scalar()
    if not cid:
        with ENGINE.begin() as cx:
            cid = cx.execute(text("""
              insert into public.clutches (planned_cross_id, cross_id, date_birth, created_by)
              values (cast(:pid as uuid), cast(:cid as uuid), :bd, :by)
              returning id_uuid::text
            """), {"pid": planned_cross_id, "cid": cross_fk,
                   "bd": pd.to_datetime(date_birth).date(), "by": created_by}).scalar()
    # clutch code based on id + date
    yy = f"{date_birth.year%100:02d}"; code = f"CLUTCH-{yy}{cid[:4].upper()}"
    return {"id": cid, "cross_id": cross_fk, "clutch_code": code}

def _render_petri_labels_pdf(label_rows: list[dict]) -> bytes:
    """
    Petri labels 2.4in x 0.75in, one field per line (NO 'CROSS …' line):
      1: <clutch_code>                  (bold)
      2: <nickname/title>               (bold, slightly smaller)
      3: <mom × dad>
      4: <birthday>                     (YYYY-MM-DD)
      5: <genotype>                     (summarized/ellipsized)
      6: <treatments • user>            (optional, summarized)  [we pass '' for now]
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import inch
    from reportlab.pdfbase.pdfmetrics import stringWidth
    import io

    # Geometry and typography tuned to ALWAYS fit 6 lines on 0.75"
    W, H = 2.4 * inch, 0.75 * inch
    PAD_L, PAD_R, PAD_T = 6, 6, 4
    MAXW = W - PAD_L - PAD_R

    FS1 = 8.4   # line 1: clutch_code (smaller than before)
    FS2 = 7.6   # line 2: title (smaller)
    FS_B = 6.9  # lines 3–6 (body)
    STEP = 7.2  # vertical step

    def _fit(s: str, font: str, size: float, maxw: float) -> str:
        s = (s or "").strip()
        if not s or stringWidth(s, font, size) <= maxw:
            return s
        ell = "…"; lo, hi = 0, len(s)
        while lo < hi:
            mid = (lo + hi) // 2
            if stringWidth(s[:mid] + ell, font, size) <= maxw:
                lo = mid + 1
            else:
                hi = mid
        cut = max(0, lo - 1)
        return (s[:cut] + ell) if cut > 0 else ell

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))

    for r in label_rows:
        clutch_code = str(r.get("clutch_code") or "")
        title       = str(r.get("title") or r.get("nickname") or "")
        parents     = (str(r.get("mom") or "") + " × " + str(r.get("dad") or "")).strip(" ×")
        birthday    = str(r.get("birthday") or "")
        genotype    = str(r.get("genotype") or "")
        tail        = str(r.get("tail") or "")  # keep if you later add treatments/user

        y = H - PAD_T - FS1

        # 1) clutch_code
        c.setFont("Helvetica-Bold", FS1)
        c.drawString(PAD_L, y, _fit(clutch_code, "Helvetica-Bold", FS1, MAXW))

        # 2) title
        y -= STEP
        c.setFont("Helvetica-Bold", FS2)
        c.drawString(PAD_L, y, _fit(title, "Helvetica-Bold", FS2, MAXW))

        # 3) parents
        y -= STEP
        c.setFont("Helvetica", FS_B)
        c.drawString(PAD_L, y, _fit(parents, "Helvetica", FS_B, MAXW))

        # 4) birthday
        y -= STEP
        c.drawString(PAD_L, y, _fit(birthday, "Helvetica", FS_B, MAXW))

        # 5) genotype
        y -= STEP
        c.drawString(PAD_L, y, _fit(genotype, "Helvetica", FS_B, MAXW))

        # 6) tail (optional)
        y -= STEP
        c.drawString(PAD_L, y, _fit(tail, "Helvetica", FS_B, MAXW))

        c.showPage()

    c.save(); buf.seek(0)
    return buf.getvalue()

user_name = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
if st.button("➕ Create clutches + ⬇️ Petri labels (PDF)", type="primary", use_container_width=True):
    if sel_for_print.empty:
        st.warning("Select at least one run above.")
    else:
        petri_rows=[]
        for _, r in sel_for_print.iterrows():
            planned_id = str(r.get("cross_id") or "")
            if not planned_id: 
                continue
            bd = pd.to_datetime(r["cross_date"]).date()
            try:
                ensured = _ensure_clutch_for_planned(planned_id, bd, created_by=user_name)
            except Exception as e:
                st.error(f"Ensure clutch failed: {e}")
                continue

            # Build 6-line payload: NO CROSS line here
            petri_rows.append({
                "clutch_code": ensured["clutch_code"],
                "title":       str(r.get("planned_name") or ""),
                "mom":         str(r.get("mom_code") or ""),
                "dad":         str(r.get("dad_code") or ""),
                "birthday":    bd.strftime("%Y-%m-%d"),
                "genotype":    _clutch_geno_from_planned_name(str(r.get("planned_name") or "")),
                "tail":        "",  # keep for future "treatments • user"
            })

        if petri_rows:
            try:
                petri_pdf = _render_petri_labels_pdf(petri_rows)
                st.download_button("⬇️ Petri labels (PDF)", data=petri_pdf,
                                   file_name=f"petri_labels_{report_date}.pdf",
                                   mime="application/pdf", use_container_width=True)
                st.success(f"Created {len(petri_rows)} clutch record(s).")
            except Exception as e:
                st.error(f"Render Petri labels failed: {e}")
        if petri_rows:
            try:
                petri_pdf = _render_petri_labels_pdf(petri_rows)
                st.download_button("⬇️ Petri labels (PDF)", data=petri_pdf,
                                   file_name=f"petri_labels_{report_date}.pdf",
                                   mime="application/pdf", use_container_width=True)
                st.success(f"Created {len(petri_rows)} clutch record(s).")
            except Exception as e:
                st.error(f"Render Petri labels failed: {e}")