from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

import os, json, io
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Register Clutches", page_icon="🍼")
st.title("🍼 Register Clutches — confirm crossing tanks & notes")

ENGINE = create_engine(os.environ["DB_URL"], pool_pre_ping=True)

# ============================== Generic helpers ===============================
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

# ========================= Crossing tanks / fishes / crosses ===================
def _current_tanks_for_fish_code(fish_code: str | None) -> pd.DataFrame:
    """Return current (open membership) tanks for a fish_code. Columns: id, label"""
    if not fish_code:
        return pd.DataFrame(columns=["id","label"])
    sql = text("""
      select c.id_uuid::text as id, coalesce(c.label,'') as label
      from public.fish f
      join public.fish_tank_memberships m
        on m.fish_id = f.id and m.left_at is null
      join public.containers c
        on c.id_uuid = m.container_id
      where f.fish_code = :code
      order by c.created_at
    """)
    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx, params={"code": fish_code})

def _get_crossing_tank_ids(run_id: str) -> tuple[str | None, str | None]:
    """Return (tank_a_id, tank_b_id) for a crossing tank row (cross_plan_runs.id)."""
    sql = text("select tank_a_id::text as a, tank_b_id::text as b from public.cross_plan_runs where id = :id")
    with ENGINE.begin() as cx:
        row = cx.execute(sql, {"id": run_id}).fetchone()
    return (row[0] if row and row[0] else None, row[1] if row and row[1] else None)

def _default_index(cur_id: str | None, id_list: list[str | None]) -> int:
    """Index for selectbox default; 0 if not present."""
    try:
        return id_list.index(cur_id) if cur_id in id_list else 0
    except Exception:
        return 0

def _load_crossing_tanks(d0: date, d1_excl: date) -> pd.DataFrame:
    """
    Load crossing tanks (aka cross plan runs) for a date range from v_cross_plan_runs_enriched.
    Expected columns include:
      id, planned_date, plan_title, plan_nickname, mother_fish_code, father_fish_code,
      seq, tank_a_label, tank_b_label, status
    """
    sql = text("""
      select *
      from public.v_cross_plan_runs_enriched
      where planned_date >= :d0 and planned_date < :d1
      order by planned_date asc, plan_title nulls last, seq asc
    """)
    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx, params={"d0": d0, "d1": d1_excl})

def _confirm_crossing_tank(run_id: str, tank_a_id: str | None, tank_b_id: str | None) -> None:
    sql = text("""
      update public.cross_plan_runs
      set tank_a_id = :a, tank_b_id = :b
      where id = :id
    """)
    with ENGINE.begin() as cx:
        cx.execute(sql, {"a": tank_a_id, "b": tank_b_id, "id": run_id})

def _get_run_plan_id(run_id: str) -> str | None:
    """Return the cross plan id for a crossing-tank row (cross_plan_runs.plan_id)."""
    sql = text("select plan_id::text from public.cross_plan_runs where id = :id")
    with ENGINE.begin() as cx:
        row = cx.execute(sql, {"id": run_id}).fetchone()
    return row[0] if row else None

def _ensure_cross_for_run(run_id: str, created_by: str) -> str:
    """
    Ensure there is a row in public.crosses for this crossing tank:
    mom_code + dad_code + planned_for (from v_cross_plan_runs_enriched).
    If not found, create it. Return its id_uuid.
    """
    sql_run = text("""
      select mother_fish_code, father_fish_code, planned_date
      from public.v_cross_plan_runs_enriched
      where id = :id
      limit 1
    """)
    with ENGINE.begin() as cx:
        rr = cx.execute(sql_run, {"id": run_id}).fetchone()
    if not rr:
        raise RuntimeError("Could not load crossing-tank info for run_id")

    mom_code, dad_code, planned_for = rr[0], rr[1], rr[2]

    sql_find = text("""
      select id_uuid
      from public.crosses
      where mother_code = :m
        and father_code = :f
        and planned_for = :d
      order by created_at desc
      limit 1
    """)
    with ENGINE.begin() as cx:
        found = cx.execute(sql_find, {"m": mom_code, "f": dad_code, "d": planned_for}).fetchone()
    if found and found[0]:
        return str(found[0])

    sql_ins = text("""
      insert into public.crosses (mother_code, father_code, created_by, planned_for)
      values (:m, :f, :by, :d)
      returning id_uuid
    """)
    with ENGINE.begin() as cx:
        row = cx.execute(sql_ins, {"m": mom_code, "f": dad_code, "by": created_by, "d": planned_for}).fetchone()
    return str(row[0])

# ========================= Clutch insert + label helpers ======================
def _register_clutch_with_birthday(
    run_id: str,
    birthday: date | None,
    notes: str | None,
    created_by: str,
) -> tuple[bool, str]:
    """
    Insert a clutch:
    - Writes birthday into clutches.date_birth (single clutch date).
    - Links to the crossing-tank row via run FK (run_id or cross_plan_run_id).
    - If clutches.cross_id exists (FK to public.crosses), ensure a crosses row exists and use that id.
    Returns (True, inserted_id) if an id column exists, else (True, 'ok').
    """
    # 1) Detect FK column to the run
    if _table_has_columns("clutches", "run_id"):
        run_fk_col = "run_id"
    elif _table_has_columns("clutches", "cross_plan_run_id"):
        run_fk_col = "cross_plan_run_id"
    else:
        return False, "clutches table missing run FK (expected run_id or cross_plan_run_id)."

    # 2) Ensure clutches.date_birth exists
    if not _table_has_columns("clutches", "date_birth"):
        return False, "clutches.date_birth is missing; run the migration to keep only date_birth."

    # 3) cross_id support
    have_cross_id = _table_has_columns("clutches", "cross_id")
    cross_id_val = None
    if have_cross_id:
        try:
            cross_id_val = _ensure_cross_for_run(run_id, created_by=created_by)
        except Exception as e:
            return False, f"could not ensure crosses row for this run: {e}"

    # 4) Build dynamic insert
    cols = [run_fk_col, "date_birth", "note", "created_by"]
    vals = [":rid", ":bd", ":note", ":by"]
    params = {"rid": run_id, "bd": birthday, "note": notes, "by": created_by}

    if have_cross_id:
        cols.insert(1, "cross_id")
        vals.insert(1, ":cid")
        params["cid"] = cross_id_val

    col_sql = ", ".join(cols)
    val_sql = ", ".join(vals)

    # 5) Choose a PK to RETURN if available
    pk_col = _first_existing_column("clutches", ["id", "id_uuid", "clutch_id"])
    if pk_col:
        sql = text(f"""
          insert into public.clutches ({col_sql})
          values ({val_sql})
          returning {pk_col}
        """)
        with ENGINE.begin() as cx:
            row = cx.execute(sql, params).fetchone()
        return True, (str(row[0]) if row else "ok")
    else:
        sql = text(f"""
          insert into public.clutches ({col_sql})
          values ({val_sql})
        """)
        with ENGINE.begin() as cx:
            cx.execute(sql, params)
        return True, "ok"

def _get_run_genotype_treatments(run_id: str) -> tuple[str, str]:
    """
    Return (genotype_text, treatments_text) for a crossing tank by joining its plan.
    """
    with ENGINE.begin() as cx:
        plan_id = cx.execute(text("select plan_id::text from public.cross_plan_runs where id=:id"), {"id": run_id}).scalar()
    if not plan_id:
        return "", ""

    sql_g = text("""
      select coalesce(string_agg(
               format('%s[%s]%s',
                      ga.transgene_base_code,
                      ga.allele_number,
                      coalesce(' '||ga.zygosity_planned,'')
               ),
               ', ' order by ga.transgene_base_code, ga.allele_number
             ), '') as gtxt
      from public.cross_plan_genotype_alleles ga
      where ga.plan_id = :pid
    """)
    sql_t = text("""
      select coalesce(string_agg(
               trim(both ' ' from concat(
                 coalesce(ct.treatment_name,''),
                 case when coalesce(ct.injection_mix,'')  <> '' then ' (mix='||ct.injection_mix||')' else '' end,
                 case when coalesce(ct.treatment_notes,'')<> '' then ' ['||ct.treatment_notes||']' else '' end,
                 case when coalesce(ct.timing_note,'')    <> '' then ' {'||ct.timing_note||'}' else '' end
               )),
               ' • ' order by coalesce(ct.treatment_name,''), coalesce(ct.rna_id::text,''), coalesce(ct.plasmid_id::text,'')
             ), '') as ttxt
      from public.cross_plan_treatments ct
      where ct.plan_id = :pid
    """)
    with ENGINE.begin() as cx:
        gtxt = cx.execute(sql_g, {"pid": plan_id}).scalar() or ""
        ttxt = cx.execute(sql_t, {"pid": plan_id}).scalar() or ""
    return gtxt, ttxt

def _to_base36(n: int, width: int = 4) -> str:
    """Return n as zero-padded base-36 (0-9A-Z)."""
    if n < 0:
        n = 0
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = digits[r] + out
    out = out or "0"
    return out.rjust(width, "0")

def _make_clutch_code(inserted_id: str, birthday: date) -> str:
    """
    Generate CLUTCH-YYXXXX where:
      YY   = two-digit year
      XXXX = base36 value derived from the inserted clutch id modulo 36^4
    """
    yy = f"{birthday.year % 100:02d}"
    try:
        seed = int(inserted_id.replace("-", ""), 16)
    except Exception:
        seed = abs(hash(inserted_id))
    suffix = _to_base36(seed % (36 ** 4), 4)
    return f"CLUTCH-{yy}{suffix}"

def _render_petri_labels_pdf(label_rows: list[dict]) -> bytes:
    """
    Render petri-dish labels as a PDF, 2.4in x 0.75in each (no QR).
    Fields used per row:
      clutch_code, nickname/label, mom, dad, birthday, genotype, treatments, user
    Width-aware: lines are ellipsized to fit the printable area (no clipping).
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import inch
        from reportlab.pdfbase.pdfmetrics import stringWidth
    except Exception as e:
        raise RuntimeError("reportlab is required for inline PDF rendering") from e

    # Page + margins
    W, H = 2.4 * inch, 0.75 * inch   # 172.8 x 54.0 pt
    LEFT, RIGHT = 6, 6               # add a small right padding to prevent chop
    MAXW = W - LEFT - RIGHT

    def _fit(text: str, font: str, size: float, maxw: float) -> str:
        """Return text or its ellipsized form so that it fits within maxw."""
        if not text:
            return ""
        if stringWidth(text, font, size) <= maxw:
            return text
        # ellipsize by binary-search truncation
        lo, hi = 0, len(text)
        ell = "…"
        while lo < hi:
            mid = (lo + hi) // 2
            if stringWidth(text[:mid] + ell, font, size) <= maxw:
                lo = mid + 1
            else:
                hi = mid
        cut = max(0, lo - 1)
        return (text[:cut] + ell) if cut > 0 else ell

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))

    for r in label_rows:
        clutch_code = (r.get("clutch_code") or "").strip()
        title       = (r.get("nickname") or r.get("label") or "").strip()
        mom         = (r.get("mom") or "").strip()
        dad         = (r.get("dad") or "").strip()
        bday        = (r.get("birthday") or "").strip()
        genotype    = (r.get("genotype") or "").strip()
        treatments  = (r.get("treatments") or "").strip()
        user        = (r.get("user") or "").strip()

        # Compose lines (at most 5 lines in 0.75" height)
        # L1: clutch code
        c.setFont("Helvetica-Bold", 9)
        c.drawString(LEFT, H-12, _fit(clutch_code, "Helvetica-Bold", 9, MAXW))

        # L2: nickname/title
        c.setFont("Helvetica-Bold", 9)
        c.drawString(LEFT, H-23, _fit(title, "Helvetica-Bold", 9, MAXW))

        # L3: parents + birthday
        c.setFont("Helvetica", 8)
        line3 = f"{mom} × {dad}  {bday}".strip()
        c.drawString(LEFT, H-33, _fit(line3, "Helvetica", 8, MAXW))

        # L4: genotype
        if genotype:
            c.setFont("Helvetica", 7)
            c.drawString(LEFT, H-42, _fit(genotype, "Helvetica", 7, MAXW))

        # L5: treatments + user
        if treatments or user:
            c.setFont("Helvetica", 7)
            tail = treatments
            if user:
                tail = (tail + ("  •  " if tail else "") + user)
            c.drawString(LEFT, H-51, _fit(tail, "Helvetica", 7, MAXW))

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.getvalue()

# ============================== Pick day ==============================
default_day = None
try:
    qp = st.query_params
    if "report_day" in qp:
        default_day = pd.to_datetime(qp["report_day"]).date()
except Exception:
    default_day = None

rep_day = st.date_input("Report day (saved as clutch birthday)", value=default_day or date.today())

# Load daily crossing tanks and cast id->str for Streamlit/PyArrow
df_day = _load_crossing_tanks(rep_day, rep_day + timedelta(days=1))
if not df_day.empty:
    df_day["id"] = df_day["id"].astype(str)

# ================== Register clutch for a crossing tank ==================
st.subheader("Register clutch for a crossing tank")

if df_day.empty:
    st.info("No crossing tanks for this date.")
else:
    table = df_day[[
        "id","planned_date","plan_title","plan_nickname",
        "mother_fish_code","father_fish_code","seq",
        "tank_a_label","tank_b_label","status"
    ]].rename(columns={
        "planned_date":"Date",
        "plan_title":"Name",
        "plan_nickname":"Nickname",
        "mother_fish_code":"Mom fish",
        "father_fish_code":"Dad fish",
        "tank_a_label":"Tank A (intended)",
        "tank_b_label":"Tank B (intended)",
    }).reset_index(drop=True)

    try:
        table["Date"] = pd.to_datetime(table["Date"]).dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    table["Register"] = False
    disp = table.set_index("id")[[
        "Register","Date","Name","Nickname","Mom fish","Dad fish","seq",
        "Tank A (intended)","Tank B (intended)","status"
    ]]
    sel = st.data_editor(
        disp,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={"Register": st.column_config.CheckboxColumn("Register", default=False)},
        key="reg_table",
    )
    chosen_ids = [idx for idx, r in sel.iterrows() if r.get("Register")]

    if not chosen_ids:
        st.info("Tick one row above to change crossing tank info (if needed) and add clutch notes.")
    else:
        run_id = chosen_ids[0]
        row = df_day.loc[df_day["id"] == run_id].iloc[0]
        mom_code = row.get("mother_fish_code")
        dad_code = row.get("father_fish_code")
        seq_val  = int(row.get("seq") or 0)

        st.markdown(f"**Selected:** {row.get('plan_title') or '—'} — {mom_code or '—'} × {dad_code or '—'} (seq {seq_val})")

        # ---- optional tank change ----
        with st.expander("Change crossing tank info"):
            st.caption("Use this only if the intended tanks above are incorrect.")
            mom_tanks = _current_tanks_for_fish_code(mom_code)
            dad_tanks = _current_tanks_for_fish_code(dad_code)
            mom_labels = ["—"] + [f"{r.label or '—'} · {r.id[:8]}…" for _, r in mom_tanks.iterrows()]
            mom_ids    = [None] + mom_tanks["id"].tolist()
            dad_labels = ["—"] + [f"{r.label or '—'} · {r.id[:8]}…" for _, r in dad_tanks.iterrows()]
            dad_ids    = [None] + dad_tanks["id"].tolist()
            cur_a_id, cur_b_id = _get_crossing_tank_ids(run_id)

            c1, c2 = st.columns([1,1])
            with c1:
                a_idx = st.selectbox(
                    f"Tank A (Mom: {mom_code or '—'})",
                    options=range(len(mom_ids)),
                    format_func=lambda j: mom_labels[j],
                    index=_default_index(cur_a_id, mom_ids),
                    key="ct_confA_day",
                )
            with c2:
                b_idx = st.selectbox(
                    f"Tank B (Dad: {dad_code or '—'})",
                    options=range(len(dad_ids)),
                    format_func=lambda j: dad_labels[j],
                    index=_default_index(cur_b_id, dad_ids),
                    key="ct_confB_day",
                )
            a_id, b_id = mom_ids[a_idx], dad_ids[b_idx]

            if st.button("Save crossing tanks", use_container_width=True, key="save_ct",
                         disabled=(a_id and b_id and a_id == b_id)):
                if a_id and b_id and a_id == b_id:
                    st.warning("Tank A and Tank B must be different.")
                else:
                    _confirm_crossing_tank(run_id, a_id, b_id)
                    st.success("Crossing tanks saved.")

        st.markdown("---")

        # ---- clutch notes + actions ----
        st.markdown("**Clutch notes**")
        clutch_notes = st.text_area("Notes", value="", key="clutch_notes")

        bcols = st.columns([1,1])
        with bcols[0]:
            if st.button("Save clutch", type="primary", use_container_width=True, key="save_clutch"):
                ok, msg = _register_clutch_with_birthday(
                    run_id=run_id, birthday=rep_day, notes=clutch_notes, created_by=os.getenv("USER","unknown")
                )
                if ok:
                    st.success(f"Clutch saved (id: {msg}).")
                else:
                    st.warning(f"Could not write to clutches table: {msg}")
                    st.code(json.dumps({
                        "run_id": run_id,
                        "date_birth": str(rep_day),
                        "notes": clutch_notes,
                        "created_by": os.getenv("USER","unknown"),
                    }, indent=2))

        with bcols[1]:
            if st.button("Save clutch + download petri-dish label (PDF)", type="primary",
                         use_container_width=True, key="save_clutch_print"):
                user_name = os.getenv("USER","unknown")
                ok, inserted_id = _register_clutch_with_birthday(
                    run_id=run_id, birthday=rep_day, notes=clutch_notes, created_by=user_name
                )
                if ok:
                    # clutch code + genotype/treatments for label
                    clutch_code = _make_clutch_code(inserted_id, rep_day)
                    geno, tx    = _get_run_genotype_treatments(run_id)

                    label_rows = [{
                        "run_id": run_id,
                        "birthday": str(rep_day),
                        "label": f"{row.get('plan_title') or ''}",
                        "nickname": row.get("plan_nickname") or "",
                        "mom": mom_code or "",
                        "dad": dad_code or "",
                        "clutch_code": clutch_code,
                        "genotype": geno,
                        "treatments": tx,
                        "user": user_name,
                    }]
                    try:
                        pdf_bytes = _render_petri_labels_pdf(label_rows)
                        st.download_button(
                            "Download petri-dish label PDF",
                            data=pdf_bytes,
                            file_name=f"{clutch_code}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                        st.success(f"Clutch saved (id: {inserted_id}). PDF ready to download.")
                    except Exception as e:
                        st.error(f"Could not render PDF inline: {e}")
                else:
                    st.warning(f"Could not write to clutches table: {inserted_id}")
                    st.code(json.dumps({
                        "run_id": run_id,
                        "date_birth": str(rep_day),
                        "notes": clutch_notes,
                        "created_by": user_name,
                    }, indent=2))