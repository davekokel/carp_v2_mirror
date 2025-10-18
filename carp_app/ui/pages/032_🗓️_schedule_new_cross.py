from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os, tempfile, subprocess
from datetime import date, timedelta
from typing import List, Dict, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.lib.config import engine as get_engine

sb, session, user = require_auth()
require_email_otp()

st.set_page_config(page_title="🗓️ Schedule new cross", page_icon="🗓️", layout="wide")
st.title("🗓️ Schedule new cross")

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

try:
    from carp_app.lib.labels_components import (
        build_crossing_label_pages as _ext_build_crossing_pages,
        build_petri_label_pages as _ext_build_petri_pages,
        make_label_pdf as _ext_make_label_pdf,
    )
except Exception:
    _ext_build_crossing_pages = _ext_build_petri_pages = _ext_make_label_pdf = None

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
    def esc(s: str) -> str: return s.replace("\\","\\\\").replace("(","\\(").replace(")","\\)")
    content = ["BT","/F1 12 Tf","72 770 Td","1 -1 scale",f"( {esc(title)} ) Tj","T*"]
    for ln in lines: content += [f"( {esc(ln)} ) Tj","T*"]
    content.append("ET")
    stream = "\n".join(content).encode("latin-1","replace")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n"%len(stream)+stream+b"\nendstream",
    ]
    out = bytearray(); out.extend(b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n"); offs=[]
    for i,b in enumerate(objs,1):
        offs.append(len(out)); out.extend(f"{i} 0 obj\n".encode()); out.extend(b); out.extend(b"\nendobj\n")
    xref=len(out); out.extend(b"xref\n"); out.extend(f"0 {len(objs)+1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for o in offs: out.extend(f"{o:010d} 00000 n \n".encode())
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
    def esc(s: str) -> str: return s.replace("\\","\\\\").replace("(","\\(").replace(")","\\)")
    import io
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n")
    obj_offsets = []
    def add_obj(s: bytes) -> int:
        obj_offsets.append(out.tell()); out.write(s); out.write(b"\nendobj\n"); return len(obj_offsets)
    pages_ids=[]; W,H=int(width_in*72),int(height_in*72)
    font_id = add_obj(b"1 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for lines in pages:
        y = H - 12
        parts = [f"BT /F1 {int(header_pt)} Tf 6 {y} Td 1 -1 scale".encode()]
        if lines: parts += [f"( {esc(lines[0])} ) Tj".encode()]
        parts += [f"/F1 {int(body_pt)} Tf".encode()]
        for ln in lines[1:]:
            parts += [b"T*", f"( {esc(ln[:120])} ) Tj".encode()]
        parts += [b"ET"]
        stream = b"\n".join(parts)
        cont_id = add_obj(b"2 0 obj\n<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
        page_id = add_obj(b"0 0 obj\n<< /Type /Page /Parent 3 0 R /MediaBox [0 0 " + str(W).encode() + b" " + str(H).encode() + b"] /Resources << /Font << /F1 " + str(font_id).encode() + b" 0 R >> >> /Contents " + str(cont_id).encode() + b" 0 R >>")
        pages_ids.append(page_id)
    kids = " ".join(f"{pid} 0 R" for pid in pages_ids).encode()
    pages_id = add_obj(b"3 0 obj\n<< /Type /Pages /Kids [ " + kids + b" ] /Count " + str(len(pages_ids)).encode() + b" >>")
    catalog_id = add_obj(b"4 0 obj\n<< /Type /Catalog /Pages 3 0 R >>")
    xref = out.tell()
    out.write(b"xref\n0 " + str(len(obj_offsets)+1).encode() + b"\n")
    out.write(b"0000000000 65535 f \n")
    for off in obj_offsets: out.write(f"{off:010d} 00000 n \n".encode())
    out.write(b"trailer\n<< /Size " + str(len(obj_offsets)+1).encode() + b" /Root " + str(catalog_id).encode() + b" 0 R >>\n")
    out.write(b"startxref\n" + str(xref).encode() + b"\n%%EOF\n")
    return out.getvalue()

def _build_crossing_label_pages(df: pd.DataFrame) -> List[List[str]]:
    if _ext_build_crossing_pages: return _ext_build_crossing_pages(df)
    pages=[]
    for r in df.itertuples(index=False):
        cc = getattr(r,"cross_code","") or ""
        dt = pd.to_datetime(getattr(r,"cross_date",None)).strftime("%a %Y-%m-%d") if getattr(r,"cross_date",None) is not None else ""
        mom = (getattr(r,"mother_tank_label","") or getattr(r,"mother_tank_code","")) or ""
        dad = (getattr(r,"father_tank_label","") or getattr(r,"father_tank_code","")) or ""
        pages.append([f"CROSS {cc}", dt, f"M: {mom}", f"D: {dad}"])
    return pages

def _build_petri_label_pages(df: pd.DataFrame) -> List[List[str]]:
    if _ext_build_petri_pages: return _ext_build_petri_pages(df)
    pages=[]
    for r in df.itertuples(index=False):
        inst = getattr(r,"clutch_instance_code","") or ""
        name = getattr(r,"clutch_name","") or ""
        mom  = getattr(r,"mom_code","") or ""
        dad  = getattr(r,"dad_code","") or ""
        dob  = getattr(r,"date_birth",None)
        dob_text = pd.to_datetime(dob).date().isoformat() if dob is not None else "DOB TBD"
        pages.append([inst, name, f"{mom} × {dad}", dob_text])
    return pages

def _print_pdf_bytes(pdf_bytes: bytes, queue_name: str, media_opt: str) -> tuple[bool,str]:
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes); tmp_path = tmp.name
        out = subprocess.run(["lp","-d",queue_name,"-o",media_opt,tmp_path], capture_output=True, text=True, check=False)
        ok = (out.returncode==0); msg = out.stdout.strip() or out.stderr.strip() or ("sent to "+queue_name if ok else "print failed")
        return ok, msg
    except FileNotFoundError:
        return False, "lp not found on host"
    except Exception as e:
        return False, str(e)

def _lookup_cross_id(cross_code: str) -> str:
    with _get_engine().begin() as cx:
        row = cx.execute(text("select id::text from public.crosses where cross_code = :c limit 1"), {"c": cross_code}).fetchone()
    if not row: raise RuntimeError(f"cross_id not found for code {cross_code}")
    return row[0]

def _schedule_instance(cross_code: str, mom_code: str, dad_code: str,
                       run_date: date, created_by: str,
                       mother_tank_id: str | None = None, father_tank_id: str | None = None,
                       note: str | None = None):
    cross_id = _lookup_cross_id(cross_code)
    with _get_engine().begin() as cx:
        if mother_tank_id and father_tank_id:
            cx.execute(text("""
                insert into public.planned_crosses
                  (clutch_id, cross_id, mom_code, dad_code, mother_tank_id, father_tank_id, cross_date, note, created_by)
                values (null, :cross_id, :mom, :dad, :m_id, :f_id, :d, :note, :by)
                on conflict on constraint uq_planned_crosses_clutch_parents_canonical do nothing
            """), {"cross_id": cross_id, "mom": mom_code, "dad": dad_code,
                   "m_id": mother_tank_id, "f_id": father_tank_id,
                   "d": run_date, "note": note or "", "by": created_by})
        ci_id, ci_code = cx.execute(text("""
            insert into public.cross_instances (cross_id, cross_date, note, created_by)
            values (:cross_id, :d, :note, :by)
            returning id::text, cross_run_code
        """), {"cross_id": cross_id, "d": run_date, "note": note, "by": created_by}).one()
        dob = run_date + timedelta(days=1)
        clutch_id = cx.execute(text("""
            insert into public.clutches (cross_id, cross_instance_id, date_birth, created_by)
            values (:cross_id, :ci, :dob, :by) returning id::text
        """), {"cross_id": cross_id, "ci": ci_id, "dob": dob, "by": created_by}).scalar()
        petri_label = f"PETRI {cross_code} • {dob:%Y-%m-%d}"
        container_id = cx.execute(text("""
            insert into public.containers (container_type, status, label, created_by)
            values ('petri_dish', 'new_tank', :label, :by) returning id::text
        """), {"label": petri_label, "by": created_by}).scalar()
        cx.execute(text("""
            insert into public.clutch_containers (container_id, clutch_id, created_by)
            values (:cid, :cl, :by)
        """), {"cid": container_id, "cl": clutch_id, "by": created_by})
    return ci_id, ci_code, clutch_id

def _fetch_labels_for_instances(inst_codes: List[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not inst_codes:
        return pd.DataFrame(), pd.DataFrame()
    sql = text("""
      with x as (
        select
          ci.cross_run_code,
          ci.cross_date,
          cr.cross_code,
          cr.mother_code as mom_code,
          cr.father_code as dad_code,
          pc.mother_tank_id, pc.father_tank_id,
          cp.planned_name as clutch_name,
          cl.clutch_instance_code,
          cl.date_birth
        from public.cross_instances ci
        join public.crosses cr on cr.id = ci.cross_id
        left join public.planned_crosses pc on pc.cross_id = cr.id
        left join public.clutch_plans   cp on cp.id = pc.clutch_id
        left join public.clutches       cl on cl.cross_instance_id = ci.id
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
      left join public.containers cm on cm.id = x.mother_tank_id
      left join public.containers cf on cf.id = x.father_tank_id
      order by x.cross_date, x.cross_run_code
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": inst_codes})
    df_crossing = df[[
        "cross_code","cross_date",
        "mother_tank_label","father_tank_label",
        "mother_tank_code","father_tank_code",
        "clutch_instance_code","clutch_name"
    ]].copy()
    df_petri = df[[
        "clutch_instance_code","clutch_name",
        "mom_code","dad_code","date_birth","cross_date"
    ]].copy()
    df_crossing["mother_tank_label"] = df_crossing["mother_tank_label"].fillna(df_crossing["mother_tank_code"])
    df_crossing["father_tank_label"] = df_crossing["father_tank_label"].fillna(df_crossing["father_tank_code"])
    return df_crossing, df_petri

def _extract_genotype_tokens(plan_rows: pd.DataFrame) -> Dict[str, List[str]]:
    import re
    texts = []
    for col in ("planned_name","planned_nickname"):
        if col in plan_rows.columns:
            texts += plan_rows[col].dropna().astype(str).tolist()
    blob = " ".join(texts).strip()
    U = blob.upper()
    STOP = {"RNA","MRNA","SGRNA","CAS9","PLASMID","VECTOR","MORPHOLINO","MO","DYE","INJECT","INJECTION","TREAT","DOSE","EXPOSE","TRICAINE","UG","µG","MG/ML","NM","µM","UM","%","H","HPF","DPF"}
    geno = set()
    for m in re.findall(r"Tg[\[\(][A-Za-z0-9:_\-]+[\]\)]\d+|[A-Za-z0-9:_\-]+\^[A-Za-z0-9:_\-]+|[A-Za-z0-9:_\-]+:[A-Za-z0-9:_\-]+", blob):
        t = m.strip()
        if t and t.upper() not in STOP:
            geno.add(t)
    for m in re.findall(r"[A-Za-z0-9]{3,}[-_:]?[0-9]{2,3}", blob):
        t = m.strip()
        if t and t.upper() not in STOP:
            geno.add(t)
    strain = set()
    for s in ["CASPER","AB","TU","TL","WIK","EK","TÜ","TÜB","NACRE","ROY"]:
        if s in U:
            strain.add(s)
    return {"geno": sorted(geno), "strain": sorted(strain)}

def _fetch_fish_genotypes_and_bg(codes: List[str]) -> Dict[str, Dict[str,str]]:
    if not codes: return {}
    uniq = list({c for c in codes if c})
    with _get_engine().begin() as cx:
        has_vw = bool(pd.read_sql(
            text("""select 1 from information_schema.tables 
                    where table_schema='public' and table_name='vw_fish_overview' limit 1"""), cx
        ).shape[0])
        if has_vw:
            df = pd.read_sql(
                text("""select fish_code, coalesce(genotype,'') as genotype,
                               coalesce(genetic_background,'') as genetic_background
                        from public.vw_fish_overview
                        where fish_code = any(:codes)"""),
                cx, params={"codes": uniq}
            )
        else:
            cols = pd.read_sql(
                text("""select column_name from information_schema.columns 
                        where table_schema='public' and table_name='fish'"""), cx
            )["column_name"].tolist()
            gcol = "genotype" if "genotype" in cols else None
            bcol = "genetic_background" if "genetic_background" in cols else None
            if gcol or bcol:
                df = pd.read_sql(
                    text(f"""select fish_code,
                                    coalesce({gcol},'') as genotype,
                                    coalesce({bcol},'') as genetic_background
                             from public.fish where fish_code = any(:codes)"""),
                    cx, params={"codes": uniq}
                )
            else:
                df = pd.DataFrame({"fish_code": uniq, "genotype": ["" for _ in uniq], "genetic_background": ["" for _ in uniq]})
    return {r["fish_code"]: {"genotype": r.get("genotype",""), "genetic_background": r.get("genetic_background","")} for _, r in df.iterrows()}

def _score_fish_row(geno: str, bg: str, tokens: Dict[str,List[str]]) -> int:
    g = f"{(geno or '').upper()} {(bg or '').upper()}".strip()
    score = 0
    for t in tokens.get("geno", []):
        if t.upper() in g:
            score += 2
    for s in tokens.get("strain", []):
        if s in g:
            score += 1
    return score

def _load_clutch_concepts(d1: date, d2: date, created_by: str, q: str) -> pd.DataFrame:
    sql = text("""
    WITH mom_live AS (
      SELECT f.fish_code, COUNT(*)::int AS n_live
      FROM public.fish f
      JOIN public.fish_tank_memberships m ON m.fish_id = f.id AND m.left_at IS NULL
      JOIN public.containers c           ON c.id = m.container_id
      WHERE c.status = ANY(:live_statuses) AND c.container_type = ANY(:tank_types)
      GROUP BY f.fish_code
    ),
    dad_live AS (
      SELECT f.fish_code, COUNT(*)::int AS n_live
      FROM public.fish f
      JOIN public.fish_tank_memberships m ON m.fish_id = f.id AND m.left_at IS NULL
      JOIN public.containers c           ON c.id = m.container_id
      WHERE c.status = ANY(:live_statuses) AND c.container_type = ANY(:tank_types)
      GROUP BY f.fish_code
    ),
    tx_counts AS (
      SELECT clutch_id, COUNT(*)::int AS n_treatments
      FROM public.clutch_plan_treatments
      GROUP BY clutch_id
    ),
    last_used AS (
      SELECT
        pc.clutch_id,
        pc.mother_tank_id,
        pc.father_tank_id,
        ROW_NUMBER() OVER (
          PARTITION BY pc.clutch_id
          ORDER BY COALESCE(pc.cross_date::timestamp, pc.created_at) DESC NULLS LAST
        ) AS rn
      FROM public.planned_crosses pc
    )
    SELECT
      cp.id::text                          AS clutch_id,
      COALESCE(cp.clutch_code, cp.id::text) AS clutch_code,
      COALESCE(cp.planned_name,'')         AS planned_name,
      COALESCE(cp.planned_nickname,'')     AS planned_nickname,
      cp.mom_code,
      cp.dad_code,
      COALESCE(ml.n_live,0)                AS mom_live,
      COALESCE(dl.n_live,0)                AS dad_live,
      (COALESCE(ml.n_live,0) * COALESCE(dl.n_live,0))::int AS pairings,
      COALESCE(tx.n_treatments,0)          AS n_treatments,
      lm.label AS last_mom_label,
      lf.label AS last_dad_label,
      cp.created_by,
      cp.created_at
    FROM public.clutch_plans cp
    LEFT JOIN mom_live ml ON ml.fish_code = cp.mom_code
    LEFT JOIN dad_live dl ON dl.fish_code = cp.dad_code
    LEFT JOIN tx_counts tx ON tx.clutch_id = cp.id
    LEFT JOIN last_used lu ON lu.clutch_id = cp.id AND lu.rn = 1
    LEFT JOIN public.containers lm ON lm.id = lu.mother_tank_id
    LEFT JOIN public.containers lf ON lf.id = lu.father_tank_id
    WHERE (cp.created_at::date BETWEEN :d1 AND :d2)
      AND (:by = '' OR cp.created_by ILIKE :byl)
      AND (
        :q = '' OR
        COALESCE(cp.clutch_code,'')      ILIKE :ql OR
        COALESCE(cp.planned_name,'')     ILIKE :ql OR
        COALESCE(cp.planned_nickname,'') ILIKE :ql OR
        COALESCE(cp.mom_code,'')         ILIKE :ql OR
        COALESCE(cp.dad_code,'')         ILIKE :ql
      )
    ORDER BY cp.created_at DESC
    """)
    params = {
        "live_statuses": list(LIVE_STATUSES),
        "tank_types": list(TANK_TYPES),
        "d1": d1, "d2": d2,
        "by": created_by or "", "byl": f"%{created_by or ''}%",
        "q": q or "", "ql": f"%{q or ''}%"
    }
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params=params)

with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1, c2, c3, c4 = st.columns([1,1,1,3])
    with c1: start = st.date_input("From", value=today - timedelta(days=14))
    with c2: end   = st.date_input("To", value=today)
    with c3: created_by = st.text_input("Created by", value=os.environ.get("USER") or os.environ.get("USERNAME") or "")
    with c4: q = st.text_input("Omni-search (code / name / nickname / mom / dad)", value="")
    st.form_submit_button("Apply", use_container_width=True)

plans = _load_clutch_concepts(start, end, created_by, q)
if "n_treatments" in plans.columns:
    plans = plans[plans["n_treatments"].fillna(0) == 0]

st.markdown("### 1) Select the clutch genotype you want to generate")
st.caption(f"{len(plans)} clutch concept(s). Showing genotype-only (no treatments).")

visible_cols = ["clutch_code","planned_name","planned_nickname","pairings","last_mom_label","last_dad_label","created_by","created_at"]
plan_df = plans.copy() if not plans.empty else pd.DataFrame(columns=visible_cols)
if "✓ Select" not in plan_df.columns:
    plan_df.insert(0,"✓ Select",False)

plan_table_key = f"plans_{start}_{end}_{created_by}_{q}"
plan_edited = st.data_editor(
    plan_df[["✓ Select"] + visible_cols],
    hide_index=True,
    use_container_width=True,
    column_order=["✓ Select"] + visible_cols,
    column_config={
        "✓ Select":  st.column_config.CheckboxColumn("✓", default=False),
        "pairings":  st.column_config.NumberColumn("pairings", disabled=True, width="small"),
        "created_at":st.column_config.DatetimeColumn("created_at", disabled=True),
    },
    key=plan_table_key,
)
sel_mask  = plan_edited.get("✓ Select", pd.Series(False, index=plan_edited.index)).fillna(False).astype(bool)
sel_plans = plan_df.loc[sel_mask].reset_index(drop=True)

st.subheader("2) Choose FSH pairings (mother fish × father fish)")
if sel_plans.empty:
    st.info("Select a clutch genotype above to see live parent candidates.")
    fsh_pairs_selected = pd.DataFrame(columns=["mom_code","mom_live","dad_code","dad_live"])
else:
    sql_live_fish = text("""
        with live_counts as (
            select f.fish_code, count(*)::int as n_live
            from public.fish f
            join public.fish_tank_memberships m on m.fish_id=f.id and m.left_at is null
            join public.containers c on c.id=m.container_id
            where c.status = any(:live_statuses) and c.container_type = any(:tank_types)
            group by f.fish_code
        )
        select fish_code, n_live from live_counts order by fish_code
    """)
    with _get_engine().begin() as cx:
        live_fish = pd.read_sql(sql_live_fish, cx, params={"live_statuses": list(LIVE_STATUSES), "tank_types": list(TANK_TYPES)})

    f1, f2 = st.columns([1,1])
    with f1: mom_filter = st.text_input("Filter mothers (contains)", value="")
    with f2: dad_filter = st.text_input("Filter fathers (contains)", value="")

    moms_df = live_fish.copy(); dads_df = live_fish.copy()
    if mom_filter: moms_df = moms_df[moms_df["fish_code"].str.contains(mom_filter, case=False, na=False)]
    if dad_filter: dads_df = dads_df[dads_df["fish_code"].str.contains(dad_filter, case=False, na=False)]

    fish_pool = sorted(set(moms_df["fish_code"].tolist() + dads_df["fish_code"].tolist()))
    geno_map = _fetch_fish_genotypes_and_bg(fish_pool)
    moms_df["genotype"] = moms_df["fish_code"].map(lambda c: geno_map.get(c,{}).get("genotype",""))
    moms_df["genetic_background"] = moms_df["fish_code"].map(lambda c: geno_map.get(c,{}).get("genetic_background",""))
    dads_df["genotype"] = dads_df["fish_code"].map(lambda c: geno_map.get(c,{}).get("genotype",""))
    dads_df["genetic_background"] = dads_df["fish_code"].map(lambda c: geno_map.get(c,{}).get("genetic_background",""))

    pairs = (
        moms_df.assign(key=1)
        .merge(dads_df.assign(key=1), on="key", suffixes=("_mom","_dad"))
        .drop(columns="key")
        .rename(columns={
            "fish_code_mom":"mom_code","n_live_mom":"mom_live",
            "genotype_mom":"mom_genotype","genetic_background_mom":"mom_background",
            "fish_code_dad":"dad_code","n_live_dad":"dad_live",
            "genotype_dad":"dad_genotype","genetic_background_dad":"dad_background",
        })
    )

    match_tokens = _extract_genotype_tokens(sel_plans)
    if match_tokens["geno"] or match_tokens["strain"]:
        st.caption("Parent auto-filter tokens: " + ", ".join(match_tokens["geno"] + match_tokens["strain"]))
    ignore_tokens = st.checkbox("Ignore genotype tokens for parent selection", value=False)

    pairs["score_mom"] = pairs.apply(lambda r: _score_fish_row(r["mom_genotype"], r["mom_background"], match_tokens), axis=1)
    pairs["score_dad"] = pairs.apply(lambda r: _score_fish_row(r["dad_genotype"], r["dad_background"], match_tokens), axis=1)
    pairs["score_pair"] = pairs["score_mom"] + pairs["score_dad"]

    compat_mask = pd.Series(True, index=pairs.index)
    if (match_tokens["geno"] or match_tokens["strain"]) and not ignore_tokens:
        compat_mask = (pairs["score_pair"] > 0)
        if not compat_mask.any():
            st.info("No parent pairs matched genotype tokens — showing all candidates. Toggle the checkbox above to bypass this filter.")
            compat_mask[:] = True

    pairs = pairs[compat_mask].reset_index(drop=True)
    pairs = pairs.sort_values(["score_pair","mom_code","dad_code"], ascending=[False, True, True]).reset_index(drop=True)

    if pairs.empty:
        st.info("No fish pairings match the filters and genotype requirements.")
        fsh_pairs_selected = pd.DataFrame(columns=["mom_code","mom_live","dad_code","dad_live","mom_genotype","dad_genotype"])
    else:
        pairs.insert(0,"✓ Pair",False)
        pairs["est_pairings"] = (pairs["mom_live"] * pairs["dad_live"]).astype(int)
        pairs_view = pairs[[
            "✓ Pair",
            "mom_code","mom_live","mom_genotype","mom_background","score_mom",
            "dad_code","dad_live","dad_genotype","dad_background","score_dad",
            "score_pair","est_pairings"
        ]]
        pairs_edit = st.data_editor(
            pairs_view, hide_index=True, use_container_width=True, num_rows="fixed",
            column_config={
                "✓ Pair":        st.column_config.CheckboxColumn("✓ Pair", default=False),
                "mom_live":      st.column_config.NumberColumn("#mom tanks", disabled=True, width="small"),
                "dad_live":      st.column_config.NumberColumn("#dad tanks", disabled=True, width="small"),
                "mom_genotype":  st.column_config.TextColumn("mom genotype", disabled=True, width="large"),
                "mom_background":st.column_config.TextColumn("mom background", disabled=True),
                "dad_genotype":  st.column_config.TextColumn("dad genotype", disabled=True, width="large"),
                "dad_background":st.column_config.TextColumn("dad background", disabled=True),
                "score_mom":     st.column_config.NumberColumn("mom score", disabled=True, width="small"),
                "score_dad":     st.column_config.NumberColumn("dad score", disabled=True, width="small"),
                "score_pair":    st.column_config.NumberColumn("pair score", disabled=True, width="small"),
                "est_pairings":  st.column_config.NumberColumn("est tank pairs", disabled=True, width="small"),
            },
            key="fsh_pairs_editor",
        )
        fsh_pairs_selected = pairs_edit[pairs_edit["✓ Pair"]].reset_index(drop=True)
        st.caption(f"{len(fsh_pairs_selected)} FSH pair(s) selected")

st.subheader("3) Available instance(s) (live tank pairings)")
if sel_plans.empty or (isinstance(locals().get("fsh_pairs_selected", None), pd.DataFrame) and fsh_pairs_selected.empty):
    st.info("Pick at least one clutch genotype and at least one mother×father fish pair to see runnable tank pairings.")
    inst_df = pd.DataFrame(columns=["✓ Run","clutch_code","cross","mom_code","mom_tank","mom label","dad_code","dad_tank","dad label","note","mom_tank_id","dad_tank_id"])
else:
    fish_codes = sorted(set(fsh_pairs_selected["mom_code"].tolist() + fsh_pairs_selected["dad_code"].tolist()))
    sql_live = text("""
        select f.fish_code, c.id::text as tank_id, c.tank_code, coalesce(c.label,'') as tank_label
        from public.fish f
        join public.fish_tank_memberships m on m.fish_id=f.id and m.left_at is null
        join public.containers c on c.id=m.container_id
        where f.fish_code = any(:fish_codes)
          and c.status = any(:live_statuses)
          and c.container_type = any(:tank_types)
        order by f.fish_code, c.tank_code
    """)
    with _get_engine().begin() as cx:
        live = pd.read_sql(sql_live, cx, params={"fish_codes": fish_codes, "live_statuses": list(LIVE_STATUSES), "tank_types": list(TANK_TYPES)})
    by_fish: Dict[str, pd.DataFrame] = {fc: live[live["fish_code"]==fc].copy() for fc in fish_codes}

    rows=[]
    for plan in sel_plans.itertuples(index=False):
        for row in fsh_pairs_selected.itertuples(index=False):
            mom_code, dad_code = row.mom_code, row.dad_code
            moms = by_fish.get(mom_code, pd.DataFrame()); dads = by_fish.get(dad_code, pd.DataFrame())
            if moms.empty or dads.empty:
                rows.append({"✓ Run": False, "clutch_code": plan.clutch_code, "cross": f"{mom_code}×{dad_code}",
                             "mom_code": mom_code, "mom_tank":"", "mom label":"", "mom_tank_id":"",
                             "dad_code": dad_code, "dad_tank":"", "dad label":"", "dad_tank_id":"",
                             "note":"No live tanks"})
                continue
            for mr in moms.itertuples(index=False):
                for dr in dads.itertuples(index=False):
                    rows.append({"✓ Run": False, "clutch_code": plan.clutch_code, "cross": f"{mom_code}×{dad_code}",
                                 "mom_code": mom_code, "mom_tank": mr.tank_code or "", "mom label": getattr(mr,"tank_label","") or (mr.tank_code or ""), "mom_tank_id": mr.tank_id or "",
                                 "dad_code": dad_code, "dad_tank": dr.tank_code or "", "dad label": getattr(dr,"tank_label","") or (dr.tank_code or ""), "dad_tank_id": dr.tank_id or "",
                                 "note": ""})
    inst_df = pd.DataFrame(rows)

if inst_df.empty:
    st.dataframe(inst_df, hide_index=True, use_container_width=True)
else:
    disabled_cols = [c for c in inst_df.columns if c not in {"✓ Run","note"}]
    inst_df = inst_df[["✓ Run","clutch_code","cross","mom_code","mom_tank","mom label","dad_code","dad_tank","dad label","note","mom_tank_id","dad_tank_id"]]
    inst_edited = st.data_editor(
        inst_df, hide_index=True, use_container_width=True, num_rows="fixed",
        column_config={
            "✓ Run": st.column_config.CheckboxColumn("✓ Run", default=False),
            "note":  st.column_config.TextColumn("note"),
            "mom_tank_id": st.column_config.TextColumn("mom_tank_id", disabled=True),
            "dad_tank_id": st.column_config.TextColumn("dad_tank_id", disabled=True),
            "mom_code":    st.column_config.TextColumn("mom_code", disabled=True),
            "dad_code":    st.column_config.TextColumn("dad_code", disabled=True),
            "mom_tank":    st.column_config.TextColumn("mom_tank", disabled=True),
            "dad_tank":    st.column_config.TextColumn("dad_tank", disabled=True),
            "mom label":   st.column_config.TextColumn("mom label", disabled=True),
            "dad label":   st.column_config.TextColumn("dad label", disabled=True),
            "clutch_code": st.column_config.TextColumn("clutch_code", disabled=True),
            "cross":       st.column_config.TextColumn("cross", disabled=True),
        },
        disabled=disabled_cols,
        key="instance_candidates_editor",
    )
    inst_selected = inst_edited[inst_edited["✓ Run"]].reset_index(drop=True)
    st.caption(f"{len(inst_selected)} tank pairing(s) selected")

st.subheader("4) Schedule")
sched_date = st.date_input("Run date (applies to all selected instances)", value=date.today(), key="run_date_all")
creator = os.environ.get("USER") or os.environ.get("USERNAME") or "system"

if st.button("➕ Save scheduled cross instance(s)", type="primary", use_container_width=True,
             disabled=("inst_selected" not in locals() or inst_selected.empty), key="btn_schedule"):
    created=0; errors=[]; new_codes=[]
    for r in inst_selected.itertuples(index=False):
        try:
            _, ci_code, _ = _schedule_instance(
                cross_code=r.cross,
                mom_code=r.mom_code,
                dad_code=r.dad_code,
                run_date=sched_date,
                created_by=creator,
                mother_tank_id=getattr(r,"mom_tank_id",None) or None,
                father_tank_id=getattr(r,"dad_tank_id",None) or None,
                note=getattr(r,"note","") or "",
            )
            created+=1; new_codes.append(ci_code)
        except Exception as e:
            errors.append(f"{r.cross}: {e}")
    if created:
        st.session_state["last_scheduled_runs"] = new_codes + st.session_state.get("last_scheduled_runs", [])
        st.success(f"Scheduled {created} cross instance(s).")
        st.rerun()
    if errors:
        st.error("Some instances failed:\n- " + "\n- ".join(errors))

st.subheader("5) Scheduled instances")
with _get_engine().begin() as cx:
    inst_rows = cx.execute(text("""
        select
          ci.cross_run_code,
          ci.cross_date,
          ci.created_by,
          x.cross_code,
          coalesce(x.cross_name_code, x.cross_code)    as cross_name,
          coalesce(x.cross_name_genotype,'')           as cross_name_genotype
        from public.cross_instances ci
        join public.crosses x on x.id = ci.cross_id
        where ci.cross_date between :d1 and :d2
          and (:by is null or ci.created_by=:by)
        order by ci.created_at desc
        limit 200
    """), {"d1": start, "d2": end, "by": (created_by or None)}).mappings().all()

sched_df = pd.DataFrame([dict(r) for r in inst_rows])
if sched_df.empty:
    st.info("No scheduled instances in range."); chosen_codes=[]
else:
    sched_df = sched_df.rename(columns={"cross_run_code":"cross_run","cross_date":"date"})
    sched_df.insert(0,"✓ Print",False)
    sched_df["date"] = pd.to_datetime(sched_df["date"], errors="coerce").dt.date
    show_cols = ["✓ Print","cross_run","date","created_by","cross_code","cross_name","cross_name_genotype"]
    for c in show_cols:
        if c not in sched_df.columns: sched_df[c]=None
    sched_view = sched_df[show_cols]
    sched_edit = st.data_editor(
        sched_view, hide_index=True, use_container_width=True, num_rows="fixed",
        column_config={
            "✓ Print":             st.column_config.CheckboxColumn("✓ Print", default=False),
            "cross_run":           st.column_config.TextColumn("cross_run", disabled=True),
            "date":                st.column_config.DateColumn("date", disabled=True),
            "created_by":          st.column_config.TextColumn("created_by", disabled=True),
            "cross_code":          st.column_config.TextColumn("cross_code", disabled=True),
            "cross_name":          st.column_config.TextColumn("cross_name", disabled=True, width="large"),
            "cross_name_genotype": st.column_config.TextColumn("cross_name_genotype", disabled=True, width="large"),
        },
        key="scheduled_instances_editor",
    )
    chosen_codes = sched_edit.loc[sched_edit["✓ Print"], "cross_run"].astype(str).tolist()

st.subheader("Labels & report for selected scheduled instances")
df_crossing, df_petri = (pd.DataFrame(), pd.DataFrame())
if chosen_codes:
    df_crossing, df_petri = _fetch_labels_for_instances(chosen_codes)

cross_pdf = _labels_pdf_pages(_build_crossing_label_pages(df_crossing), 2.4, 1.0, 9.2, 7.0, 7.2) if not df_crossing.empty else b""
petri_pdf  = _labels_pdf_pages(_build_petri_label_pages(df_petri),     2.4, 0.75, 10.5, 7.0, 7.1) if not df_petri.empty else b""

def _fmt_date(x):
    try: return pd.to_datetime(x).date().isoformat()
    except Exception: return str(x or "")

report_lines = []
if not sched_df.empty:
    for r in (sched_edit if "sched_edit" in locals() else sched_df).itertuples(index=False):
        if getattr(r, "✓ Print", False):
            report_lines.append(f"{getattr(r,'cross_run','')} | date {_fmt_date(getattr(r,'date',None))}")

c1,c2,c3,c4,c5 = st.columns(5)
with c1:
    st.download_button(
        "📄 Crossing report (PDF)",
        data=_make_pdf("Crossing report", report_lines or ["(none selected)"]),
        file_name=f"crossing_report_{start:%Y%m%d}_{end:%Y%m%d}.pdf",
        mime="application/pdf",
        key=f"dl_report_{start:%Y%m%d}_{end:%Y%m%d}",
    )
with c2:
    st.download_button(
        "🏷️ Crossing tank labels (2.4\"×1.0\")",
        data=cross_pdf,
        file_name=f"crossing_tank_labels_{start:%Y%m%d}_{end:%Y%m%d}.pdf",
        mime="application/pdf",
        key=f"dl_tank_{start:%Y%m%d}_{end:%Y%m%d}",
        disabled=(not cross_pdf),
    )
with c3:
    st.download_button(
        "⬇️ Petri dish labels (2.4\"×0.75\")",
        data=petri_pdf,
        file_name=f"petri_labels_{start:%Y%m%d}_{end:%Y%m%d}.pdf",
        mime="application/pdf",
        key=f"dl_petri_{start:%Y%m%d}_{end:%Y%m%d}",
        disabled=(not petri_pdf),
    )
with c4:
    if st.button("🖨️ Print crossing labels → Brother", use_container_width=True, disabled=(not cross_pdf), key="print_crossing"):
        ok,msg=_print_pdf_bytes(cross_pdf, os.getenv("BROTHER_QUEUE","Brother_QL_1110NWB"), os.getenv("BROTHER_MEDIA_CROSSING","media=Custom.61x25mm"))
        (st.success if ok else st.error)(msg)
with c5:
    if st.button("🖨️ Print petri labels → Brother", use_container_width=True, disabled=(not petri_pdf), key="print_petri"):
        ok,msg=_print_pdf_bytes(petri_pdf, os.getenv("BROTHER_QUEUE","Brother_QL_1110NWB"), os.getenv("BROTHER_MEDIA_PETRI","media=Custom.61x19mm"))
        (st.success if ok else st.error)(msg)