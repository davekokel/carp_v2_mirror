from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from carp_app.ui.auth_gate import require_auth
from carp_app.lib.config import engine as get_engine, DB_URL
sb, session, user = require_auth()

from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

from pathlib import Path
import os, tempfile, subprocess
from datetime import date, timedelta
from typing import List, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text

# ---------------- UI ----------------
st.set_page_config(page_title="🧬 Enter cross_instance → schedule", page_icon="🧬", layout="wide")
st.title("🧬 Enter cross_instance → schedule")

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

# ---------------- Engine ----------------
_ENGINE = None
def _get_engine():
    global _ENGINE
    if _ENGINE:
        return _ENGINE
    if not os.getenv("DB_URL"):
        st.error("DB_URL not set"); st.stop()
    _ENGINE = get_engine()
    return _ENGINE

LIVE_STATUSES = ("active", "new_tank")
TANK_TYPES    = ("inventory_tank","holding_tank","nursery_tank")

# ---------------- Optional shared label components ----------------
try:
    from carp_app.lib.labels_components import (
        build_crossing_label_pages as _ext_build_crossing_pages,
        build_petri_label_pages as _ext_build_petri_pages,
        make_label_pdf as _ext_make_label_pdf,
    )
except Exception:
    _ext_build_crossing_pages = _ext_build_petri_pages = _ext_make_label_pdf = None

# ---------------- Minimal PDF helpers (fallbacks) ----------------
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
    c.setFont("Helvetica-Bold", 14); c.drawString(x, y, title); y -= 8*mm
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
    for o in offs: out.extend(f"{o:010d} 00000 n \n")
    out.extend(b"trailer\n"); out.extend(f"<< /Size {len(objs)+1} /Root 1 0 R >>\n".encode())
    out.extend(b"startxref\n"); out.extend(f"{xref}\n".encode()); out.extend(b"%%EOF\n")
    return bytes(out)

def _make_pdf(title: str, lines: List[str]) -> bytes:
    pdf = _pdf_bytes_reportlab(title, lines)
    return pdf if pdf is not None else _pdf_bytes_minimal(title, lines)

def _labels_pdf_pages(pages: List[List[str]], width_in: float, height_in: float,
                      header_pt: float, body_pt: float, leading_pt: float) -> bytes:
    if _ext_make_label_pdf:
        return _ext_make_label_pdf(pages, width_in, height_in, header_pt, body_pt, leading_pt)
    # ultra-minimal fallback (one label per page)
    def esc(s:str)->str: return s.replace("\\","\\\\").replace("(","\\(").replace(")","\\)")
    import io
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n")
    offsets = []; objs = []; catalog_id, pages_id, font_id = 1000, 1001, 1002
    base = 2000; kids = []
    W, H = int(width_in*72), int(height_in*72)
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

def _build_crossing_label_pages(df: pd.DataFrame) -> List[List[str]]:
    if _ext_build_crossing_pages: return _ext_build_crossing_pages(df)
    pages: List[List[str]] = []
    for r in df.itertuples(index=False):
        dt = pd.to_datetime(getattr(r, "cross_date", None)).strftime("%a %Y-%m-%d") if getattr(r, "cross_date", None) else ""
        mom = (getattr(r, "mother_tank_label", "") or getattr(r, "mother_tank_code", "")) or ""
        dad = (getattr(r, "father_tank_label", "") or getattr(r, "father_tank_code", "")) or ""
        pages.append([f"CROSS {getattr(r,'cross_code','')}", dt, f"M: {mom}", f"D: {dad}"])
    return pages

def _build_petri_label_pages(df: pd.DataFrame) -> List[List[str]]:
    if _ext_build_petri_pages: return _ext_build_petri_pages(df)
    pages: List[List[str]] = []
    for r in df.itertuples(index=False):
        dob = getattr(r, "date_birth", None)
        dob_text = pd.to_datetime(dob).date().isoformat() if dob else "DOB TBD"
        pages.append([
            f"{getattr(r,'clutch_instance_code','')}",
            f"{getattr(r,'clutch_name','')}",
            f"{getattr(r,'mom_code','')} × {getattr(r,'dad_code','')}",
            f"{dob_text}",
        ])
    return pages

# ---------------- Printing ----------------
def _print_pdf_bytes(pdf_bytes: bytes, queue_name: str, media_opt: str) -> tuple[bool, str]:
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        cmd = ["lp", "-d", queue_name, "-o", media_opt, tmp_path]
        out = subprocess.run(cmd, capture_output=True, text=True, check=False)
        ok = (out.returncode == 0)
        msg = out.stdout.strip() or out.stderr.strip() or ("sent to " + queue_name if ok else "print failed")
        return ok, msg
    except FileNotFoundError:
        return False, "lp not found on host"
    except Exception as e:
        return False, str(e)

# ---------------- Data loaders & actions ----------------
def _load_runnable_concepts(d1: date, d2: date, created_by: str, q: str) -> pd.DataFrame:
    sql = text("""
    WITH live_by_fish AS (
      SELECT f.fish_code, COUNT(*)::int AS n_live
      FROM public.fish f
      JOIN public.fish_tank_memberships m ON m.fish_id = f.id AND m.left_at IS NULL
      JOIN public.containers c           ON c.id = m.container_id
      WHERE c.status = ANY(:live_statuses) AND c.container_type = ANY(:tank_types)
      GROUP BY f.fish_code
    ),
    pc_with_tanks AS (
      SELECT
        x.id            AS cross_id,
        pc.id           AS planned_cross_id,
        pc.clutch_id    AS clutch_plan_id,
        pc.mother_tank_id, pc.father_tank_id,
        ROW_NUMBER() OVER (
          PARTITION BY x.id
          ORDER BY COALESCE(pc.cross_date::timestamp, pc.created_at) DESC NULLS LAST
        ) AS rn
      FROM public.crosses x
      LEFT JOIN public.planned_crosses pc
        ON pc.cross_id = x.id
       AND pc.mother_tank_id IS NOT NULL
       AND pc.father_tank_id IS NOT NULL
    ),
    picked_pc AS ( SELECT * FROM pc_with_tanks WHERE rn = 1 ),
    fallback_pc AS (
      SELECT
        x.id            AS cross_id,
        pc.id           AS planned_cross_id,
        pc.clutch_id    AS clutch_plan_id,
        pc.mother_tank_id, pc.father_tank_id,
        ROW_NUMBER() OVER (
          PARTITION BY x.id
          ORDER BY COALESCE(pc.cross_date::timestamp, pc.created_at) DESC NULLS LAST
        ) AS rn
      FROM public.crosses x
      LEFT JOIN public.planned_crosses pc ON pc.cross_id = x.id
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
      COALESCE(x.cross_name_code, v.cross_code)            AS cross_name,
      COALESCE(x.cross_name_genotype, '')                  AS cross_nickname,
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
    JOIN public.crosses x     ON x.id = v.cross_id
    LEFT JOIN live_by_fish lm ON lm.fish_code = v.mom_code
    LEFT JOIN live_by_fish ld ON ld.fish_code = v.dad_code
    LEFT JOIN picked p        ON p.cross_id   = v.cross_id
    LEFT JOIN public.clutch_plans cp ON cp.id = p.clutch_plan_id
    LEFT JOIN public.containers  cm ON cm.id = p.mother_tank_id
    LEFT JOIN public.containers  cf ON cf.id = p.father_tank_id
    WHERE (lm.n_live > 0 AND ld.n_live > 0)
      AND (v.created_at::date BETWEEN :d1 AND :d2 OR v.latest_cross_date BETWEEN :d1 AND :d2)
      AND (:by = '' OR v.created_by ILIKE :byl)
      AND (
        :q = '' OR
        v.cross_code ILIKE :ql OR
        COALESCE(x.cross_name_code,'')       ILIKE :ql OR
        COALESCE(x.cross_name_genotype,'')   ILIKE :ql OR
        v.mom_code  ILIKE :ql OR v.dad_code  ILIKE :ql OR
        COALESCE(cm.label, cm.tank_code, '') ILIKE :ql OR
        COALESCE(cf.label, cf.tank_code, '') ILIKE :ql OR
        COALESCE(cp.clutch_code,'')          ILIKE :ql OR
        COALESCE(cp.planned_name,'')         ILIKE :ql OR
        COALESCE(cp.planned_nickname,'')     ILIKE :ql
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
        row = cx.execute(text("select id::text from public.crosses where cross_code = :c limit 1"),
                         {"c": cross_code}).fetchone()
    if not row:
        raise RuntimeError(f"cross_id not found for code {cross_code}")
    return row[0]

def _schedule_instance(cross_code: str, mom_code: str, dad_code: str, run_date: date, created_by: str):
    cross_id = _lookup_cross_id(cross_code)
    with _get_engine().begin() as cx:
        ci_id, ci_code = cx.execute(
            text("""insert into public.cross_instances (cross_id, cross_date, note, created_by)
                    values (:cross_id, :d, :note, :by)
                    returning id::text, cross_run_code"""),
            {"cross_id": cross_id, "d": run_date, "note": None, "by": created_by},
        ).one()

        dob = run_date + timedelta(days=1)
        clutch_id = cx.execute(
            text("""insert into public.clutches (cross_id, cross_instance_id, date_birth, created_by)
                    values (:cross_id, :ci, :dob, :by)
                    returning id::text"""),
            {"cross_id": cross_id, "ci": ci_id, "dob": dob, "by": created_by},
        ).scalar()

        petri_label = f"PETRI {cross_code} • {dob:%Y-%m-%d}"
        container_id = cx.execute(
            text("""insert into public.containers (container_type, status, label, created_by)
                    values ('petri_dish', 'new_tank', :label, :by)
                    returning id::text"""),
            {"label": petri_label, "by": created_by},
        ).scalar()

        cx.execute(
            text("""insert into public.clutch_containers (container_id, clutch_id, created_by)
                    values (:cid, :cl, :by)"""),
            {"cid": container_id, "cl": clutch_id, "by": created_by},
        )
    return ci_id, ci_code, clutch_id

# ---------------- Filters ----------------
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

# ---------------- Load, pick, preview ----------------
df = _load_runnable_concepts(start, end, created_by, q)
st.caption(f"{len(df)} runnable cross concept(s) (both parents have live tanks)")

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

# ---------------- Schedule (Button) ----------------
if "last_scheduled_runs" not in st.session_state:
    st.session_state["last_scheduled_runs"] = []

creator = os.environ.get("USER") or os.environ.get("USERNAME") or "system"
if st.button("➕ Save scheduled cross instance(s)", type="primary", use_container_width=True, disabled=selected.empty, key="btn_schedule"):
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
        st.session_state["last_scheduled_runs"] = new_run_codes + st.session_state["last_scheduled_runs"]
        st.success(f"Scheduled {created} cross instance(s).")
        st.rerun()
    if errors:
        st.error("Some instances failed:\n- " + "\n- ".join(errors))

# ---------------- Scheduled Instances TABLE (shown immediately after save) ----------------
st.subheader("Scheduled instances")
with _get_engine().begin() as cx:
    inst_rows = cx.execute(
        text("""
            select ci.cross_run_code, ci.cross_date, ci.created_by
            from public.cross_instances ci
            where ci.cross_date between :d1 and :d2
              and (:by is null or ci.created_by = :by)
            order by ci.created_at desc
            limit 100
        """),
        {"d1": start, "d2": end, "by": (created_by or None)},
    ).mappings().all()
st.dataframe(pd.DataFrame([dict(r) for r in inst_rows]), use_container_width=True, hide_index=True)

# ---------------- Downloads & Print (after the table) ----------------
st.subheader("Downloads (scheduled instances)")
sched_codes = st.session_state.get("last_scheduled_runs", [])
report_lines = [f"{r.cross_code} | {getattr(r, 'mom_code', '')} × {getattr(r, 'dad_code', '')} | date {getattr(r, 'date', '')}"
                for r in preview_df.itertuples(index=False)]

# Labels data
def _fetch_labels_for_instances_safe(codes: List[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        return _fetch_labels_for_instances(codes)
    except Exception:
        return (pd.DataFrame(), pd.DataFrame())

df_crossing, df_petri = _fetch_labels_for_instances_safe(sched_codes) if sched_codes else (pd.DataFrame(), pd.DataFrame())

cross_pdf = _labels_pdf_pages(
    _ext_build_crossing_pages(df_crossing) if _ext_build_crossing_pages else _build_crossing_label_pages(df_crossing),
    width_in=2.4, height_in=1.0, header_pt=9.2, body_pt=7.0, leading_pt=7.2
) if not df_crossing.empty else b""

petri_pdf = _labels_pdf_pages(
    _ext_build_petri_pages(df_petri) if _ext_build_petri_pages else _build_petri_label_pages(df_petri),
    width_in=2.4, height_in=0.75, header_pt=10.5, body_pt=7.0, leading_pt=7.1
) if not df_petri.empty else b""

c1, c2, c3, c4, c5 = st.columns(5)
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
with c4:
    if st.button("🖨️ Print crossing labels → Brother", use_container_width=True, disabled=(not cross_pdf), key="print_crossing"):
        ok, msg = _print_pdf_bytes(cross_pdf, queue_name=os.getenv("BROTHER_QUEUE", "Brother_QL_1110NWB"), media_opt=os.getenv("BROTHER_MEDIA_CROSSING", "media=Custom.61x25mm"))
        (st.success if ok else st.error)(msg)
with c5:
    if st.button("🖨️ Print petri labels → Brother", use_container_width=True, disabled=(not petri_pdf), key="print_petri"):
        ok, msg = _print_pdf_bytes(petri_pdf, queue_name=os.getenv("BROTHER_QUEUE", "Brother_QL_1110NWB"), media_opt=os.getenv("BROTHER_MEDIA_PETRI", "media=Custom.61x19mm"))
        (st.success if ok else st.error)(msg)