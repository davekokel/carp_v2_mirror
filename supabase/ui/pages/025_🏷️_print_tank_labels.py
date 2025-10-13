from supabase.ui.email_otp_gate import require_email_otp
require_email_otp()

from __future__ import annotations
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from typing import List, Dict
import os
from io import BytesIO
from datetime import datetime

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

import importlib
import supabase.queries as Q
importlib.reload(Q)

st.set_page_config(page_title="CARP — Overview Tanks (holding) + Labels", page_icon="🏷️", layout="wide")
st.title("🏷️ Overview Tanks (holding) → Print Labels")

_ENGINE = None
def _get_engine():
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    url = os.getenv("DB_URL")
    if not url:
        raise RuntimeError("DB_URL is not set")
    _ENGINE = create_engine(url, future=True, pool_pre_ping=True)
    return _ENGINE

def _stage_choices() -> List[str]:
    sql = """
      select distinct upper(stage) as s
      from public.vw_fish_standard
      where stage is not null and stage <> ''
      order by 1
    """
    with _get_engine().begin() as cx:
        df = pd.read_sql(text(sql), cx)
    return [s for s in df["s"].astype(str).tolist() if s]

def _load_standard_for_codes(codes: List[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame()
    sql = text("""
      with wanted as (
        select id, fish_code
        from public.fish
        where fish_code = any(:codes)
      ),
      live_counts as (
        select m.fish_id, count(*)::int as n_living_tanks
        from public.fish_tank_memberships m
        join public.containers c on c.id_uuid = m.container_id
        where m.left_at is null
          and c.status in ('active','new_tank')
          and m.fish_id in (select id from wanted)
        group by m.fish_id
      )
      select
        s.*,
        coalesce(lc.n_living_tanks, 0) as n_living_tanks
      from public.vw_fish_standard s
      join wanted w on w.fish_code = s.fish_code
      left join live_counts lc on lc.fish_id = w.id
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    df = df.loc[:, ~df.columns.duplicated(keep="last")]
    if "n_living_tanks" in df.columns:
        df["n_living_tanks"] = df["n_living_tanks"].fillna(0).astype(int)
    order = {c: i for i, c in enumerate(codes)}
    df["__ord"] = df["fish_code"].map(order).fillna(len(order)).astype(int)
    df = df.sort_values("__ord").drop(columns="__ord")
    return df

@st.cache_data(show_spinner=False)
def _has_location() -> bool:
    with _get_engine().begin() as cx:
        return pd.read_sql(
            text("""
              select 1
              from information_schema.columns
              where table_schema='public'
                and table_name='containers'
                and column_name='location'
              limit 1
            """), cx
        ).shape[0] > 0

def _load_tanks_for_codes(codes: List[str]) -> pd.DataFrame:
    if not codes:
        cols = ["fish_code","container_id","label","status","container_type","location","created_at","activated_at","deactivated_at","last_seen_at","tank_code"]
        return pd.DataFrame(columns=cols)
    loc_expr = "coalesce(c.location,'')" if _has_location() else "''::text"
    base_sql = f"""
      select
        f.fish_code,
        c.id_uuid::text            as container_id,
        coalesce(c.label,'')       as label,
        coalesce(c.status,'')      as status,
        c.container_type,
        {loc_expr}                 as location,
        c.created_at,
        c.activated_at,
        c.deactivated_at,
        c.last_seen_at,
        c.tank_code                as tank_code
      from public.fish f
      join public.fish_tank_memberships m
        on m.fish_id = f.id
       and m.left_at is null
      join public.containers c
        on c.id_uuid = m.container_id
      where f.fish_code = ANY(:codes)
        and c.container_type = 'holding_tank'
      order by f.fish_code, c.created_at
    """
    with _get_engine().begin() as cx:
        return pd.read_sql(text(base_sql), cx, params={"codes": codes})

def _fetch_enriched_for_containers(container_ids: List[str]) -> pd.DataFrame:
    if not container_ids:
        cols = [
            "container_id","tank_code","label","status","container_type","location",
            "created_at","activated_at","deactivated_at","last_seen_at",
            "fish_code","nickname","name","genotype","genetic_background","stage","dob"
        ]
        return pd.DataFrame(columns=cols)

    # location-safe projection (some installs don't have containers.location)
    loc_expr = "c.location::text" if _has_location() else "''::text"

    sql = text(f"""
      with picked as (select unnest(cast(:ids as uuid[])) as container_id),
      live as (
        select m.container_id, m.fish_id
        from public.fish_tank_memberships m
        where m.left_at is null
      )
      select
        c.id_uuid::text                   as container_id,
        c.tank_code::text                 as tank_code,
        coalesce(c.label,'')              as label,
        coalesce(c.status,'')             as status,
        c.container_type::text            as container_type,
        {loc_expr}                        as location,
        c.created_at::timestamptz         as created_at,
        c.activated_at,
        c.deactivated_at,
        c.last_seen_at,
        f.fish_code::text                 as fish_code,
        coalesce(v.nickname,'')           as nickname,
        coalesce(v.name,'')               as name,
        coalesce(v.genotype,'')           as genotype,
        coalesce(v.genetic_background,'') as genetic_background,
        coalesce(v.stage,'')              as stage,
        v.dob                             as dob
      from picked p
      join public.containers c on c.id_uuid = p.container_id
      left join live L on L.container_id = c.id_uuid
      left join public.fish f on f.id = L.fish_id
      left join public.v_fish_label_fields v on v.fish_code = f.fish_code
      order by c.created_at asc, c.tank_code asc
    """)
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params={"ids": container_ids})

from reportlab.pdfgen import canvas as _canvas
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

PT_PER_IN = 72.0
LABEL_W   = 2.4 * PT_PER_IN
LABEL_H   = 1.5 * PT_PER_IN
PAD_L, PAD_R, PAD_T, PAD_B = 10.0, 10.0, 8.0, 8.0
QR_SIZE, QR_GAP = 40.0, 6.0

try:
    pdfmetrics.registerFont(TTFont("LabelMono", "/Library/Fonts/SourceCodePro-Regular.ttf"))
    MONO_FONT_NAME = "LabelMono"
except Exception:
    MONO_FONT_NAME = None

def _safe(v):
    from datetime import date, datetime as _dt
    if v is None: return ""
    if isinstance(v, (_dt, date)): return v.strftime("%Y-%m-%d")
    return str(v).strip()

def _ellipsize(txt: str, max_w: float, font_name: str, font_size: float) -> str:
    if not txt: return ""
    if stringWidth(txt, font_name, font_size) <= max_w: return txt
    ell = "…"; lo, hi = 0, len(txt)
    while lo < hi:
        mid = (lo + hi)//2
        if stringWidth(txt[:mid]+ell, font_name, font_size) <= max_w:
            lo = mid+1
        else:
            hi = mid
    cut = max(0, lo-1)
    return (txt[:cut]+ell) if cut>0 else ell

def _draw_qr(c: _canvas.Canvas, payload: str, x: float, y: float, size: float) -> None:
    try:
        from reportlab.graphics.barcode import qr
        from reportlab.graphics import renderPDF
        from reportlab.graphics.shapes import Drawing
        code = qr.QrCodeWidget(payload or "")
        bx0, by0, bx1, by1 = code.getBounds()
        bw = max(1.0, bx1-bx0); bh = max(1.0, by1-by0)
        sx = size/bw; sy = size/bh
        d = Drawing(size, size, transform=[sx,0,0,sy,0,0])
        d.add(code); renderPDF.draw(d, c, x, y)
    except Exception:
        pass

def _render_full_label(c: _canvas.Canvas, r: Dict) -> None:
    x0, y0 = PAD_L, PAD_B
    w  = LABEL_W - PAD_L - PAD_R
    h  = LABEL_H - PAD_B - PAD_T
    qr_x, qr_y = x0 + w - QR_SIZE, y0
    text_w = w - QR_SIZE - QR_GAP
    mono = MONO_FONT_NAME or "Helvetica"

    nickname = _safe(r.get("nickname"))
    name     = _safe(r.get("name"))
    tankline = _safe(r.get("tank_line"))
    fishcode = _safe(r.get("fish_code"))
    genotype = _safe(r.get("genotype"))
    backgrnd = _safe(r.get("genetic_background"))
    stage    = _safe(r.get("stage"))
    dob      = _safe(r.get("dob"))

    lines = [
        ("nick","Helvetica-Oblique", 9.0,  nickname, 0.00),
        ("name","Helvetica-Bold",   10.5,  name,     0.00),
        ("tank","Helvetica-Bold",   11.0,  (tankline or fishcode), 0.00),
        ("geno",mono,                9.2,  genotype, 0.00),
        ("bg",  "Helvetica",         8.2,  backgrnd, 0.00),
        ("stg", "Helvetica",         8.2,  stage,    0.00),
        ("dob", "Helvetica",         8.2,  dob,      0.00),
    ]

    lane_h = h/len(lines); MIN_FS = 7.0; TOP_PAD_FRAC = 0.82
    for i, (_k, fn, fs, txt, gray) in enumerate(lines):
        lane_top = y0 + h - i*lane_h
        fs_lane = min(fs, max(MIN_FS, lane_h - 1.0)); fs_use = fs_lane
        if _k in ("nick","name","tank") and txt:
            while fs_use>MIN_FS and stringWidth(txt, fn, fs_use) > text_w:
                fs_use -= 0.3
        line = _ellipsize(txt or "", text_w, fn, fs_use)
        baseline = lane_top - (fs_use*TOP_PAD_FRAC)
        c.setFont(fn, fs_use); c.setFillGray(gray); c.drawString(x0, baseline, line)

    payload = _safe(r.get("tank_code")) or fishcode or tankline
    if payload: _draw_qr(c, payload, qr_x, qr_y, QR_SIZE)

def _build_labels_pdf(rows: List[Dict]) -> bytes:
    buf = BytesIO(); c = _canvas.Canvas(buf, pagesize=(LABEL_W, LABEL_H))
    for r in rows:
        _render_full_label(c, r); c.showPage()
    c.save(); buf.seek(0); return buf.read()

with st.form("filters"):
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        q = st.text_input("Search (multi-term; quotes & -negation supported)", "")
    with col2:
        try:
            stages = st.multiselect("Stage", _stage_choices(), default=[])
        except Exception:
            stages = []
    with col3:
        limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
    submitted = st.form_submit_button("Apply")

rows = Q.load_fish_overview(_get_engine(), q=q, stages=stages, limit=limit)
match_df = pd.DataFrame(rows)
st.caption(f"{len(match_df)} matches")
if match_df.empty:
    st.info("No rows match your filters.")
    with st.expander("Debug"):
        st.write({"VIEW": getattr(Q, "VIEW", "auto"), "search_columns": getattr(Q, "SEARCH_COLUMNS", "auto")})
        st.code(q or "", language="text")
    st.stop()

codes_in_order = match_df["fish_code"].astype(str).tolist()
df = _load_standard_for_codes(codes_in_order)

base_cols = [
    "fish_code","name","nickname","genotype","genetic_background","stage",
    "date_birth","age_days","created_at","created_by","batch_display",
    "treatments_rollup","n_living_tanks"
]
for c in base_cols:
    if c not in df.columns:
        df[c] = None

view = df[base_cols].copy()
view.insert(0, "✓ Select", False)

key_sig = "|".join(codes_in_order)
if st.session_state.get("_ov_sig") != key_sig:
    st.session_state["_ov_sig"] = key_sig
    st.session_state["_ov_table"] = view.copy()

csa, csb = st.columns([1,1])
with csa:
    if st.button("Select all"):
        st.session_state["_ov_table"].loc[:, "✓ Select"] = True
with csb:
    if st.button("Clear all"):
        st.session_state["_ov_table"].loc[:, "✓ Select"] = False

edited = st.data_editor(
    st.session_state["_ov_table"],
    use_container_width=True,
    hide_index=True,
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
        "fish_code": st.column_config.TextColumn("fish_code", disabled=True),
        "name": st.column_config.TextColumn("name", disabled=True),
        "nickname": st.column_config.TextColumn("nickname", disabled=True),
        "genotype": st.column_config.TextColumn("genotype", disabled=True),
        "genetic_background": st.column_config.TextColumn("genetic_background", disabled=True),
        "stage": st.column_config.TextColumn("stage", disabled=True),
        "date_birth": st.column_config.DateColumn("date_birth", disabled=True),
        "age_days": st.column_config.NumberColumn("age_days", disabled=True),
        "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
        "created_by": st.column_config.TextColumn("created_by", disabled=True),
        "batch_display": st.column_config.TextColumn("batch_display", disabled=True),
        "treatments_rollup": st.column_config.TextColumn("treatments_rollup", disabled=True),
        "n_living_tanks": st.column_config.NumberColumn("n_living_tanks", disabled=True),
    },
    key="ov_editor",
)
st.session_state["_ov_table"] = edited.copy()
selected_codes = edited.loc[edited["✓ Select"], "fish_code"].astype(str).tolist()

st.subheader("Tanks for selected fish (holding_tank only)")
if not selected_codes:
    st.info("Select one or more fish above to see their current tanks.")
    st.stop()

tanks_df = _load_tanks_for_codes(selected_codes)
if tanks_df.empty:
    st.info("No active holding tanks for the selected fish.")
    st.stop()

tanks_df = tanks_df.sort_values(["fish_code", "created_at"], ascending=[True, False])
tanks_view = tanks_df.rename(columns={
    "fish_code":"fish_code",
    "container_id":"container_id",
    "label":"label",
    "status":"status",
    "container_type":"type",
    "location":"location",
    "created_at":"created_at",
    "activated_at":"activated_at",
    "deactivated_at":"deactivated_at",
    "last_seen_at":"last_seen_at",
    "tank_code":"tank_code",
})
cols = ["fish_code","label","status","type","created_at","activated_at","deactivated_at","last_seen_at","container_id"]
if "location" in tanks_view.columns:
    cols.insert(4, "location")
st.dataframe(tanks_view[cols], use_container_width=True, hide_index=True)

only_new = st.checkbox("Only print tanks with status = new_tank", value=True)
to_print = tanks_view if not only_new else tanks_view[tanks_view["status"] == "new_tank"]

if st.button("🖨️ Download labels (2.4 × 1.5 • QR)"):
    if to_print.empty:
        st.warning("No tanks to print.")
        st.stop()
    ids = to_print["container_id"].astype(str).tolist()
    enriched = _fetch_enriched_for_containers(ids)
    rows: List[Dict] = []
    for _, r in enriched.iterrows():
        rows.append({
            "tank_code": r.get("tank_code"),
            "tank_line": r.get("tank_code") or r.get("label"),
            "label":     r.get("label"),
            "fish_code": r.get("fish_code"),
            "nickname":  r.get("nickname"),
            "name":      r.get("name"),
            "genotype":  r.get("genotype"),
            "genetic_background": r.get("genetic_background"),
            "stage":     r.get("stage"),
            "dob":       r.get("dob"),
        })
    pdf = _build_labels_pdf(rows)
    fname = f"tank_labels_2_4x1_5_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    st.download_button("Download PDF", data=pdf, file_name=fname, mime="application/pdf", type="primary", use_container_width=True)