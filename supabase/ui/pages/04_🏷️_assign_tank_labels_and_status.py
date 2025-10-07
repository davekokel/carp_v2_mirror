from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

import os, json, uuid, re
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Assign Inventory Tanks & Status", page_icon="🏷️")
st.title("🏷️ Assign Inventory Tanks & Status")

if "last_created_container_ids" not in st.session_state:
    st.session_state["last_created_container_ids"] = []

def _db_url() -> str:
    u = os.environ.get("DB_URL", "")
    if not u:
        raise RuntimeError("DB_URL not set")
    return u

ENGINE = create_engine(_db_url(), pool_pre_ping=True)

def _sanitize_label(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def _load_fish(search: str = "") -> pd.DataFrame:
    q = """
      select f.id, f.fish_code, coalesce(f.nickname,'') as nickname, coalesce(f.name,'') as name,
             coalesce(v.genotype_text,'') as genotype_text, f.created_at
      from public.fish f
      left join public.v_fish_overview v on v.fish_code = f.fish_code
      where 1=1
    """
    params: Dict[str, str] = {}
    if search.strip():
        q += " and (f.fish_code ilike :q or f.nickname ilike :q or f.name ilike :q) "
        params["q"] = f"%{search.strip()}%"
    q += " order by f.created_at desc limit 500"
    with ENGINE.begin() as c:
        return pd.read_sql(text(q), c, params=params)

def _load_inventory_tanks() -> pd.DataFrame:
    q = text("""
      select
        id_uuid as id,
        label,
        container_type,
        status,
        created_at,
        status_changed_at,
        activated_at,
        deactivated_at,
        last_seen_at
      from public.v_containers_crossing_candidates
      where container_type = 'inventory_tank'
      order by coalesce(label,'') asc, created_at asc
    """)
    with ENGINE.begin() as c:
        df = pd.read_sql(q, c)
    df["id"] = df["id"].astype(str)
    return df

def _ensure_inventory_tank_v(label: str, created_by: str, status: str, volume_l: int | None) -> str:
    stmt = text("select public.ensure_inventory_tank_v_text(:label, :by, :status, :vol)")
    with ENGINE.begin() as c:
        rid = c.execute(stmt, {"label": label, "by": created_by, "status": status, "vol": volume_l}).scalar()
    return str(rid)

def _assign_fish_to_tank(fish_id: str, tank_id: str, created_by: str, note: Optional[str]) -> str:
    with ENGINE.begin() as c:
        rid = c.execute(text("select public.assign_fish_to_tank(:f, :t, :by, :note)"),
                        dict(f=fish_id, t=tank_id, by=created_by, note=note)).scalar()
        return str(rid)

def _enqueue_tank_labels(container_ids: List[str], created_by: str, title_note: str = "") -> Optional[str]:
    if not container_ids:
        return None
    job_id = str(uuid.uuid4())
    with ENGINE.begin() as c:
        containers = pd.read_sql(
            text("""
              select id_uuid as id, coalesce(label,'') as label
              from public.containers
              where id_uuid = any(CAST(:ids AS uuid[]))
            """),
            c,
            params={"ids": container_ids},
        )
        payloads: List[Dict] = []
        for _, row in containers.iterrows():
            payloads.append(
                dict(
                    tank_label=row["label"],
                    role="Tank",
                    genotype="",
                    plan_date=datetime.now().date().isoformat(),
                )
            )
        c.execute(
            text("""
              insert into public.label_jobs (id_uuid, entity_type, entity_id, template, media, status, requested_by, source_params, num_labels, notes)
              values (:id, 'containers_bulk', null, 'tank_2.4x1.5', '2.4x1.5', 'queued', :by, :params, :num, :notes)
            """),
            dict(
                id=job_id,
                by=created_by,
                params=json.dumps({"count": len(payloads)}),
                num=len(payloads),
                notes=title_note,
            ),
        )
        ins_item = text("""
          insert into public.label_items (id_uuid, job_id, seq, payload, qr_text)
          values (:id, :job_id, :seq, :payload, :qr)
        """)
        for i, p in enumerate(payloads, start=1):
            c.execute(ins_item, dict(
                id=str(uuid.uuid4()),
                job_id=job_id,
                seq=i,
                payload=json.dumps(p),
                qr=None,
            ))
    return job_id

user_default = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
created_by = st.text_input("Created by", value=user_default)

#----------------------------------------------------------------------------------------------------------------------------

st.header("Step 1 — Pick fish")
q = st.text_input("Search fish (code, nickname, name)")
fish_df = _load_fish(q)
if fish_df.empty:
    st.info("No fish found. Try clearing the search box.")
    st.stop()

fish_df = fish_df.copy()
fish_df["id"] = fish_df["id"].astype(str)

base_df = fish_df[["id","fish_code","nickname","name","genotype_text"]].copy()
base_df["✓ Select"] = False
base_df = base_df.rename(columns={
    "fish_code":"Fish code","nickname":"Nickname","name":"Name","genotype_text":"Genotype"
})
base_df = base_df[["id","✓ Select","Fish code","Nickname","Name","Genotype"]].set_index("id")

def _needs_reset(session_df: pd.DataFrame | None, fresh_df: pd.DataFrame) -> bool:
    if session_df is None:
        return True
    return not session_df.index.equals(fresh_df.index)

if _needs_reset(st.session_state.get("fish_picker_df"), base_df):
    st.session_state.fish_picker_df = base_df.copy()

c1, c2 = st.columns([1,1])
with c1:
    if st.button("Select all"):
        st.session_state.fish_picker_df.loc[:, "✓ Select"] = True
with c2:
    if st.button("Clear all"):
        st.session_state.fish_picker_df.loc[:, "✓ Select"] = False

sel_df = st.data_editor(
    st.session_state.fish_picker_df,
    use_container_width=True,
    hide_index=True,
    column_order=["✓ Select","Fish code","Nickname","Name","Genotype"],
    column_config={
        "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
        "Fish code": st.column_config.TextColumn(disabled=True),
        "Nickname": st.column_config.TextColumn(disabled=True),
        "Name": st.column_config.TextColumn(disabled=True),
        "Genotype": st.column_config.TextColumn(disabled=True),
    },
    key="fish_picker_editor",
)
st.session_state.fish_picker_df = sel_df.copy()
selected = sel_df[sel_df["✓ Select"]].copy()
if selected.empty:
    st.warning("Select at least one fish to continue.")
    st.stop()

st.header("Step 2 — New tanks (bulk)")
colv, coln, coll = st.columns([1,1,2])
with colv:
    default_vol = st.selectbox("Tank volume", [2,4,8,16], index=1)
with coln:
    default_count = st.number_input("Tanks per fish", min_value=1, max_value=16, value=1, step=1)
with coll:
    default_label_template = st.text_input("Label template", value="TANK {fish_code}")

st.caption("Per-fish overrides (optional)")
assign_rows: List[dict] = []
for fid, r in selected.iterrows():
    base = default_label_template.format(fish_code=r["Fish code"])
    with st.expander(f"{r['Fish code']} — {r.get('Nickname') or r.get('Name') or ''}", expanded=False):
        c1, c2 = st.columns([1,3])
        with c1:
            count = st.number_input(f"Count for {r['Fish code']}", min_value=1, max_value=16, value=int(default_count), step=1, key=f"cnt_{fid}")
            vol = st.selectbox(f"Volume for {r['Fish code']}", [2,4,8,16], index=[2,4,8,16].index(default_vol), key=f"vol_{fid}")
        with c2:
            label_template = st.text_input(f"Label template for {r['Fish code']}", value=base, key=f"lbl_{fid}")
        assign_rows.append(dict(
            fish_id=str(fid),
            fish_code=r["Fish code"],
            count=int(count),
            volume=int(vol),
            label_template=label_template.strip()
        ))

#----------------------------------------------------------------------------------------------------------------------------

st.header("Step 3 — Create tanks, assign, and label")
enqueue = st.checkbox("Enqueue labels for all created tanks", value=True)
note = st.text_input("Optional membership note", value="")

preview_rows = []
total_new = 0
for row in assign_rows:
    n = row["count"]
    vol = row["volume"]
    tmpl = row["label_template"] or f"TANK {row['fish_code']}"
    labels = [tmpl] if n == 1 else [f"{tmpl} #{i}" for i in range(1, n+1)]
    preview_rows.append({
        "Fish": row["fish_code"],
        "Count": n,
        "Volume (L)": vol,
        "First label": labels[0],
        "…more": max(0, n-1)
    })
    total_new += n

if preview_rows:
    prev_df = pd.DataFrame(preview_rows)
    st.dataframe(prev_df, use_container_width=True, hide_index=True)
    st.caption(f"Total new tanks: {total_new}  •  One active + assigned per fish, others created as planned.")

save_btn = st.button("Create tanks and assign", type="primary", use_container_width=True, disabled=not (created_by and assign_rows))

if save_btn:
    created_ids: List[str] = []
    for row in assign_rows:
        fish_id = row["fish_id"]
        n = row["count"]
        vol = row["volume"]
        tmpl = row["label_template"] or f"TANK {row['fish_code']}"
        labels = [tmpl] if n == 1 else [f"{tmpl} #{i}" for i in range(1, n+1)]
        tank_ids: List[str] = []
        for i, lbl in enumerate(labels, start=1):
            status = "active" if i == 1 else "planned"
            tid = _ensure_inventory_tank_v(lbl, created_by, status, vol)
            tank_ids.append(tid)
        _assign_fish_to_tank(fish_id, tank_ids[0], created_by, note.strip() or None)
        created_ids.extend(tank_ids)

    st.success(f"Created {len(created_ids)} tank(s) across {len(assign_rows)} fish and assigned the first tank for each fish.")
    st.session_state["last_created_container_ids"] = sorted(set(created_ids))

    existing = _load_inventory_tanks().copy()
    existing["id"] = existing["id"].astype(str)

    if enqueue and created_ids:
        jid = _enqueue_tank_labels(sorted(set(created_ids)), created_by, "New inventory tanks")
        if jid:
            st.info(f"Enqueued label job: {jid}")

#---------------------------------------------------------------------------------------------------------------------
# =========================
# Step 4 — Print labels (full 8-row layout + QR, self-contained)
# =========================
st.header("Step 4 — Print labels")

from io import BytesIO
from reportlab.pdfgen import canvas as _canvas
from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

# ----- geometry (same as your label_rolls) -----
PT_PER_IN = 72.0
LABEL_W   = 2.4 * PT_PER_IN
LABEL_H   = 1.5 * PT_PER_IN
PAD_L, PAD_R, PAD_T, PAD_B = 10.0, 10.0, 8.0, 8.0
QR_SIZE, QR_GAP = 40.0, 6.0

# Optional mono font for genotype / fish code (best-effort)
try:
    pdfmetrics.registerFont(TTFont("LabelMono", "/Library/Fonts/SourceCodePro-Regular.ttf"))
    MONO_FONT_NAME = "LabelMono"
except Exception:
    MONO_FONT_NAME = None

def _safe(v):
    from datetime import date, datetime
    if v is None: return ""
    if isinstance(v, (date, datetime)): return v.strftime("%Y-%m-%d")
    return str(v).strip()

def _ellipsize(txt: str, max_w: float, font_name: str, font_size: float) -> str:
    if not txt: return ""
    if stringWidth(txt, font_name, font_size) <= max_w: return txt
    ell = "…"
    lo, hi = 0, len(txt)
    while lo < hi:
        mid = (lo + hi) // 2
        if stringWidth(txt[:mid] + ell, font_name, font_size) <= max_w:
            lo = mid + 1
        else:
            hi = mid
    cut = max(0, lo - 1)
    return (txt[:cut] + ell) if cut > 0 else ell

# QR (same placement/scale logic)
def _draw_qr(c: _canvas.Canvas, payload: str, x: float, y: float, size: float) -> None:
    try:
        from reportlab.graphics.barcode import qr
        from reportlab.graphics import renderPDF
        from reportlab.graphics.shapes import Drawing
        code = qr.QrCodeWidget(payload or "")
        bounds = code.getBounds()
        bw = max(1.0, bounds[2] - bounds[0])
        bh = max(1.0, bounds[3] - bounds[1])
        sx = size / bw
        sy = size / bh
        d = Drawing(size, size, transform=[sx, 0, 0, sy, 0, 0])
        d.add(code)
        renderPDF.draw(d, c, x, y)
    except Exception:
        pass

# Stable fallback for tank code if you want it later
_ALPH32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
def _tank_code_for(fish_code: str, when=None) -> str:
    from datetime import datetime
    when = when or datetime.utcnow()
    yy = when.strftime("%y")
    h = 2166136261
    for ch in (fish_code or ""):
        h ^= ord(ch); h = (h * 16777619) & 0xFFFFFFFF
    # simple 4-char crockford
    n = abs(h); out = []
    while n: n, r = divmod(n, 32); out.append(_ALPH32[r])
    base = "".join(reversed(out))[:4].rjust(4,"0")
    return f"TANK-{yy}{base}"

def _fetch_created_tanks_with_fish(ids: List[str]) -> pd.DataFrame:
    if not ids:
        return pd.DataFrame(columns=[
            "id","label","fish_code","nickname","name","genotype","genetic_background","stage","dob","created_at"
        ])
    q = text("""
      with picked as (select unnest(CAST(:ids as uuid[])) as id)
      select
        c.id_uuid                         as id,
        coalesce(c.label,'')              as label,
        f.fish_code,
        coalesce(f.nickname,'')           as nickname,
        coalesce(f.name,'')               as name,
        coalesce(v.genotype,'')           as genotype,
        coalesce(v.genetic_background,'') as genetic_background,
        coalesce(v.stage,'')              as stage,
        v.dob                              as dob,
        c.created_at
      from picked p
      join public.containers c on c.id_uuid = p.id
      left join public.fish_tank_memberships m on m.container_id = c.id_uuid and m.left_at is null
      left join public.fish f on f.id = m.fish_id
      left join public.v_fish_label_fields v on v.fish_code = f.fish_code
      order by c.created_at asc, c.label asc
    """)
    with ENGINE.begin() as c:
        df = pd.read_sql(q, c, params={"ids": ids})
    df["id"] = df["id"].astype(str)
    return df

def _base_label(lbl: str) -> str:
    s = (lbl or "").strip()
    if " #" not in s: return s
    try:
        head, tail = s.rsplit(" #", 1)
        int(tail); return head
    except Exception:
        return s

def _rows_for_print(df_run: pd.DataFrame, copy_meta: bool) -> List[Dict]:
    rows: List[Dict] = []
    by_base: Dict[str, Dict] = {}
    for _, r in df_run.iterrows():
        if r.get("fish_code"):
            by_base.setdefault(_base_label(r["label"]), dict(
                fish_code=_safe(r.get("fish_code")),
                nickname=_safe(r.get("nickname")),
                name=_safe(r.get("name")),
                genotype=_safe(r.get("genotype")),
                background=_safe(r.get("genetic_background")),
                stage=_safe(r.get("stage")),
                dob=_safe(r.get("dob")),
            ))
    for _, r in df_run.iterrows():
        label = _safe(r.get("label"))
        meta = dict(
            fish_code=_safe(r.get("fish_code")),
            nickname=_safe(r.get("nickname")),
            name=_safe(r.get("name")),
            genotype=_safe(r.get("genotype")),
            background=_safe(r.get("genetic_background")),
            stage=_safe(r.get("stage")),
            dob=_safe(r.get("dob")),
        )
        if copy_meta and not meta["fish_code"]:
            b = _base_label(label)
            meta.update({k:v for k,v in by_base.get(b, {}).items() if not meta.get(k)})
        rows.append({"label": label, **meta})
    return rows

def _render_full_label(c: _canvas.Canvas, r: Dict) -> None:
    x0, y0 = PAD_L, PAD_B
    w  = LABEL_W - PAD_L - PAD_R
    h  = LABEL_H - PAD_B - PAD_T
    qr_x, qr_y = x0 + w - QR_SIZE, y0
    text_w = w - QR_SIZE - QR_GAP

    combined = _safe(r.get("label"))
    mono = MONO_FONT_NAME or "Helvetica"

    lines = [
        ("nick", "Helvetica-Oblique", 9.0,  _safe(r.get("nickname")), 0.00),       # NICKNAME now black
        ("name", "Helvetica-Bold",   10.5,  _safe(r.get("name")),     0.00),       # NAME
        ("tank", "Helvetica-Bold",   11.0,  combined,                 0.00),       # BIG human label
        ("fish", mono,                9.5,  "",                       0.00),       # (blank fish line)
        ("geno", mono,                9.2,  _safe(r.get("genotype")), 0.00),       # GENOTYPE
        ("bg",   "Helvetica",         8.2,  _safe(r.get("background")),0.00),      # BACKGROUND
        ("stg",  "Helvetica",         8.2,  _safe(r.get("stage")),    0.00),       # STAGE
        ("dob",  "Helvetica",         8.2,  _safe(r.get("dob")),      0.00),       # DATE
    ]

    lane_h = h / len(lines)
    MIN_FS = 7.0
    TOP_PAD_FRAC = 0.82

    for i, (key, fn, fs, txt, gray) in enumerate(lines):
        lane_top = y0 + h - i * lane_h
        fs_lane = min(fs, max(MIN_FS, lane_h - 1.0))
        fs_use = fs_lane
        if key == "nick" and txt:
            while fs_use > MIN_FS and stringWidth(txt, fn, fs_use) > text_w:
                fs_use -= 0.3
        line = _ellipsize(txt or "", text_w, fn, fs_use)
        baseline = lane_top - (fs_use * TOP_PAD_FRAC)
        c.setFont(fn, fs_use)
        c.setFillGray(gray)
        c.drawString(x0, baseline, line)

    payload = _safe(r.get("fish_code")) or combined
    if payload:
        _draw_qr(c, payload, qr_x, qr_y, QR_SIZE)

def _build_labels_pdf(rows: List[Dict]) -> bytes:
    buf = BytesIO()
    c = _canvas.Canvas(buf, pagesize=(LABEL_W, LABEL_H))
    for r in rows:
        _render_full_label(c, r)
        c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()

# ---- fetch created tanks + summary + render ----
run_ids: List[str] = st.session_state.get("last_created_container_ids", [])
df_run = _fetch_created_tanks_with_fish(run_ids)

if df_run.empty:
    st.info("No tanks were created in this session yet. Create tanks above, then come back here to download labels.")
else:
    st.markdown("**Tanks created in this run**")
    show = df_run.rename(columns={
        "label":"Tank label","fish_code":"Fish","nickname":"Nickname","name":"Name",
        "genotype":"Genotype","genetic_background":"Background","stage":"Stage","dob":"DOB","created_at":"Created at"
    })
    cols = [c for c in ["Tank label","Fish","Nickname","Name","Genotype","Background","Stage","DOB","Created at"] if c in show.columns]
    st.dataframe(show[cols], use_container_width=True, hide_index=True)

    copy_meta = st.checkbox("Copy fish details to extra tanks (#2..#N) for printing", value=True)
    rows = _rows_for_print(df_run, copy_meta)

    pdf_bytes = _build_labels_pdf(rows)
    fname = f"tank_labels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    st.download_button(
        label="📥 Download PDF (2.4\"×1.5\"; 8-row layout + QR)",
        data=pdf_bytes,
        file_name=fname,
        mime="application/pdf",
        use_container_width=True,
        type="primary",
    )