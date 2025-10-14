from __future__ import annotations
from supabase.ui.auth_gate import require_auth
sb, session, user = require_auth()

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import os
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# =======================
# Page config
# =======================
st.set_page_config(page_title="🐟 Deploy crosses", page_icon="🐟", layout="wide")
st.title("🐟 Deploy crosses — select concepts → preview instance(s) → schedule")

# 🔒 optional gate
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

# =======================
# DB
# =======================
_ENGINE = None
def _get_engine():
    global _ENGINE
    if _ENGINE:
        return _ENGINE
    url = os.getenv("DB_URL")
    if not url:
        st.stop()
    _ENGINE = create_engine(url, future=True)
    return _ENGINE

LIVE_STATUSES = ("active", "new_tank")
TANK_TYPES    = ("inventory_tank","holding_tank","nursery_tank")

# =======================
# PDF helpers (letter report)
# =======================
def _has_column(schema: str, table: str, column: str) -> bool:
    with _get_engine().begin() as cx:
        return bool(pd.read_sql(
            text("""
              select 1
              from information_schema.columns
              where table_schema=:s and table_name=:t and column_name=:c
              limit 1
            """),
            cx, params={"s": schema, "t": table, "c": column}
        ).shape[0])

def _pdf_bytes_reportlab(title: str, lines: List[str]) -> Optional[bytes]:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
    except Exception:
        return None
    import io
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    W, H = letter
    x, y = 18*mm, H - 18*mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y, title)
    y -= 8*mm
    c.setFont("Helvetica", 11)
    for ln in lines:
        if y < 18*mm:
            c.showPage(); y = H - 18*mm; c.setFont("Helvetica", 11)
        c.drawString(x, y, ln); y -= 6*mm
    c.save()
    return buf.getvalue()

def _pdf_bytes_minimal(title: str, lines: List[str]) -> bytes:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = ["BT", "/F1 12 Tf", "72 770 Td", "1 -1 scale", f"( {esc(title)} ) Tj", "T*"]
    for ln in lines:
        content.append(f"( {esc(ln)} ) Tj"); content.append("T*")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", "replace")

    objs = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")

    out = bytearray()
    out.extend(b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n")
    offs = []
    for i, body in enumerate(objs, start=1):
        offs.append(len(out))
        out.extend(f"{i} 0 obj\n".encode()); out.extend(body); out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(b"xref\n"); out.extend(f"0 {len(objs)+1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for o in offs: out.extend(f"{o:010d} 00000 n \n".encode())
    out.extend(b"trailer\n"); out.extend(f"<< /Size {len(objs)+1} /Root 1 0 R >>\n".encode())
    out.extend(b"startxref\n"); out.extend(f"{xref}\n".encode()); out.extend(b"%%EOF\n")
    return bytes(out)

def _make_pdf(title: str, lines: List[str]) -> bytes:
    pdf = _pdf_bytes_reportlab(title, lines)
    return pdf if pdf is not None else _pdf_bytes_minimal(title, lines)

# =======================
# Label layout (exact sizes + fit/ellipsis)
# =======================
def _rl_or_none():
    try:
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase.pdfmetrics import stringWidth
        return canvas, stringWidth
    except Exception:
        return None, None

def _elide(text: str, maxw: float, font: str, size: float, stringWidth) -> str:
    if not text:
        return ""
    if stringWidth(text, font, size) <= maxw:
        return text
    ell = "…"
    if stringWidth(ell, font, size) > maxw:
        return ""
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi) // 2
        trial = text[:mid] + ell
        if stringWidth(trial, font, size) <= maxw:
            lo = mid + 1
        else:
            hi = mid
    return text[:max(0, lo - 1)] + ell

def _pdf_bytes_minimal_pages(pages: List[List[str]]) -> bytes:
    # tiny valid-PDF fallback per label (no fitting)
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    import io
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n")
    offsets = []; objs = []; catalog_id, pages_id, font_id = 1000, 1001, 1002
    base = 2000; kids = []
    W, H = 173, 72  # ~2.4x1.0
    for i, page in enumerate(pages):
        content = ["BT", "/F1 10 Tf", "6 60 Td"]
        if page:
            content.append(f"( {esc(page[0])} ) Tj")
        content.append("/F1 7 Tf")
        for ln in page[1:]:
            content.append("T*"); content.append(f"( {esc(ln[:120])} ) Tj")
        content.append("ET")
        stream = "\n".join(content).encode("latin-1", "replace")
        cid = base + i*2 + 1; pid = base + i*2 + 2
        kids.append(pid)
        objs.append((cid, b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"))
        objs.append((pid, f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {W} {H}] "
                          f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {cid} 0 R >>"
                          .encode()))
    offsets.append(out.tell()); out.write(f"{catalog_id} 0 obj\n".encode())
    out.write(f"<< /Type /Catalog /Pages {pages_id} 0 R >>\nendobj\n".encode())
    offsets.append(out.tell()); out.write(f"{font_id} 0 obj\n".encode())
    out.write(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    for obj_id, body in objs:
        offsets.append(out.tell()); out.write(f"{obj_id} 0 obj\n".encode()); out.write(body); out.write(b"\nendobj\n")
    offsets.append(out.tell()); out.write(f"{pages_id} 0 obj\n".encode())
    kids_list = " ".join(f"{k} 0 R" for k in kids)
    out.write(f"<< /Type /Pages /Kids [ {kids_list} ] /Count {len(kids)} >>\nendobj\n".encode())
    xref = len(out); out.write(b"xref\n"); out.write(f"0 {len(offsets)+1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets: out.write(f"{off:010d} 00000 n \n".encode())
    out.write(b"trailer\n"); out.write(f"<< /Size {len(offsets)+1} /Root 1000 0 R >>\n".encode())
    out.write(b"startxref\n"); out.write(f"{xref}\n".encode()); out.write(b"%%EOF\n")
    return out.getvalue()

def _labels_pdf_pages(pages: List[List[str]], width_in: float, height_in: float,
                      header_pt: float, body_pt: float, leading_pt: float,
                      margin_pt: float = 6.0, line_limit: int | None = None) -> bytes:
    canvas, stringWidth = _rl_or_none()
    if canvas is None:
        return _pdf_bytes_minimal_pages(pages)

    import io
    W = width_in * 72.0
    H = height_in * 72.0
    maxw = W - 2 * margin_pt

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))

    for lines in pages:
        x = margin_pt
        y = H - margin_pt

        # header
        if lines:
            c.setFont("Helvetica-Bold", header_pt)
            hdr = _elide(lines[0], maxw, "Helvetica-Bold", header_pt, stringWidth)
            y -= header_pt * 0.85
            c.drawString(x, y, hdr)

        # body
        c.setFont("Helvetica", body_pt)
        rendered = 0
        for ln in lines[1:]:
            if line_limit is not None and rendered >= line_limit:
                break
            y -= leading_pt
            if y < margin_pt + body_pt:
                break
            ln_fit = _elide(ln, maxw, "Helvetica", body_pt, stringWidth)
            c.drawString(x, y, ln_fit)
            rendered += 1

        c.showPage()

    c.save()
    return buf.getvalue()

def _make_label_pdf(pages: List[List[str]], width_in: float, height_in: float,
                    header_pt: float, body_pt: float, leading_pt: float) -> bytes:
    return _labels_pdf_pages(pages, width_in, height_in, header_pt, body_pt, leading_pt)

# ---- Label text builders (compact to fit small labels) ----
def _strip_tank_prefix(s: str | None) -> str:
    s = (s or "").strip()
    if s.upper().startswith("TANK "):
        return s[5:]
    return s

def _build_crossing_label_pages(df: pd.DataFrame) -> List[List[str]]:
    """
    Need: cross_code, cross_date, mother_tank_label, father_tank_label,
          clutch_instance_code, clutch_name
    """
    pages: List[List[str]] = []
    for r in df.itertuples(index=False):
        cross_code = getattr(r, "cross_code", "") or ""
        cross_date = getattr(r, "cross_date", None)
        dt_text    = cross_date.strftime("%a %Y-%m-%d") if cross_date else ""
        mom_tank   = _strip_tank_prefix(getattr(r, "mother_tank_label", "") or getattr(r, "mother_tank_code", ""))
        dad_tank   = _strip_tank_prefix(getattr(r, "father_tank_label", "") or getattr(r, "father_tank_code", ""))
        clutch_inst = getattr(r, "clutch_instance_code", "") or ""
        clutch_name = getattr(r, "clutch_name", "") or ""
        pages.append([
            f"CROSS {cross_code}",    # header
            dt_text,
            f"M: {mom_tank}",
            f"D: {dad_tank}",
            "↓",
            f"{clutch_inst}",
            f"{clutch_name}",         # clutch name last
        ])
    return pages

def _build_petri_label_pages(df: pd.DataFrame) -> List[List[str]]:
    """
    Need: clutch_instance_code, clutch_name, mom_code, dad_code, date_birth
    """
    pages: List[List[str]] = []
    for r in df.itertuples(index=False):
        clutch_inst = getattr(r, "clutch_instance_code", "") or ""
        clutch_name = getattr(r, "clutch_name", "") or ""
        mom_code = getattr(r, "mom_code", "") or ""
        dad_code = getattr(r, "dad_code", "") or ""
        dob = getattr(r, "date_birth", None)
        dob_text = dob.strftime("%Y-%m-%d") if dob else "DOB TBD"
        pages.append([
            f"{clutch_inst}",        # header (bigger)
            f"{clutch_name}",
            f"{mom_code} × {dad_code}",
            f"{dob_text}",
        ])
    return pages

# =======================
# Load runnable concepts
# =======================
def _load_runnable_concepts(d1: date, d2: date, created_by: str, q: str) -> pd.DataFrame:
    """
    Concepts (vw_crosses_concept) whose mom & dad both have at least one live tank.
    Also surfaces a latest planned_cross (with tanks if possible) to show tank/plan fields.
    """
    sql = text("""
    WITH live_by_fish AS (
      SELECT f.fish_code, COUNT(*)::int AS n_live
      FROM public.fish f
      JOIN public.fish_tank_memberships m ON m.fish_id = f.id AND m.left_at IS NULL
      JOIN public.containers c           ON c.id_uuid = m.container_id
      WHERE c.status = ANY(:live_statuses) AND c.container_type = ANY(:tank_types)
      GROUP BY f.fish_code
    ),
    pc_with_tanks AS (
      SELECT
        x.id_uuid            AS cross_id,
        pc.id_uuid           AS planned_cross_id,
        pc.clutch_id         AS clutch_plan_id,
        pc.mother_tank_id, pc.father_tank_id,
        ROW_NUMBER() OVER (
          PARTITION BY x.id_uuid
          ORDER BY COALESCE(pc.cross_date::timestamp, pc.created_at) DESC NULLS LAST
        ) AS rn
      FROM public.crosses x
      LEFT JOIN public.planned_crosses pc
        ON pc.cross_id = x.id_uuid
       AND pc.mother_tank_id IS NOT NULL
       AND pc.father_tank_id IS NOT NULL
    ),
    picked_pc AS ( SELECT * FROM pc_with_tanks WHERE rn = 1 ),
    fallback_pc AS (
      SELECT
        x.id_uuid            AS cross_id,
        pc.id_uuid           AS planned_cross_id,
        pc.clutch_id         AS clutch_plan_id,
        pc.mother_tank_id, pc.father_tank_id,
        ROW_NUMBER() OVER (
          PARTITION BY x.id_uuid
          ORDER BY COALESCE(pc.cross_date::timestamp, pc.created_at) DESC NULLS LAST
        ) AS rn
      FROM public.crosses x
      LEFT JOIN public.planned_crosses pc ON pc.cross_id = x.id_uuid
    ),
    picked_any AS ( SELECT * FROM fallback_pc WHERE rn = 1 ),
    picked AS (
      SELECT cross_id, planned_cross_id, clutch_plan_id, mother_tank_id, father_tank_id
      FROM picked_pc
      UNION ALL
      SELECT fa.cross_id, fa.planned_cross_id, fa.clutch_plan_id, fa.mother_tank_id, fa.father_tank_id
      FROM picked_any fa
      WHERE NOT EXISTS (SELECT 1 FROM picked_pc pp WHERE pp.cross_id = fa.cross_id)
    )
    SELECT
      v.cross_code,
      x.cross_name, x.cross_nickname,

      v.mom_code, COALESCE(cm.label, cm.tank_code) AS mom_tank,
      v.dad_code, COALESCE(cf.label, cf.tank_code) AS dad_tank,

      cp.clutch_code, cp.planned_name AS clutch_name, cp.planned_nickname AS clutch_nickname,

      v.n_runs AS n_cross_instances,
      v.latest_cross_date AS latest,
      v.created_by, v.created_at,

      COALESCE(lm.n_live,0) AS mom_live,
      COALESCE(ld.n_live,0) AS dad_live,
      v.n_clutches AS clutches,
      v.n_containers AS containers
    FROM public.vw_crosses_concept v
    JOIN public.crosses x     ON x.id_uuid = v.cross_id
    LEFT JOIN live_by_fish lm ON lm.fish_code = v.mom_code
    LEFT JOIN live_by_fish ld ON ld.fish_code = v.dad_code
    LEFT JOIN picked p        ON p.cross_id   = v.cross_id
    LEFT JOIN public.clutch_plans cp ON cp.id_uuid = p.clutch_plan_id
    LEFT JOIN public.containers  cm ON cm.id_uuid = p.mother_tank_id
    LEFT JOIN public.containers  cf ON cf.id_uuid = p.father_tank_id
    WHERE (lm.n_live > 0 AND ld.n_live > 0)
      AND (v.created_at::date BETWEEN :d1 AND :d2 OR v.latest_cross_date BETWEEN :d1 AND :d2)
      AND (:by = '' OR v.created_by ILIKE :byl)
      AND (
        :q = '' OR
        v.cross_code ILIKE :ql OR x.cross_name ILIKE :ql OR x.cross_nickname ILIKE :ql OR
        v.mom_code  ILIKE :ql OR v.dad_code  ILIKE :ql OR
        COALESCE(cm.label, cm.tank_code, '') ILIKE :ql OR
        COALESCE(cf.label, cf.tank_code, '') ILIKE :ql OR
        COALESCE(cp.clutch_code,'') ILIKE :ql OR COALESCE(cp.planned_name,'') ILIKE :ql OR COALESCE(cp.planned_nickname,'') ILIKE :ql
      )
    ORDER BY COALESCE(v.latest_cross_date, v.created_at) DESC NULLS LAST
    """)
    params = {
        "live_statuses": list(LIVE_STATUSES),
        "tank_types":    list(TANK_TYPES),
        "d1": d1, "d2": d2,
        "by": created_by or "", "byl": f"%{created_by or ''}%",
        "q": q or "", "ql": f"%{q or ''}%",
    }
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params=params)

def _lookup_cross_id(cross_code: str) -> str:
    with _get_engine().begin() as cx:
        row = cx.execute(text("select id_uuid::text from public.crosses where cross_code = :c limit 1"),
                         {"c": cross_code}).fetchone()
    if not row:
        raise RuntimeError(f"cross_id not found for code {cross_code}")
    return row[0]

def _schedule_instance(cross_code: str, mom_code: str, dad_code: str, run_date: date, created_by: str):
    """
    Persist one cross_instance + clutch + petri container for the given concept and date.
    Returns (cross_instance_id, cross_run_code, clutch_id)
    """
    cross_id = _lookup_cross_id(cross_code)
    with _get_engine().begin() as cx:
        # 1) cross_instance (run)
        ci_id, ci_code = cx.execute(
            text("""insert into public.cross_instances (cross_id, cross_date, note, created_by)
                    values (:cross_id, :d, :note, :by)
                    returning id_uuid::text, cross_run_code"""),
            {"cross_id": cross_id, "d": run_date, "note": None, "by": created_by},
        ).one()

        # 2) clutch — DOB is **run_date + 1 day**
        dob = run_date + timedelta(days=1)
        clutch_id = cx.execute(
            text("""insert into public.clutches (cross_id, cross_instance_id, date_birth, created_by)
                    values (:cross_id, :ci, :dob, :by)
                    returning id_uuid::text"""),
            {"cross_id": cross_id, "ci": ci_id, "dob": dob, "by": created_by},
        ).scalar()

        # 3) petri container → clutch_container
        petri_label = f"PETRI {cross_code} • {dob:%Y-%m-%d}"
        container_id = cx.execute(
            text("""insert into public.containers (container_type, status, label, created_by)
                    values ('petri_dish', 'new_tank', :label, :by)
                    returning id_uuid::text"""),
            {"label": petri_label, "by": created_by},
        ).scalar()

        cx.execute(
            text("""insert into public.clutch_containers (container_id, clutch_id, created_by)
                    values (:cid, :cl, :by)"""),
            {"cid": container_id, "cl": clutch_id, "by": created_by},
        )
    return ci_id, ci_code, clutch_id

# =======================
# Labels data (uses clutch_instance_code)
# =======================
def _fetch_labels_for_instances(inst_codes: List[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Return two DataFrames for labels:
      df_crossing: cross_code, cross_date, mother_tank_label, father_tank_label,
                   mother_tank_code, father_tank_code, clutch_instance_code, clutch_name
      df_petri:    clutch_instance_code, clutch_name, mom_code, dad_code, date_birth, cross_date
    Falls back to short clutch UUID if clutch_instance_code column doesn't exist.
    """
    if not inst_codes:
        return pd.DataFrame(), pd.DataFrame()

    use_ci_code = _has_column("public", "clutches", "clutch_instance_code")
    clutch_code_expr = "cl.clutch_instance_code" if use_ci_code else "left(cl.id_uuid::text, 8)"

    sql = text(f"""
      with x as (
        select
          ci.cross_run_code,
          ci.cross_date,
          x.cross_code,
          x.mother_code as mom_code,
          x.father_code as dad_code,
          pc.mother_tank_id, pc.father_tank_id,
          cp.planned_name as clutch_name,
          {clutch_code_expr} as clutch_instance_code,
          cl.date_birth
        from public.cross_instances ci
        join public.crosses x  on x.id_uuid = ci.cross_id
        left join public.planned_crosses pc on pc.cross_id = x.id_uuid
        left join public.clutch_plans   cp on cp.id_uuid = pc.clutch_id
        left join public.clutches       cl on cl.cross_instance_id = ci.id_uuid
        where ci.cross_run_code = any(:codes)
      )
      select
        x.cross_run_code,
        x.cross_code,
        x.cross_date,
        x.clutch_name,
        x.clutch_instance_code,
        x.date_birth,
        x.mom_code, x.dad_code,
        cm.label as mother_tank_label,
        cf.label as father_tank_label,
        cm.tank_code as mother_tank_code,
        cf.tank_code as father_tank_code
      from x
      left join public.containers cm on cm.id_uuid = x.mother_tank_id
      left join public.containers cf on cf.id_uuid = x.father_tank_id
      order by x.cross_date, x.cross_run_code
    """)

    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": inst_codes})

    df_crossing = df[[
        "cross_code","cross_date",
        "mother_tank_label","father_tank_label","mother_tank_code","father_tank_code",
        "clutch_instance_code","clutch_name"
    ]].copy()

    df_petri = df[[
        "clutch_instance_code","clutch_name","mom_code","dad_code","date_birth","cross_date"
    ]].copy()

    # prefer label; fallback to code
    df_crossing["mother_tank_label"] = df_crossing["mother_tank_label"].fillna(df_crossing["mother_tank_code"])
    df_crossing["father_tank_label"] = df_crossing["father_tank_label"].fillna(df_crossing["father_tank_code"])
    # (optional) expose print date if you want to reuse it
    # df_petri["date_to_print"] = df_petri["date_birth"].fillna(df_petri["cross_date"])

    return df_crossing, df_petri

# =======================
# Filters + overview table
# =======================
with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1, c2, c3, c4 = st.columns([1,1,1,3])
    with c1:
        start = st.date_input("From", value=today - timedelta(days=14))
    with c2:
        end   = st.date_input("To", value=today)
    with c3:
        created_by = st.text_input("Created by", value=os.environ.get("USER") or os.environ.get("USERNAME") or "")
    with c4:
        q = st.text_input("Omni-search (code / mom / dad / plan)", value="")
    st.form_submit_button("Apply", use_container_width=True)

df = _load_runnable_concepts(start, end, created_by, q)
st.caption(f"{len(df)} runnable cross concept(s) (both parents have live tanks)")

# Overview with selection (rich columns)
desired = [
    "cross_code","cross_name","cross_nickname",
    "mom_code","mom_tank","dad_code","dad_tank",
    "clutch_code","clutch_name","clutch_nickname",
    "n_cross_instances","latest","created_by","created_at",
    "mom_live","dad_live","clutches","containers",
]
overview = df[[c for c in desired if c in df.columns]].copy()
overview.insert(0, "✓ Select", False)

table_key = f"ov_{start.isoformat()}_{end.isoformat()}_{created_by}_{q}"
store_key = f"{table_key}__store"
current_codes = overview["cross_code"].astype(str).tolist()
if store_key not in st.session_state or set(st.session_state[store_key].get("codes", [])) != set(current_codes):
    st.session_state[store_key] = {"df": overview.copy(), "codes": current_codes}

edited = st.data_editor(
    st.session_state[store_key]["df"],
    hide_index=True, use_container_width=True,
    column_order=["✓ Select"] + desired,
    column_config={
        "✓ Select":        st.column_config.CheckboxColumn("✓", default=False),
        "cross_code":      st.column_config.TextColumn("cross", disabled=True),
        "cross_name":      st.column_config.TextColumn("cross name", disabled=True, width="large"),
        "cross_nickname":  st.column_config.TextColumn("nickname", disabled=True),
        "mom_code":        st.column_config.TextColumn("mom", disabled=True),
        "mom_tank":        st.column_config.TextColumn("mom tank", disabled=True),
        "dad_code":        st.column_config.TextColumn("dad", disabled=True),
        "dad_tank":        st.column_config.TextColumn("dad tank", disabled=True),
        "clutch_code":     st.column_config.TextColumn("clutch code", disabled=True),
        "clutch_name":     st.column_config.TextColumn("clutch name", disabled=True),
        "clutch_nickname": st.column_config.TextColumn("clutch nickname", disabled=True),
        "n_cross_instances": st.column_config.NumberColumn("#runs", disabled=True, width="small"),
        "latest":          st.column_config.DateColumn("latest", disabled=True),
        "created_by":      st.column_config.TextColumn("created_by", disabled=True),
        "created_at":      st.column_config.DatetimeColumn("created_at", disabled=True),
        "mom_live":        st.column_config.NumberColumn("mom live", disabled=True, width="small"),
        "dad_live":        st.column_config.NumberColumn("dad live", disabled=True, width="small"),
        "clutches":        st.column_config.NumberColumn("clutches", disabled=True, width="small"),
        "containers":      st.column_config.NumberColumn("containers", disabled=True, width="small"),
    },
    key=table_key,
)
st.session_state[store_key]["df"] = edited.copy()

sel_mask = edited.get("✓ Select", pd.Series(False, index=edited.index)).fillna(False).astype(bool)
selected = edited.loc[sel_mask, ["cross_code","mom_code","dad_code"]].reset_index(drop=True)

# =======================
# 2–3) Preview instances + date selector
# =======================
st.subheader("Preview: cross instance(s)")
if selected.empty:
    st.info("Select crosses above to create preview instance(s).")
    preview_df = pd.DataFrame(columns=["cross_code","date","mom_code","dad_code"])
else:
    default_date = date.today()
    run_date = st.date_input("Instance date (applies to all selected)", value=default_date, key="inst_date")
    preview_df = selected.copy()
    preview_df.insert(1, "date", run_date.isoformat())

st.dataframe(preview_df, use_container_width=True, hide_index=True)
st.caption(f"{len(preview_df)} instance(s) in preview")

# =======================
# 4) Schedule (persist instances)
# =======================
st.subheader("Schedule")
if "last_scheduled_runs" not in st.session_state:
    st.session_state["last_scheduled_runs"] = []

creator = os.environ.get("USER") or os.environ.get("USERNAME") or "system"
if st.button("➕ Save scheduled cross instance(s)", type="primary", use_container_width=True, disabled=selected.empty):
    created = 0; errors: List[str] = []; new_run_codes: List[str] = []
    for _, r in preview_df.iterrows():
        try:
            ci_id, ci_code, clutch_id = _schedule_instance(
                cross_code=r["cross_code"],
                mom_code=r["mom_code"],
                dad_code=r["dad_code"],
                run_date=date.fromisoformat(r["date"]),
                created_by=creator,
            )
            created += 1; new_run_codes.append(ci_code)
        except Exception as e:
            errors.append(f"{r['cross_code']}: {e}")
    if created:
        st.session_state["last_scheduled_runs"].extend(new_run_codes)
        st.success(f"Scheduled {created} cross instance(s). Re-apply filters to refresh.")
    if errors:
        st.error("Some instances failed:\n- " + "\n- ".join(errors))

# =======================
# 5) Downloads (scheduled instances) — label PDFs that FIT
# =======================
st.subheader("Downloads (scheduled instances)")
sched_codes = st.session_state.get("last_scheduled_runs", [])

# Report from preview selection
report_lines = [f"{r.cross_code} | {r.mom_code} × {r.dad_code} | date {r.date}" for r in preview_df.itertuples(index=False)]

# Build label pages from scheduled instances
df_crossing, df_petri = _fetch_labels_for_instances(sched_codes) if sched_codes else (pd.DataFrame(), pd.DataFrame())

cross_pdf = _make_label_pdf(
    pages=_build_crossing_label_pages(df_crossing),
    width_in=2.4, height_in=1.0,
    header_pt=9.2, body_pt=7.0, leading_pt=7.2
) if not df_crossing.empty else b""

petri_pdf = _make_label_pdf(
    pages=_build_petri_label_pages(df_petri),
    width_in=2.4, height_in=0.75,
    header_pt=10.5, body_pt=7.0, leading_pt=7.1
) if not df_petri.empty else b""

c1, c2, c3 = st.columns(3)
with c1:
    st.download_button(
        "📄 Crossing report (PDF)",
        data=_make_pdf("Crossing report", report_lines),
        file_name=f"crossing_report_{start:%Y%m%d}_{end:%Y%m%d}.pdf",
        mime="application/pdf",
        key=f"dl_report_{start:%Y%m%d}_{end:%Y%m%d}"
    )
with c2:
    st.download_button(
        "🏷️ Crossing tank labels (2.4\"×1.0\")",
        data=cross_pdf,
        file_name=f"crossing_tank_labels_{start:%Y%m%d}_{end:%Y%m%d}.pdf",
        mime="application/pdf",
        key=f"dl_tank_{start:%Y%m%d}_{end:%Y%m%d}",
        disabled=(not cross_pdf)
    )
with c3:
    st.download_button(
        "⬇️ Petri dish labels (2.4\"×0.75\")",
        data=petri_pdf,
        file_name=f"petri_labels_{start:%Y%m%d}_{end:%Y%m%d}.pdf",
        mime="application/pdf",
        key=f"dl_petri_{start:%Y%m%d}_{end:%Y%m%d}",
        disabled=(not petri_pdf)
    )
