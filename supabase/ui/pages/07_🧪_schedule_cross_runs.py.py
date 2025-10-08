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
st.title("🧪 Schedule Cross Runs")

ENGINE = create_engine(os.environ["DB_URL"], pool_pre_ping=True)

# ---------------- DB helpers ----------------
def _search_plans(q: str) -> pd.DataFrame:
    sql = text("""
      select p.id::text as id, coalesce(p.plan_title,'') as plan_title, coalesce(p.plan_nickname,'') as plan_nickname,
             fm.fish_code as mom, ff.fish_code as dad, p.created_at
      from public.cross_plans p
      left join public.fish fm on fm.id = p.mother_fish_id
      left join public.fish ff on ff.id = p.father_fish_id
      where :q = '' or
            coalesce(p.plan_title,'') ilike :like or
            coalesce(p.plan_nickname,'') ilike :like or
            coalesce(fm.fish_code,'') ilike :like or
            coalesce(ff.fish_code,'') ilike :like
      order by p.created_at desc
    """)
    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx, params={"q": q.strip(), "like": f"%{q.strip()}%" if q.strip() else "%%"})

def _list_inventory_tanks() -> pd.DataFrame:
    sql = text("""
      select id_uuid::text as id, coalesce(label,'') as label
      from public.containers
      where container_type='inventory_tank'
      order by coalesce(label,''), created_at
    """)
    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx)

def _create_runs(plan_id: str, planned_date: date, rows: pd.DataFrame, created_by: str):
    sql = text("""
      insert into public.cross_plan_runs (plan_id, seq, planned_date, tank_a_id, tank_b_id, status, created_by)
      values (:pid, :seq, :d, :a, :b, 'planned', :by)
      on conflict do nothing
    """)
    with ENGINE.begin() as cx:
        for _, r in rows.iterrows():
            cx.execute(sql, dict(pid=plan_id, seq=int(r["seq"]), d=planned_date,
                                 a=(r.get("tank_a_id") or None), b=(r.get("tank_b_id") or None), by=created_by))

def _load_run_reports(created_by: str, d0: date, d1_excl: date) -> pd.DataFrame:
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

def _update_run_tanks(run_id: str, tank_a_id: str | None, tank_b_id: str | None):
    with ENGINE.begin() as cx:
        cx.execute(text("update public.cross_plan_runs set tank_a_id=:a, tank_b_id=:b where id=:id"),
                   {"a": tank_a_id, "b": tank_b_id, "id": run_id})

# ---------------- UI: pick plan ----------------
q = st.text_input("Find a cross (name / nickname / mom / dad)", "")
plans = _search_plans(q)
if plans.empty:
    st.info("No matching crosses yet. Define one on page 05.")
    st.stop()

st.dataframe(plans.rename(columns={"plan_title":"Name","plan_nickname":"Nickname","mom":"Mom","dad":"Dad"}),
             use_container_width=True, hide_index=True)

plan_id = st.selectbox("Pick a cross", options=[""] + plans["id"].tolist(),
                       format_func=lambda pid: (plans.loc[plans["id"]==pid,"plan_title"].iat[0] if pid else "—"))
if not plan_id:
    st.stop()

# ---------------- UI: build runs ----------------
col1, col2 = st.columns([1,1])
with col1:
    run_date = st.date_input("Planned date", value=date.today())
with col2:
    n_runs = st.number_input("How many runs?", min_value=1, max_value=50, value=1, step=1)

tanks = _list_inventory_tanks()
tank_labels = ["—"] + [f"{r.label or '—'} · {r.id[:8]}…" for _, r in tanks.iterrows()]
tank_ids    = [None] + tanks["id"].tolist()

rows = []
st.caption("Optionally assign tanks now (or leave unspecified).")
for i in range(n_runs):
    a_col, b_col = st.columns([1,1])
    with a_col:
        opt_a = st.selectbox(f"Run #{i+1} — Tank A", options=range(len(tank_ids)),
                             format_func=lambda j: tank_labels[j], key=f"runA_{i}")
    with b_col:
        opt_b = st.selectbox(f"Run #{i+1} — Tank B", options=range(len(tank_ids)),
                             format_func=lambda j: tank_labels[j], key=f"runB_{i}")
    a_id = tank_ids[opt_a]; b_id = tank_ids[opt_b]
    rows.append({"seq": i+1, "tank_a_id": a_id, "tank_b_id": b_id})

run_df = pd.DataFrame(rows)
st.dataframe(run_df.assign(
    tank_a=lambda d: d["tank_a_id"].apply(lambda v: next((lab for lab, idv in zip(tank_labels[1:], tank_ids[1:]) if idv==v), "—")),
    tank_b=lambda d: d["tank_b_id"].apply(lambda v: next((lab for lab, idv in zip(tank_labels[1:], tank_ids[1:]) if idv==v), "—"))
)[["seq","tank_a","tank_b"]], hide_index=True, use_container_width=True)

if st.button("Create runs", type="primary", use_container_width=True):
    _create_runs(plan_id, run_date, run_df, created_by=os.getenv("USER","unknown"))
    st.success(f"Created {n_runs} run(s).")

# ---------------- Reports (runs) ----------------
st.divider()
st.subheader("Run reports")

c1, c2 = st.columns([1,1])
with c1:
    rep_day = st.date_input("Report day", value=date.today())
with c2:
    wk_start = rep_day - timedelta(days=rep_day.weekday())
    wk_end   = wk_start + timedelta(days=7)
    st.caption(f"Week: {wk_start} → {wk_end - timedelta(days=1)}")

df_day  = _load_run_reports(created_by=os.getenv("USER","unknown"), d0=rep_day,   d1_excl=rep_day+timedelta(days=1))
df_week = _load_run_reports(created_by=os.getenv("USER","unknown"), d0=wk_start, d1_excl=wk_end)

st.markdown("**Daily runs**")
if df_day.empty:
    st.write("— none —")
else:
    dshow = _add_tanks_ok(df_day)[
        ["id","planned_date","plan_title","plan_nickname","mother_fish_code","father_fish_code","seq","tank_a_label","tank_b_label","Tanks OK","status"]
    ].rename(columns={
        "planned_date":"Date","plan_title":"Name","plan_nickname":"Nickname",
        "mother_fish_code":"Mom fish","father_fish_code":"Dad fish",
        "tank_a_label":"Tank A","tank_b_label":"Tank B"
    })
    st.dataframe(dshow.drop(columns=["id"]), use_container_width=True, hide_index=True)
    st.download_button("Download daily CSV", dshow.drop(columns=["id"]).to_csv(index=False).encode("utf-8"),
                       file_name=f"cross_runs_{rep_day}.csv", mime="text/csv", use_container_width=True)

    with st.expander("Confirm tanks (Daily)"):
        if tanks.empty:
            st.info("No inventory tanks available.")
        else:
            opts = [f"{r['Date']} · {r['Name'] or '—'} · run #{int(r['seq'])} · {str(r['id'])[:8]}…" for _, r in dshow.iterrows()]
            pick_map = {opt: dshow.iloc[i]["id"] for i, opt in enumerate(opts)}
            sel = st.selectbox("Pick a run", [""] + opts)
            if sel:
                run_id = pick_map[sel]
                a = st.selectbox("Tank A", options=range(len(tank_ids)), format_func=lambda j: tank_labels[j], key="confirmA")
                b = st.selectbox("Tank B", options=range(len(tank_ids)), format_func=lambda j: tank_labels[j], key="confirmB")
                a_id, b_id = tank_ids[a], tank_ids[b]
                if a_id and b_id and a_id == b_id:
                    st.warning("Pick two different tanks.")
                if st.button("Save tanks", type="primary", use_container_width=True, disabled=bool(a_id and b_id and a_id == b_id)):
                    _update_run_tanks(run_id, a_id, b_id)
                    st.success("Updated tanks.")
                    st.experimental_rerun()

st.markdown("**Weekly runs**")
if df_week.empty:
    st.write("— none —")
else:
    wshow = _add_tanks_ok(df_week)[
        ["id","planned_date","plan_title","plan_nickname","mother_fish_code","father_fish_code","seq","tank_a_label","tank_b_label","Tanks OK","status"]
    ].rename(columns={
        "planned_date":"Date","plan_title":"Name","plan_nickname":"Nickname",
        "mother_fish_code":"Mom fish","father_fish_code":"Dad fish",
        "tank_a_label":"Tank A","tank_b_label":"Tank B"
    })
    st.dataframe(wshow.drop(columns=["id"]), use_container_width=True, hide_index=True)
    st.download_button("Download weekly CSV", wshow.drop(columns=["id"]).to_csv(index=False).encode("utf-8"),
                       file_name=f"cross_runs_week_{wk_start}.csv", mime="text/csv", use_container_width=True)

    with st.expander("Confirm tanks (Weekly)"):
        if tanks.empty:
            st.info("No inventory tanks available.")
        else:
            opts = [f"{r['Date']} · {r['Name'] or '—'} · run #{int(r['seq'])} · {str(r['id'])[:8]}…" for _, r in wshow.iterrows()]
            pick_map = {opt: wshow.iloc[i]["id"] for i, opt in enumerate(opts)}
            sel = st.selectbox("Pick a run", [""] + opts, key="weekly_run_sel")
            if sel:
                run_id = pick_map[sel]
                a = st.selectbox("Tank A", options=range(len(tank_ids)), format_func=lambda j: tank_labels[j], key="cwA")
                b = st.selectbox("Tank B", options=range(len(tank_ids)), format_func=lambda j: tank_labels[j], key="cwB")
                a_id, b_id = tank_ids[a], tank_ids[b]
                if a_id and b_id and a_id == b_id:
                    st.warning("Pick two different tanks.")
                if st.button("Save tanks (weekly)", type="primary", use_container_width=True, disabled=bool(a_id and b_id and a_id == b_id)):
                    _update_run_tanks(run_id, a_id, b_id)
                    st.success("Updated tanks.")
                    st.experimental_rerun()