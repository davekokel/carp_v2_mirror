from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

import os
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Schedule Cross Runs", page_icon="🧪")
st.title("🧪 Set up crossing tanks")

ENGINE = create_engine(os.environ["DB_URL"], pool_pre_ping=True)

# ---------------- DB helpers ----------------
def _current_tanks_for_fish_code(fish_code: str | None) -> pd.DataFrame:
    """Current tanks (open membership) for a fish_code. Columns: id, label"""
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

def _search_plans(q: str, limit: int = 200) -> pd.DataFrame:
    """
    Return cross plans including rolled-up child genotype & treatments:
      genotype_plan: e.g., pDQM005[301], pDQM005[302]
      treatments_plan: e.g., RNA:RNA-CRISPR-CTRL …
    """
    sql = text("""
      with g as (
        select p.id,
               coalesce(string_agg(
                 format('%s[%s]%s',
                        ga.transgene_base_code,
                        ga.allele_number,
                        coalesce(' '||ga.zygosity_planned,'')
                 ),
                 ', ' order by ga.transgene_base_code, ga.allele_number
               ), '') as genotype_plan
        from public.cross_plans p
        left join public.cross_plan_genotype_alleles ga on ga.plan_id = p.id
        group by p.id
      ),
      t as (
        select p.id,
               coalesce(string_agg(
                 trim(both ' ' from concat(
                   coalesce(ct.treatment_name,''),
                   case when ct.injection_mix   is not null and ct.injection_mix  <> '' then ' (mix='||ct.injection_mix||')' else '' end,
                   case when ct.treatment_notes is not null and ct.treatment_notes<> '' then ' ['||ct.treatment_notes||']' else '' end,
                   case when ct.timing_note     is not null and ct.timing_note    <> '' then ' {'||ct.timing_note||'}' else '' end
                 )),
                 ' • ' order by coalesce(ct.treatment_name,''), coalesce(ct.rna_id::text,''), coalesce(ct.plasmid_id::text,'')
               ), '') as treatments_plan
        from public.cross_plans p
        left join public.cross_plan_treatments ct on ct.plan_id = p.id
        group by p.id
      )
      select p.id::text as id,
             coalesce(p.plan_title,'')    as plan_title,
             coalesce(p.plan_nickname,'') as plan_nickname,
             fm.fish_code                 as mom,
             ff.fish_code                 as dad,
             p.created_at,
             coalesce(g.genotype_plan,'')   as genotype_plan,
             coalesce(t.treatments_plan,'') as treatments_plan
      from public.cross_plans p
      left join public.fish fm on fm.id = p.mother_fish_id
      left join public.fish ff on ff.id = p.father_fish_id
      left join g on g.id = p.id
      left join t on t.id = p.id
      where (:q = '')
         or (coalesce(p.plan_title,'')    ilike :like)
         or (coalesce(p.plan_nickname,'') ilike :like)
         or (coalesce(fm.fish_code,'')    ilike :like)
         or (coalesce(ff.fish_code,'')    ilike :like)
         or (coalesce(g.genotype_plan,'')   ilike :like)
         or (coalesce(t.treatments_plan,'') ilike :like)
      order by p.created_at desc
      limit :lim
    """)
    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx, params={"q": q.strip(), "like": f"%{q.strip()}%" if q.strip() else "%%", "lim": limit})

def _create_runs(plan_id: str, planned_date: date, rows: pd.DataFrame, created_by: str):
    sql = text("""
      insert into public.cross_plan_runs (plan_id, seq, planned_date, tank_a_id, tank_b_id, status, created_by)
      values (:pid, :seq, :d, :a, :b, 'planned', :by)
      on conflict do nothing
    """)
    with ENGINE.begin() as cx:
        for _, r in rows.iterrows():
            cx.execute(sql, dict(
                pid=plan_id,
                seq=int(r["seq"]),
                d=planned_date,
                a=(r.get("tank_a_id") or None),
                b=(r.get("tank_b_id") or None),
                by=created_by
            ))

def _load_run_reports(d0: date, d1_excl: date) -> pd.DataFrame:
    sql = text("""
      select *
      from public.v_cross_plan_runs_enriched
      where planned_date >= :d0 and planned_date < :d1
      order by planned_date asc, plan_title nulls last, seq asc
    """)
    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx, params={"d0": d0, "d1": d1_excl})

def _add_tanks_ok(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    out = df.copy()
    out["Tanks OK"] = out.apply(lambda r: "✓" if r.get("tank_a_label") and r.get("tank_b_label") else "⚠", axis=1)
    return out

# ---------------- Plan selection (checkbox in table) ----------------
st.subheader("Pick a cross to schedule")

q = st.text_input("Search crosses (name / nickname / mom / dad)", "")
plans = _search_plans(q)
if plans.empty:
    st.info("No matching crosses yet. Define a cross on page 05.")
    st.stop()

tbl = plans.rename(columns={
    "plan_title":"Name",
    "plan_nickname":"Nickname",
    "mom":"Mom",
    "dad":"Dad",
    "created_at":"Created",
    "genotype_plan":"Genotype",
    "treatments_plan":"Treatments",
}).copy()

try:
    tbl["Created"] = pd.to_datetime(tbl["Created"], unit="ms", utc=True, errors="ignore").dt.tz_convert(None).dt.strftime("%Y-%m-%d %H:%M")
except Exception:
    pass

tbl["Select"] = False
disp = tbl.set_index("id")[["Select","Name","Nickname","Mom","Dad","Genotype","Treatments","Created"]]

sel_tbl = st.data_editor(
    disp,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    column_config={
        "Select":     st.column_config.CheckboxColumn("Select", default=False, help="Pick exactly one cross"),
        "Name":       st.column_config.TextColumn(disabled=True),
        "Nickname":   st.column_config.TextColumn(disabled=True),
        "Mom":        st.column_config.TextColumn(disabled=True),
        "Dad":        st.column_config.TextColumn(disabled=True),
        "Genotype":   st.column_config.TextColumn(disabled=True),
        "Treatments": st.column_config.TextColumn(disabled=True),
        "Created":    st.column_config.TextColumn(disabled=True),
    },
    key="plan_select_table_v3",
)

chosen_ids = [idx for idx, r in sel_tbl.iterrows() if r.get("Select")]
if not chosen_ids:
    st.warning("Tick one row to continue.")
    st.stop()
if len(chosen_ids) > 1:
    st.warning("Multiple rows selected; using the first checked row.")

plan_id = chosen_ids[0]
sel_row = plans.loc[plans["id"] == plan_id].iloc[0]
summary_name = sel_row.get("plan_title") or "—"
summary_nick = sel_row.get("plan_nickname") or "—"
summary_mom  = sel_row.get("mom") or "—"
summary_dad  = sel_row.get("dad") or "—"
summary_geno = sel_row.get("genotype_plan") or "—"
summary_tx   = sel_row.get("treatments_plan") or "—"

st.markdown(
    f"**Selected:** `{summary_name}` — {summary_mom} × {summary_dad}  \n"
    f"*Nickname:* {summary_nick}  \n"
    f"*Genotype:* {summary_geno}  \n"
    f"*Treatments:* {summary_tx}"
)
st.session_state["selected_plan_id"] = plan_id
st.divider()

# ---------------- Create crossing tanks ----------------
st.subheader("Choose which tanks to cross")

mom_code = sel_row.get("mom") or None
dad_code = sel_row.get("dad") or None

col1, col2 = st.columns([1,1])
with col1:
    run_date = st.date_input("Planned date", value=date.today())
with col2:
    n_runs = st.number_input("How many crossing tanks?", min_value=1, max_value=50, value=1, step=1)

mom_tanks = _current_tanks_for_fish_code(mom_code)
dad_tanks = _current_tanks_for_fish_code(dad_code)

mom_labels = ["—"] + [f"{r.label or '—'} · {r.id[:8]}…" for _, r in mom_tanks.iterrows()]
mom_ids    = [None] + mom_tanks["id"].tolist()
dad_labels = ["—"] + [f"{r.label or '—'} · {r.id[:8]}…" for _, r in dad_tanks.iterrows()]
dad_ids    = [None] + dad_tanks["id"].tolist()

if mom_tanks.empty:
    st.info(f"No current tanks found for Mom ({mom_code or '—'}). You can leave Tank A unspecified.")
if dad_tanks.empty:
    st.info(f"No current tanks found for Dad ({dad_code or '—'}). You can leave Tank B unspecified.")

rows = []
st.caption("Pick tanks that currently hold each parent (or leave unspecified).")
for i in range(n_runs):
    a_col, b_col = st.columns([1,1])
    with a_col:
        a_idx = st.selectbox(
            f"Crossing tank #{i+1} — Tank A (Mom: {mom_code or '—'})",
            options=range(len(mom_ids)),
            format_func=lambda j: mom_labels[j],
            key=f"x_tankA_{i}"
        )
    with b_col:
        b_idx = st.selectbox(
            f"Crossing tank #{i+1} — Tank B (Dad: {dad_code or '—'})",
            options=range(len(dad_ids)),
            format_func=lambda j: dad_labels[j],
            key=f"x_tankB_{i}"
        )
    rows.append({"seq": i+1, "tank_a_id": mom_ids[a_idx], "tank_b_id": dad_ids[b_idx]})

run_df = pd.DataFrame(rows)
st.dataframe(
    run_df.assign(
        tank_a=lambda d: d["tank_a_id"].apply(lambda v: next((lab for lab, idv in zip(mom_labels[1:], mom_ids[1:]) if idv==v), "—")),
        tank_b=lambda d: d["tank_b_id"].apply(lambda v: next((lab for lab, idv in zip(dad_labels[1:], dad_ids[1:]) if idv==v), "—")),
    )[["seq","tank_a","tank_b"]].rename(columns={"tank_a":"Tank A (Mom)","tank_b":"Tank B (Dad)"}),
    hide_index=True, use_container_width=True
)

if st.button("Create crossing tanks", type="primary", use_container_width=True):
    _create_runs(plan_id, run_date, run_df, created_by=os.getenv("USER","unknown"))
    st.success(f"Created {n_runs} crossing tank(s).")

# ---------------- Run reports (read-only on this page) ----------------
st.divider()
st.subheader("Run reports")

c1, c2 = st.columns([1,1])
with c1:
    rep_day = st.date_input("Report day", value=date.today())
with c2:
    wk_start = rep_day - timedelta(days=rep_day.weekday())
    wk_end   = wk_start + timedelta(days=7)
    st.caption(f"Week: {wk_start} → {wk_end - timedelta(days=1)}")

df_day  = _load_run_reports(rep_day, rep_day + timedelta(days=1))
df_week = _load_run_reports(wk_start, wk_end)

# ---------- Daily ----------
st.markdown("**Daily runs**")
if df_day.empty:
    st.write("— none —")
else:
    dshow = _add_tanks_ok(df_day)[
        ["id","planned_date","plan_title","plan_nickname",
         "mother_fish_code","father_fish_code","seq",
         "tank_a_label","tank_b_label","Tanks OK","status"]
    ].rename(columns={
        "planned_date":"Date","plan_title":"Name","plan_nickname":"Nickname",
        "mother_fish_code":"Mom fish","father_fish_code":"Dad fish",
        "tank_a_label":"Tank A","tank_b_label":"Tank B"
    }).reset_index(drop=True)

    try:
        dshow["Date"] = pd.to_datetime(dshow["Date"]).dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    st.dataframe(dshow.drop(columns=["id"]), use_container_width=True, hide_index=True)
    st.download_button(
        "Download daily CSV",
        dshow.drop(columns=["id"]).to_csv(index=False).encode("utf-8"),
        file_name=f"cross_runs_{rep_day}.csv",
        mime="text/csv",
        use_container_width=True
    )

# ---------- Weekly ----------
st.markdown("**Weekly runs**")
if df_week.empty:
    st.write("— none —")
else:
    wshow = _add_tanks_ok(df_week)[
        ["id","planned_date","plan_title","plan_nickname",
         "mother_fish_code","father_fish_code","seq",
         "tank_a_label","tank_b_label","Tanks OK","status"]
    ].rename(columns={
        "planned_date":"Date","plan_title":"Name","plan_nickname":"Nickname",
        "mother_fish_code":"Mom fish","father_fish_code":"Dad fish",
        "tank_a_label":"Tank A","tank_b_label":"Tank B"
    }).reset_index(drop=True)

    try:
        wshow["Date"] = pd.to_datetime(wshow["Date"]).dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    st.dataframe(wshow.drop(columns=["id"]), use_container_width=True, hide_index=True)
    st.download_button(
        "Download weekly CSV",
        wshow.drop(columns=["id"]).to_csv(index=False).encode("utf-8"),
        file_name=f"cross_runs_week_{wk_start}.csv",
        mime="text/csv",
        use_container_width=True
    )

# Optional: a friendly handoff to the clutches page
st.divider()
st.caption("Ready to record actual tanks and clutch data?")
if st.button("→ Go to Register clutches (next page)", use_container_width=True):
    st.experimental_set_query_params(report_day=str(rep_day))
    # st.switch_page("pages/08_🍼_register_clutches.py")