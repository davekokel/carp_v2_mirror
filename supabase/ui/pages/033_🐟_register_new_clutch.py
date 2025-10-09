# supabase/ui/pages/033_🍼_register_clutches.py
from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

import os, io, json
from datetime import date, timedelta
from typing import Dict, Any, List

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Register Clutches", page_icon="🍼", layout="wide")
st.title("🍼 Register Clutches — record size/notes and print Petri labels")

ENGINE = create_engine(os.environ["DB_URL"], pool_pre_ping=True)

# -------------------- small helpers --------------------
def _ensure_cross_for_planned(planned_cross_id: str, created_by: str) -> str:
    """
    Given a planned_crosses.id_uuid, ensure a row exists in public.crosses
    with (mother_code, father_code, planned_for) = (mom_code, dad_code, cross_date).
    Return crosses.id_uuid (as text).
    """
    # Load mom/dad/date from planned_crosses
    sql_load = text("""
      select mom_code, dad_code, cross_date
      from public.planned_crosses
      where id_uuid = cast(:pid as uuid)
      limit 1
    """)
    with ENGINE.begin() as cx:
        row = cx.execute(sql_load, {"pid": planned_cross_id}).mappings().first()
    if not row:
        raise RuntimeError(f"planned_crosses row not found: {planned_cross_id}")

    mom_code = row["mom_code"]
    dad_code = row["dad_code"]
    planned_for = pd.to_datetime(row["cross_date"]).date() if row["cross_date"] else None

    # Try to find an existing crosses row
    sql_find = text("""
      select id_uuid::text
      from public.crosses
      where mother_code = :m and father_code = :f and planned_for is not distinct from :d
      order by created_at desc
      limit 1
    """)
    with ENGINE.begin() as cx:
        found = cx.execute(sql_find, {"m": mom_code, "f": dad_code, "d": planned_for}).scalar()

    if found:
        return str(found)

    # Insert a new crosses row
    sql_ins = text("""
      insert into public.crosses (mother_code, father_code, planned_for, created_by)
      values (:m, :f, :d, :by)
      returning id_uuid::text
    """)
    with ENGINE.begin() as cx:
        rid = cx.execute(sql_ins, {"m": mom_code, "f": dad_code, "d": planned_for, "by": created_by}).scalar()
    return str(rid)

def _table_has_columns(table: str, *cols: str) -> bool:
    sql = text("""
      select 1
      from information_schema.columns
      where table_schema='public'
        and table_name=:t
        and column_name = any(:cols)
      limit 1
    """)
    with ENGINE.begin() as cx:
        row = cx.execute(sql, {"t": table, "cols": list(cols)}).fetchone()
    return bool(row)

def _first_existing_column(table: str, candidates: list[str]) -> str | None:
    sql = text("""
      select column_name
      from information_schema.columns
      where table_schema='public'
        and table_name=:t
        and column_name = any(:cols)
      order by array_position(:cols, column_name)
      limit 1
    """)
    with ENGINE.begin() as cx:
        row = cx.execute(sql, {"t": table, "cols": candidates}).fetchone()
    return row[0] if row else None

def _to_base36(n: int, width: int = 4) -> str:
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if n < 0: n = 0
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = digits[r] + out
    out = out or "0"
    return out.rjust(width, "0")

def _make_clutch_code(inserted_id: str, birthday: date) -> str:
    yy = f"{birthday.year % 100:02d}"
    try:
        seed = int(inserted_id.replace("-", ""), 16)
    except Exception:
        seed = abs(hash(inserted_id))
    suffix = _to_base36(seed % (36 ** 4), 4)
    return f"CLUTCH-{yy}{suffix}"

# -------------------- load crosses for a date --------------------
def _load_crosses_for_birthdate(d: date, q: str, limit: int = 1000) -> pd.DataFrame:
    """
    Crosses scheduled on this day from planned_crosses.
    """
    sql = text("""
      select
        pc.id_uuid::text                         as cross_id,
        coalesce(pc.cross_code, pc.id_uuid::text) as cross_code,
        pc.mom_code,
        pc.dad_code,
        pc.mother_tank_id::text                  as mother_tank_id,
        cm.label                                 as mother_tank,
        pc.father_tank_id::text                  as father_tank_id,
        cf.label                                 as father_tank,
        pc.cross_date,
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
            "d0": pd.to_datetime(d).date(),
            "d1": (pd.to_datetime(d).date() + timedelta(days=1)),
            "q": q or "", "qlike": f"%{q or ''}%", "lim": int(limit),
        })

# -------------------- save clutch rows --------------------
def _save_clutches(rows: pd.DataFrame, birthday: date, created_by: str) -> List[str]:
    """
    Insert into public.clutches:
      - cross_id FK must point to public.crosses(id_uuid), not planned_crosses.
      - We map each planned_crosses.id -> (ensure/create) crosses row and use that id.
    Requires clutches(cross_id uuid, date_birth date). Optionally uses size, description, note, created_by.
    Returns list of inserted PKs if available; else [].
    """
    if not _table_has_columns("clutches", "cross_id", "date_birth"):
        st.error("Table public.clutches must have columns: cross_id (uuid), date_birth (date). Add migrations first.")
        return []

    pk_col  = _first_existing_column("clutches", ["id_uuid", "id", "clutch_id"])
    has_size = _table_has_columns("clutches", "size")
    has_desc = _table_has_columns("clutches", "description")
    has_note = _table_has_columns("clutches", "note")
    has_by   = _table_has_columns("clutches", "created_by")

    cols, vals = ["cross_id", "date_birth"], ["cast(:cross_id as uuid)", ":date_birth"]
    if has_size: cols.append("size");        vals.append(":size")
    if has_desc: cols.append("description"); vals.append(":description")
    if has_note: cols.append("note");        vals.append(":note")
    if has_by:   cols.append("created_by");  vals.append(":by")

    sql = f"insert into public.clutches ({', '.join(cols)}) values ({', '.join(vals)})"
    if pk_col:
        sql += f" returning {pk_col}"
    ins = text(sql)

    inserted: List[str] = []
    with ENGINE.begin() as cx:
        pass  # we just open/close to confirm connection; real inserts happen below

    for _, r in rows.iterrows():
        # NOTE: rows['cross_id'] currently holds planned_crosses.id_uuid from your selection table.
        planned_id = str(r["cross_id"])
        # Ensure/resolve a public.crosses.id_uuid
        cross_fk = _ensure_cross_for_planned(planned_id, created_by=created_by)

        params = {
            "cross_id":    cross_fk,  # <-- FK now points to public.crosses
            "date_birth":  pd.to_datetime(birthday).date(),
            "size":        int(r["size"]) if has_size and pd.notna(r.get("size")) else None,
            "description": (str(r.get("description")) if has_desc else None),
            "note":        (str(r.get("note")) if has_note else None),
            "by":          created_by if has_by else None,
        }
        if pk_col:
            with ENGINE.begin() as cx:
                rid = cx.execute(ins, params).scalar()
            inserted.append(str(rid))
        else:
            with ENGINE.begin() as cx:
                cx.execute(ins, params)

    return inserted

# -------------------- tiny label pdf for Petri dishes --------------------
def _render_petri_labels_pdf(label_rows: list[dict]) -> bytes:
    """
    Render petri-dish labels as a PDF, 2.4in x 0.75in (no QR).
    EXACTLY one field per line, in this order:
      1: clutch_code
      2: nickname/title
      3: mom × dad
      4: birthday (YYYY-MM-DD)
      5: genotype
      6: treatments • user
    All lines are end-ellipsized to fit the printable width.
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import inch
        from reportlab.pdfbase.pdfmetrics import stringWidth
    except Exception as e:
        raise RuntimeError("reportlab is required for inline PDF rendering") from e

    # Geometry
    W, H = 2.4 * inch, 0.75 * inch          # 172.8 x 54.0 pt
    PAD_L, PAD_R, PAD_T, PAD_B = 6, 6, 4, 4 # tight but safe margins
    MAXW = W - PAD_L - PAD_R

    # Typography (fits 6 lines in 0.75")
    FS_H = 8.8   # header lines (1–2)
    FS_B = 7.4   # body lines (3–6)
    STEP = 7.6   # vertical step between lines

    def _fit(text: str, font: str, size: float, maxw: float) -> str:
        """End-ellipsize to fit width."""
        s = (text or "").strip()
        if not s or stringWidth(s, font, size) <= maxw:
            return s
        ell = "…"
        lo, hi = 0, len(s)
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
        # Gather fields (stringify defensively)
        clutch_code = str(r.get("clutch_code") or "").strip()
        title       = str(r.get("nickname") or r.get("label") or "").strip()
        mom         = str(r.get("mom") or "").strip()
        dad         = str(r.get("dad") or "").strip()
        birthday    = str(r.get("birthday") or "").strip()
        genotype    = str(r.get("genotype") or "").strip()
        treatments  = str(r.get("treatments") or "").strip()
        user        = str(r.get("user") or "").strip()
        tail        = (treatments + ((" • " + user) if user else "")).strip()

        # Compute y starting point
        y = H - PAD_T - FS_H

        # L1: clutch_code
        c.setFont("Helvetica-Bold", FS_H)
        c.drawString(PAD_L, y, _fit(clutch_code, "Helvetica-Bold", FS_H, MAXW))

        # L2: nickname/title
        y -= STEP
        c.setFont("Helvetica-Bold", FS_H)
        c.drawString(PAD_L, y, _fit(title, "Helvetica-Bold", FS_H, MAXW))

        # L3: parents (mom × dad)
        y -= STEP
        c.setFont("Helvetica", FS_B)
        parents = (mom + " × " + dad).strip(" ×")
        c.drawString(PAD_L, y, _fit(parents, "Helvetica", FS_B, MAXW))

        # L4: birthday (YYYY-MM-DD)
        y -= STEP
        c.setFont("Helvetica", FS_B)
        c.drawString(PAD_L, y, _fit(birthday, "Helvetica", FS_B, MAXW))

        # L5: genotype (may be long)
        y -= STEP
        if genotype:
            c.setFont("Helvetica", FS_B)
            c.drawString(PAD_L, y, _fit(genotype, "Helvetica", FS_B, MAXW))
        else:
            # keep vertical rhythm even if empty
            c.setFont("Helvetica", FS_B)
            c.drawString(PAD_L, y, "")

        # L6: treatments • user
        y -= STEP
        c.setFont("Helvetica", FS_B)
        c.drawString(PAD_L, y, _fit(tail, "Helvetica", FS_B, MAXW))

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.getvalue()

# ============================== UI ==============================
st.subheader("Step 1 — Pick date (clutch birthday)")
cA, cB = st.columns([2,2])
with cA:
    rep_day = st.date_input("Clutch birthday", value=date.today())
with cB:
    q = st.text_input("Filter (clutch / name / mom / dad / tank label)", "")

df_crosses = _load_crosses_for_birthdate(rep_day, q)
st.caption(f"{len(df_crosses)} cross(es) scheduled on {rep_day}")

if df_crosses.empty:
    st.info("No crosses for this date.")
    st.stop()

# editor with size/description/note per selected
st.subheader("Step 2 — Select crosses and enter clutch fields")
work = df_crosses.copy()
work.insert(0, "✓ Save", False)
work["size"] = None
work["description"] = ""
work["note"] = ""

order = ["✓ Save","cross_code","clutch_code","planned_name",
         "mom_code","mother_tank","dad_code","father_tank",
         "size","description","note"]

edited = st.data_editor(
    work,
    use_container_width=True, hide_index=True,
    column_order=order,
    column_config={
        "✓ Save":        st.column_config.CheckboxColumn("✓ Save", default=False),
        "cross_code":    st.column_config.TextColumn("cross_code", disabled=True),
        "clutch_code":   st.column_config.TextColumn("clutch_code", disabled=True),
        "planned_name":  st.column_config.TextColumn("planned_name", disabled=True),
        "mom_code":      st.column_config.TextColumn("mom_code", disabled=True),
        "mother_tank":   st.column_config.TextColumn("mother_tank", disabled=True),
        "dad_code":      st.column_config.TextColumn("dad_code", disabled=True),
        "father_tank":   st.column_config.TextColumn("father_tank", disabled=True),
        "size":          st.column_config.NumberColumn("size", min_value=0, max_value=100000, step=1),
        "description":   st.column_config.TextColumn("description"),
        "note":          st.column_config.TextColumn("note"),
    },
    key="clutch_register_editor",
)

to_save = edited[edited["✓ Save"]].copy()
if to_save.empty:
    st.info("Tick rows to save clutches, then use the buttons below.")
    st.stop()

# ================== actions ==================
st.subheader("Step 3 — Save and (optionally) print labels")
colL, colR = st.columns([1,1])
with colL:
    if st.button("💾 Save clutches", type="primary", use_container_width=True):
        inserted = _save_clutches(to_save, rep_day, created_by=os.getenv("USER","unknown"))
        if inserted:
            st.success(f"Saved {len(inserted)} clutches.")
        else:
            st.success(f"Saved {len(to_save)} clutches.")
with colR:
    if st.button("💾 Save + ⬇️ Petri labels (PDF)", type="primary", use_container_width=True):
        user_name = os.getenv("USER","unknown")
        inserted = _save_clutches(to_save, rep_day, created_by=user_name)
        if not inserted and not _first_existing_column("clutches", ["id_uuid","id","clutch_id"]):
            st.error("Saved clutches, but could not determine IDs to build codes for labels.")
        else:
            # build label rows using either returned ids or re-query by (cross_id, date)
            ids = inserted
            if not ids:
                # fallback: nothing returned; just synthesize codes with a stable seed
                ids = [str(i) for i in range(len(to_save))]
            label_rows: List[Dict[str, Any]] = []
            for ix, (_, r) in enumerate(to_save.iterrows()):
                inserted_id = ids[ix] if ix < len(ids) else str(ix)
                label_rows.append({
                    "clutch_code": _make_clutch_code(inserted_id, rep_day),
                    "label": r.get("planned_name") or "",
                    "nickname": r.get("planned_name") or "",
                    "mom": r.get("mom_code") or "",
                    "dad": r.get("dad_code") or "",
                    "birthday": rep_day.strftime("%Y-%m-%d"),
                    "genotype": "",      # optional: derive from planned_name right-side if desired
                    "treatments": "",    # optional: bring in from clutch_plans if desired
                    "user": user_name,
                })
            try:
                pdf_bytes = _render_petri_labels_pdf(label_rows)
                st.download_button("Download Petri labels (PDF)", data=pdf_bytes,
                                   file_name=f"petri_labels_{rep_day}.pdf", mime="application/pdf",
                                   use_container_width=True)
                st.success(f"Saved {len(to_save)} clutches. PDF ready to download.")
            except Exception as e:
                st.error(f"Could not render PDF: {e}")

st.code(json.dumps({
    "save_count": int(to_save.shape[0]),
    "birthday": str(rep_day),
    "sample_row": (to_save.head(1).to_dict(orient="records")[0] if not to_save.empty else {}),
}, indent=2, default=str))