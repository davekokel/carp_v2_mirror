# =============================================================================
# 🗓 Schedule new cross (+ clutches) — resolve plasmid base names by code
# =============================================================================
from __future__ import annotations
import sys, pathlib, re, itertools, uuid, os
from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.elements import TextClause

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
from carp_app.ui.lib.app_ctx import get_engine

# ── Auth + engine ────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
st.set_page_config(page_title="🗓 Schedule new cross", page_icon="🗓", layout="wide")
st.title("🗓 Schedule new cross")
if not os.getenv("DB_URL"):
    st.error("DB_URL not set"); st.stop()
eng: Engine = get_engine()
with eng.begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# ── Small DB helpers ─────────────────────────────────────────────────────────
def _safe(cx, q: str | TextClause, p=None) -> pd.DataFrame:
    q = q if isinstance(q, TextClause) else text(q)
    return pd.read_sql(q, cx, params=p or {})

def _load_crosses_and_clutches_for_pair(tp_code: str) -> pd.DataFrame:
    if not tp_code:
        return pd.DataFrame(columns=["cross_code","cross_date","clutch_code","clutch_genotype","created"])
    with eng.begin() as cx:
        return _safe(cx, text("""
          select
            cr.cross_run_code                                     as cross_code,
            cr.cross_date                                         as cross_date,
            coalesce(cl.clutch_instance_code,'')                  as clutch_code,
            coalesce(cl.clutch_genotype_pretty,'')                as clutch_genotype,
            coalesce(cl.created_at, cr.created_at)::timestamptz   as created
          from public.crosses cr
          left join public.clutch_instances cl
                 on cl.cross_instance_id = cr.id
          where cr.tank_pair_code = :tp
          order by cr.cross_date desc nulls last,
                   coalesce(cl.created_at, cr.created_at) desc nulls last
          limit 200
        """), {"tp": tp_code})

# ── SQL resolver: single label → plasmid base name (via plasmids table) ─────
def resolve_plasmid_base_sql(label: str) -> str:
    if not label: return ""
    with eng.begin() as cx:
        df = _safe(cx, text(r"""
            with labels(lab, ord) as (select CAST(:lab AS text) as lab, 1::int as ord),
            parts as (
              select lab, ord, unnest(regexp_split_to_array(lab, '\s*[×x;]\s*')) as part
              from labels
            ),
            codes_raw as (
              select lab, ord, part,
                     array_remove(regexp_matches(part, '\[([A-Za-z0-9\-]+)\]', 'g'), null) ||
                     array_remove(regexp_matches(part, '\m[pP][A-Za-z]{2,}\d{2,}\M', 'g'), null) ||
                     array_remove(regexp_matches(part, '\m[A-Z]{2,}-\d{2,}\M', 'g'), null)
                     as code_arr
              from parts
            ),
            codes as (
              select lab, ord, part, lower(code) as code
              from codes_raw, unnest(code_arr) as code
            ),
            plasmid_names as (
              select c.lab, c.ord, c.part, p.name::text as plasmid_name
              from codes c
              join public.plasmids p on lower(p.code::text) = c.code
            ),
            names_per_part as (
              select lab, ord, part,
                     string_agg(distinct plasmid_name, ' + ' order by plasmid_name) as part_names
              from plasmid_names
              group by lab, ord, part
            ),
            names_per_label as (
              select l.lab, l.ord,
                     string_agg(coalesce(n.part_names,''), ' + ' order by n.part) as label_plasmid_base
              from labels l
              left join names_per_part n on n.lab = l.lab and n.ord = l.ord
              group by l.lab, l.ord
            )
            select coalesce(label_plasmid_base,'') as resolved
            from names_per_label
        """), {"lab": label})
    if df.empty: return ""
    return str(df.iloc[0]["resolved"] or "")

# ── Tank pair query (adaptive to v_tank_pairs columns) ───────────────────────
@st.cache_data(show_spinner=False)
def _vtp_cols() -> set[str]:
    with eng.begin() as cx:
        df = _safe(cx, """
            select column_name
            from information_schema.columns
            where table_schema='public' and table_name='v_tank_pairs'
        """)
    return set(df["column_name"].tolist())

@st.cache_data(show_spinner=False)
def _tank_pairs(q: str, limit: int) -> pd.DataFrame:
    C = _vtp_cols()
    have = lambda c: c in C

    sel = []
    def add(col, alias=None, default_sql="null"):
        if have(col): sel.append(f"{col}" + (f" as {alias}" if alias else ""))
        else:         sel.append(f"{default_sql}" + (f" as {alias or col}"))

    add("tank_pair_code")
    add("fish_pair_code", default_sql="null")
    add("mom_fish_code")
    add("dad_fish_code")
    add("mom_tank_code")
    add("dad_tank_code")
    add("mom_genotype")
    add("dad_genotype")
    add("created_at")

    where, params = [], {"q": q or "", "like": f"%{q or ''}%", "lim": int(limit)}
    bag = []
    if have("tank_pair_code"): bag.append("tank_pair_code ilike :like")
    if have("fish_pair_code"): bag.append("fish_pair_code ilike :like")
    if have("mom_fish_code"):  bag.append("mom_fish_code ilike :like")
    if have("dad_fish_code"):  bag.append("dad_fish_code ilike :like")
    if q and bag: where.append("(" + " OR ".join(bag) + ")")
    where_sql = (" where " + " AND ".join(where)) if where else ""

    order_sql = "created_at desc nulls last, tank_pair_code" if have("created_at") and have("tank_pair_code") \
        else "created_at desc nulls last" if have("created_at") else "tank_pair_code"

    sql = text(f"""
        select {", ".join(sel)}
        from public.v_tank_pairs
        {where_sql}
        order by {order_sql}
        limit :lim
    """)
    with eng.begin() as cx:
        return _safe(cx, sql, params)

# Derive mom/dad fish_code from tanks if missing in v_tank_pairs
def _resolve_pair_fish_codes(tp_code: str, mom_code: str|None, dad_code: str|None) -> tuple[str|None,str|None]:
    if mom_code and dad_code:
        return mom_code, dad_code
    with eng.begin() as cx:
        df = _safe(cx, text(r"""
            select
              regexp_replace(vtm.tank_code, '^.*\(([^)]+)\).*$', '\1')::text as mom_fish_code,
              regexp_replace(vtf.tank_code, '^.*\(([^)]+)\).*$', '\1')::text as dad_fish_code
            from public.tank_pairs tp
            left join public.v_tanks vtm on vtm.tank_uuid = tp.mother_tank_id
            left join public.v_tanks vtf on vtf.tank_uuid = tp.father_tank_id
            where tp.tank_pair_code = :tp
            limit 1
        """), {"tp": tp_code})
    if df.empty:
        return mom_code, dad_code
    return (df.iloc[0]["mom_fish_code"] or mom_code), (df.iloc[0]["dad_fish_code"] or dad_code)

# ── Search & select tank pair ────────────────────────────────────────────────
with st.form("search"):
    c1, c2 = st.columns([3,1])
    q = c1.text_input("Search tank pairs (code / fish / tank)")
    limit = int(c2.number_input("Limit", 50, 2000, 200))
    st.form_submit_button("Apply")
pairs = _tank_pairs(q or "", limit)

st.subheader("1) Pick a tank pair")
if pairs.empty:
    st.info("No tank pairs found."); st.stop()
pairs.insert(0, "✓", False)
sel = st.data_editor(
    pairs,
    hide_index=True,
    width="stretch",
    column_config={"✓": st.column_config.CheckboxColumn("✓", default=False)},
)
chosen = sel.loc[sel["✓"]].head(1)
if chosen.empty:
    st.stop()
tp_code = chosen.iloc[0]["tank_pair_code"]
mom_code = chosen.iloc[0]["mom_fish_code"]
dad_code = chosen.iloc[0]["dad_fish_code"]
mom_code, dad_code = _resolve_pair_fish_codes(tp_code, mom_code, dad_code)
st.success(f"Selected {tp_code} — {mom_code or 'None'} × {dad_code or 'None'}")

# ── Recent clutches table (one row per clutch) ───────────────────────────────
st.subheader("Recent clutches for this tank pair")
with eng.begin() as cx:
    recent = _safe(cx, """
      select cr.cross_run_code as cross_code,
             to_char(cr.cross_date,'YYYY-MM-DD') as cross_date,
             coalesce(cl.clutch_genotype_pretty,'') as clutch_genotype,
             cl.clutch_instance_code as clutch_code,
             to_char(coalesce(cl.created_at, cr.created_at),'YYYY-MM-DD') as created
      from public.crosses cr
      left join public.clutch_instances cl on cl.cross_instance_id = cr.id
      where cr.tank_pair_code = :tp
      order by coalesce(cl.created_at, cr.created_at) desc nulls last
      limit 20
    """, {"tp": tp_code})
if recent.empty:
    st.caption("No recent clutches.")
else:
    st.dataframe(recent, hide_index=True, width="stretch")

# ── Expected genotype label table (checkbox) — plasmid base via SQL resolver ─
st.subheader("2) Choose run date & expected genotype labels")
run_date: date = st.date_input("Run date", value=date.today())
note = st.text_input("Run note (optional)")

@st.cache_data(show_spinner=False)
def _expected_rows(m: str|None, d: str|None) -> pd.DataFrame:
    codes = [c for c in [m, d] if c]
    if not codes:
        return pd.DataFrame(columns=["label","source","plasmid_base"])
    with eng.begin() as cx:
        df = _safe(cx, """
            select fish_code, genotype_pretty as g
            from public.v_fish_unified
            where fish_code = any(:codes)
        """, {"codes": codes})
    def toks(s: str) -> list[str]:
        return [p.strip() for p in re.split(r"[;,|]+", s or "") if p.strip()]
    mom_t = toks(" ".join(df.loc[df["fish_code"].eq(m), "g"].astype(str))) if m else []
    dad_t = toks(" ".join(df.loc[df["fish_code"].eq(d), "g"].astype(str))) if d else []
    mom_sorted = sorted(set(mom_t))
    dad_sorted = sorted(set(dad_t))
    singles = [{"label": t, "source": "mom"} for t in mom_sorted] + \
              [{"label": t, "source": "dad"} for t in dad_sorted if t not in set(mom_sorted)]
    all_single = [r["label"] for r in singles]
    doubles = [{"label": " ; ".join(sorted(x)), "source": "double"}
           for x in itertools.combinations(all_single, 2)]
    rows = pd.DataFrame(singles + doubles, columns=["label","source"])
    if rows.empty:
        rows["plasmid_base"] = pd.Series(dtype="string")
        return rows
    rows["plasmid_base"] = rows["label"].map(resolve_plasmid_base_sql).fillna("")
    return rows

rows = _expected_rows(mom_code, dad_code)
if rows.empty:
    st.caption("No genotype suggestions found.")
    chosen_labels: list[str] = []
else:
    if "✓" not in rows.columns:
        rows.insert(0, "✓", rows["source"].eq("single"))  # preselect singles
    edited = st.data_editor(
        rows,
        hide_index=True,
        width="stretch",
        column_order=["✓", "label", "plasmid_base", "source"],
        column_config={
            "✓":            st.column_config.CheckboxColumn("✓", default=False),
            "label":        st.column_config.TextColumn("Expected genotype label", disabled=True),
            "plasmid_base": st.column_config.TextColumn("Plasmid base name", disabled=True),
            "source":       st.column_config.TextColumn("Type", disabled=True),
        },
    )
    chosen_labels = edited.loc[edited["✓"]].get("label", pd.Series([], dtype=str)).astype(str).tolist()
    st.caption(f"{len(chosen_labels)} selected")

# ── Idempotent cross + clutch insert ─────────────────────────────────────────
# ── Idempotent cross + clutch insert ─────────────────────────────────────────
st.subheader("3) Schedule cross & clutches")
if st.button("⏱ Schedule cross + clutch(es)", type="primary"):
    creator = user.get("email") or user.get("id") or "unknown"
    try:
        # gather labels, enforce at least one
        labels = [s for s in (chosen_labels or []) if isinstance(s, str) and s.strip()]
        if not labels:
            st.error("Pick at least one clutch genotype label before scheduling.")
            st.stop()

        # 1) Insert/Upsert the cross: unique (tank_pair_code, cross_date) handles idempotency
        with eng.begin() as cx:
            row = cx.execute(
                text("""
                    insert into public.crosses
                      (id, tank_pair_code, cross_date, created_by, note)
                    values
                      (gen_random_uuid(), :tp, :d, :by, nullif(:note,''))
                    on conflict (tank_pair_code, cross_date) do update
                      set note = coalesce(excluded.note, public.crosses.note)
                    returning id, cross_run_code
                """),
                {"tp": tp_code, "d": str(run_date), "by": creator, "note": note}
            ).mappings().first()
            cross_id   = row["id"]
            cross_code = row.get("cross_run_code")

            # 2) Insert one clutch per selected label (no NULL fallback)
            #    normalized_genotype unique constraint guards duplicates per cross.
            for lbl in labels:
                cx.execute(
                    text("""
                        insert into public.clutch_instances
                          (id, cross_instance_id, tank_pair_code, clutch_genotype_pretty)
                        values
                          (gen_random_uuid(), :cid, :tp, :lbl)
                        on conflict (cross_instance_id, normalized_genotype)
                        do nothing
                    """),
                    {"cid": cross_id, "tp": tp_code, "lbl": lbl.strip()}
                )

        st.success(f"Cross {cross_code} scheduled with {len(labels)} clutch(es).")
    except Exception as e:
        st.error(f"Schedule failed: {e}")

st.subheader("Scheduled for this tank pair")
sched_df = _load_crosses_and_clutches_for_pair(tp_code)

if sched_df.empty:
    st.caption("No scheduled crosses/clutches yet for this tank pair.")
else:
    # Nice, readable table
    show_cols = ["cross_code","cross_date","clutch_code","clutch_genotype","created"]
    st.dataframe(
        sched_df[show_cols],
        hide_index=True,
        width="stretch",
        column_config={
            "cross_code":      st.column_config.TextColumn("Cross code", disabled=True),
            "cross_date":      st.column_config.DateColumn("Cross date", disabled=True, format="YYYY-MM-DD"),
            "clutch_code":     st.column_config.TextColumn("Clutch code", disabled=True),
            "clutch_genotype": st.column_config.TextColumn("Clutch genotype", disabled=True),
            "created":         st.column_config.DatetimeColumn("Created", disabled=True),
        },
    )