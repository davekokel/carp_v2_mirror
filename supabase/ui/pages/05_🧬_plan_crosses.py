from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

import os, json, uuid
from datetime import date, timedelta
from typing import Optional, Tuple, List, Dict
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

PAGE_TITLE = "Plan Crosses — 0→7"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🧬")
st.title("🧬 Plan Crosses — 0→7")

# ---------- DB / Engine ----------
def _db_url() -> str:
    u = os.environ.get("DB_URL", "")
    if not u:
        raise RuntimeError("DB_URL not set")
    return u

ENGINE = create_engine(_db_url(), pool_pre_ping=True)

# ---------- Loaders ----------
def _load_inventory_tanks() -> pd.DataFrame:
    q = text("""
      select
        id_uuid as id,
        label,
        container_type,
        status,
        created_at
      from public.v_containers_crossing_candidates
      where container_type = 'inventory_tank'
      order by coalesce(label,'') asc, created_at asc
    """)
    with ENGINE.begin() as c:
        try:
            df = pd.read_sql(q, c)
        except Exception:
            # fall back to containers if the view is missing
            q2 = text("""
              select id_uuid as id, label, container_type, status, created_at
              from public.containers
              where container_type = 'inventory_tank'
              order by coalesce(label,'') asc, created_at asc
            """)
            df = pd.read_sql(q2, c)
    df["id"] = df["id"].astype(str)
    return df

def _load_allele_catalog() -> pd.DataFrame:
    q = text("""
      select ta.transgene_base_code as base_code,
             ta.allele_number,
             coalesce(ar.allele_nickname, ta.allele_nickname) as nickname
      from public.transgene_alleles ta
      left join public.transgene_allele_registry ar
        on ar.transgene_base_code = ta.transgene_base_code
       and ar.allele_number        = ta.allele_number
      order by base_code, allele_number
    """)
    with ENGINE.begin() as c:
        df = pd.read_sql(q, c)
    return df

def _load_enriched_plans(created_by: str, d0: date, d1_excl: date) -> pd.DataFrame:
    q = text("""
      select *
      from public.v_cross_plans_enriched
      where created_by = :by
        and plan_date >= :d0
        and plan_date <  :d1
      order by plan_date asc, tank_a_label asc, tank_b_label asc
    """)
    with ENGINE.begin() as c:
        df = pd.read_sql(q, c, params=dict(by=created_by, d0=d0, d1=d1_excl))
    return df

# ---------- Writers ----------
def _insert_cross_plan(plan_date: date, tank_a_id: str, tank_b_id: str, created_by: str, note: Optional[str]) -> Tuple[bool, Optional[str]]:
    q = text("""
      insert into public.cross_plans (plan_date, tank_a_id, tank_b_id, created_by, note)
      values (:d, :a, :b, :by, :note)
      on conflict (plan_date, tank_a_id, tank_b_id) do nothing
      returning id
    """)
    with ENGINE.begin() as c:
        row = c.execute(q, dict(d=plan_date, a=tank_a_id, b=tank_b_id, by=created_by, note=note)).fetchone()
        if row:
            return True, str(row[0])
        # fetch id if it already existed
        row2 = c.execute(text("""
          select id from public.cross_plans
          where plan_date=:d and tank_a_id=:a and tank_b_id=:b
          limit 1
        """), dict(d=plan_date, a=tank_a_id, b=tank_b_id)).fetchone()
        return False, (str(row2[0]) if row2 else None)

def _upsert_plan_genotypes(plan_id: str, rows: List[dict]) -> int:
    if not rows:
        return 0
    with ENGINE.begin() as c:
        n = 0
        for r in rows:
            c.execute(text("""
              insert into public.cross_plan_genotype_alleles (plan_id, transgene_base_code, allele_number, zygosity_planned)
              values (:pid, :bc, :num, :zyg)
              on conflict (plan_id, transgene_base_code, allele_number) do update
                set zygosity_planned = excluded.zygosity_planned
            """), dict(pid=plan_id, bc=r["base_code"], num=int(r["allele_number"]), zyg=r.get("zygosity_planned")))
            n += 1
    return n

def _upsert_plan_treatments(plan_id: str, rows: List[dict]) -> int:
    if not rows:
        return 0
    with ENGINE.begin() as c:
        n = 0
        for r in rows:
            c.execute(text("""
              insert into public.cross_plan_treatments (id, plan_id, treatment_name, amount, units, timing_note)
              values (:id, :pid, :name, :amt, :units, :note)
              on conflict do nothing
            """), dict(
                id=str(uuid.uuid4()),
                pid=plan_id,
                name=r["treatment_name"],
                amt=r.get("amount"),
                units=r.get("units"),
                note=r.get("timing_note"),
            ))
            n += 1
    return n

def _enqueue_tank_labels_for_plans(created_by: str, df_enriched: pd.DataFrame, title_note: str) -> Optional[str]:
    if df_enriched.empty:
        return None
    job_id = str(uuid.uuid4())
    payloads: List[Dict] = []
    for _, r in df_enriched.iterrows():
        label = (r.get("genotype_plan") or "").strip()
        payloads.append(dict(tank_label=r.get("tank_a_label") or "", role="Tank A", genotype=label, plan_date=str(r["plan_date"])))
        payloads.append(dict(tank_label=r.get("tank_b_label") or "", role="Tank B", genotype=label, plan_date=str(r["plan_date"])))
    with ENGINE.begin() as c:
        c.execute(text("""
          insert into public.label_jobs (id_uuid, entity_type, entity_id, template, media, status, requested_by, source_params, num_labels, notes)
          values (:id, 'cross_plans', null, 'tank_2.4x1.5', '2.4x1.5', 'queued', :by, :params, :num, :notes)
        """), dict(id=job_id, by=created_by, params=json.dumps({"source":"05_plan_crosses"}), num=len(payloads), notes=title_note))
        ins_item = text("""
          insert into public.label_items (id_uuid, job_id, seq, payload, qr_text)
          values (:id, :job_id, :seq, :payload, :qr)
        """)
        for i, p in enumerate(payloads, start=1):
            c.execute(ins_item, dict(id=str(uuid.uuid4()), job_id=job_id, seq=i, payload=json.dumps(p), qr=None))
    return job_id

# ---------- Session state ----------
if "geno_rows" not in st.session_state:
    st.session_state.geno_rows = []
if "tx_rows" not in st.session_state:
    st.session_state.tx_rows = []

# ---------- Step 0–1: Date + Tanks ----------
user_default = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
created_by = st.text_input("Created by", value=user_default)
today = date.today()
default_day = today + timedelta(days=1)
week_start = default_day - timedelta(days=default_day.weekday())
week_end_excl = week_start + timedelta(days=7)

plan_date = st.date_input("Cross date", value=default_day, min_value=today - timedelta(days=7))
note = st.text_input("Optional note", value="")

df_tanks = _load_inventory_tanks()
if df_tanks.empty:
    st.warning("No inventory tanks found. Create/assign inventory tanks first.")
    st.stop()

labels = [f"{row.label or '—'} · {row.id}" for _, row in df_tanks.iterrows()]
ids = list(df_tanks["id"])
left, right = st.columns(2)
with left:
    a_idx = st.selectbox("Parent A — inventory tank", options=range(len(ids)), format_func=lambda i: labels[i] if 0 <= i < len(labels) else "")
with right:
    b_idx = st.selectbox("Parent B — inventory tank", options=range(len(ids)), format_func=lambda i: labels[i] if 0 <= i < len(labels) else "")

tank_a_id = ids[a_idx] if 0 <= a_idx < len(ids) else None
tank_b_id = ids[b_idx] if 0 <= b_idx < len(ids) else None

st.divider()

# ---------- Step 2: Genotype inheritance ----------
st.subheader("Step 2 — Genotype inheritance")
alleles = _load_allele_catalog()
if alleles.empty:
    st.info("No transgene_alleles yet. You can skip this step.")
else:
    col_bc, col_num, col_zyg = st.columns([1,1,1])
    with col_bc:
        base_codes = [""] + sorted(alleles["base_code"].unique().tolist())
        sel_base = st.selectbox("Base code", base_codes, index=0)
    with col_num:
        nums = alleles[alleles["base_code"] == sel_base]["allele_number"].tolist() if sel_base else []
        sel_num = st.selectbox("Allele number", nums if nums else [])
    with col_zyg:
        sel_zyg = st.selectbox("Planned zygosity", ["", "heterozygous", "homozygous", "unknown"], index=0)
    if st.button("Add genotype element", disabled=not (sel_base and sel_num is not None)):
        st.session_state.geno_rows.append(dict(base_code=sel_base, allele_number=int(sel_num), zygosity_planned=(sel_zyg or None)))

if st.session_state.geno_rows:
    gdf = pd.DataFrame(st.session_state.geno_rows)
    st.dataframe(gdf, hide_index=True, use_container_width=True)
    if st.button("Clear genotype list"):
        st.session_state.geno_rows = []

# ---------- Step 3: Treatments ----------
st.subheader("Step 3 — Optional treatments")
c1, c2, c3, c4 = st.columns([1,1,1,1])
with c1:
    t_name = st.text_input("Treatment")
with c2:
    t_amt = st.number_input("Amount", value=0.0, step=0.1, format="%.3f")
with c3:
    t_units = st.text_input("Units", value="")
with c4:
    t_note = st.text_input("Timing note", value="")
if st.button("Add treatment", disabled=not t_name.strip()):
    st.session_state.tx_rows.append(dict(treatment_name=t_name.strip(), amount=(t_amt if t_amt != 0 else None), units=(t_units.strip() or None), timing_note=(t_note.strip() or None)))

if st.session_state.tx_rows:
    txdf = pd.DataFrame(st.session_state.tx_rows)
    st.dataframe(txdf, hide_index=True, use_container_width=True)
    if st.button("Clear treatments"):
        st.session_state.tx_rows = []

st.divider()

# ---------- Step 4: Preview ----------
st.subheader("Step 4 — Preview")
cols = st.columns(2)
with cols[0]:
    st.markdown("**Parents**")
    st.write(labels[a_idx] if tank_a_id else "—")
    st.write(labels[b_idx] if tank_b_id else "—")
with cols[1]:
    st.markdown("**Genotype plan**")
    if st.session_state.geno_rows:
        st.write(", ".join([f"{r['base_code']}[{r['allele_number']}] {r.get('zygosity_planned') or ''}".strip() for r in st.session_state.geno_rows]))
    else:
        st.write("—")
st.markdown("**Treatments**")
if st.session_state.tx_rows:
    st.write(", ".join([", ".join([p for p in [r['treatment_name'],
                                               (str(r['amount']) if r.get('amount') is not None else None),
                                               r.get('units'),
                                               (f\"[{r['timing_note']}]\" if r.get('timing_note') else None)] if p]) for r in st.session_state.tx_rows]))
else:
    st.write("—")

st.divider()

# ---------- Step 5: Save plan ----------
st.subheader("Step 5 — Save")
save_btn = st.button("Save plan (with genotype + treatments)", type="primary", use_container_width=True,
                     disabled=not (created_by and plan_date and tank_a_id and tank_b_id))
if save_btn:
    ok, pid = _insert_cross_plan(plan_date, tank_a_id, tank_b_id, created_by, note.strip() or None)
    if not pid:
        st.error("Could not resolve plan id.")
    else:
        n_g = _upsert_plan_genotypes(pid, st.session_state.get("geno_rows", []))
        n_t = _upsert_plan_treatments(pid, st.session_state.get("tx_rows", []))
        st.success(f"Saved plan {pid}  •  genotype rows: {n_g}  •  treatments: {n_t}")

st.divider()

# ---------- Step 6: Reports ----------
st.subheader("Step 6 — Reports")
rcol1, rcol2 = st.columns([1,1])
with rcol1:
    rep_day = st.date_input("Report day", value=plan_date)
with rcol2:
    wk_start = rep_day - timedelta(days=rep_day.weekday())
    wk_end   = wk_start + timedelta(days=7)
    st.caption(f"Week: {wk_start} → {wk_end - timedelta(days=1)}")

df_day  = _load_enriched_plans(created_by, rep_day, rep_day + timedelta(days=1))
df_week = _load_enriched_plans(created_by, wk_start, wk_end)

st.markdown("**Daily plans**")
if df_day.empty:
    st.write("— none —")
else:
    dshow = df_day[["plan_date","tank_a_label","tank_b_label","genotype_plan","treatments_plan","status"]].rename(columns={
        "plan_date":"Date","tank_a_label":"Tank A","tank_b_label":"Tank B","genotype_plan":"Genotype","treatments_plan":"Treatments","status":"Status"
    })
    st.dataframe(dshow, use_container_width=True, hide_index=True)
    st.download_button("Download daily CSV", dshow.to_csv(index=False).encode("utf-8"),
                       file_name=f"cross_plans_{rep_day}.csv", mime="text/csv", use_container_width=True)

st.markdown("**Weekly plans**")
if df_week.empty:
    st.write("— none —")
else:
    wshow = df_week[["plan_date","tank_a_label","tank_b_label","genotype_plan","treatments_plan","status"]].rename(columns={
        "plan_date":"Date","tank_a_label":"Tank A","tank_b_label":"Tank B","genotype_plan":"Genotype","treatments_plan":"Treatments","status":"Status"
    })
    st.dataframe(wshow, use_container_width=True, hide_index=True)
    st.download_button("Download weekly CSV", wshow.to_csv(index=False).encode("utf-8"),
                       file_name=f"cross_plans_week_{wk_start}.csv", mime="text/csv", use_container_width=True)

st.divider()

# ---------- Step 7: Labels ----------
st.subheader("Step 7 — Simple crossing-tank labels")
st.caption("Creates a label job with 2 labels per plan (Tank A & Tank B). Fields: tank label, role, genotype, date.")
l1, l2 = st.columns(2)
with l1:
    if st.button("Enqueue labels for DAILY report", use_container_width=True, disabled=df_day.empty):
        jid = _enqueue_tank_labels_for_plans(created_by, df_day, f"Cross plan labels — {rep_day}")
        if jid:
            st.success(f"Enqueued label job {jid} for {rep_day}")
with l2:
    if st.button("Enqueue labels for WEEKLY report", use_container_width=True, disabled=df_week.empty):
        jid = _enqueue_tank_labels_for_plans(created_by, df_week, f"Cross plan labels — week of {wk_start}")
        if jid:
            st.success(f"Enqueued label job {jid} for week starting {wk_start}")