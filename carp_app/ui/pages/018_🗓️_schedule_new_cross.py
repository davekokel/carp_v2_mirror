# =============================================================================
# 🗓 Schedule new cross (+ clutches) — resolve plasmid base names by code (SQL CTE per label, proper CAST)
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

def _col_exists(cx, s: str, t: str, c: str) -> bool:
    return not _safe(cx, """
        select 1 from information_schema.columns
        where table_schema=:s and table_name=:t and column_name=:c
        limit 1
    """, {"s": s, "t": t, "c": c}).empty

# ── SQL resolver: single label → plasmid base name (uses psql harness logic) ─
def resolve_plasmid_base_sql(label: str) -> str:
    if not label: return ""
    with eng.begin() as cx:
        df = _safe(cx, text(r"""
            with labels(lab, ord) as (
              select CAST(:lab AS text) as lab, 1::int as ord
            ),
            parts as (
              select lab, ord, unnest(regexp_split_to_array(lab, '\s*[×x]\s*')) as part
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
              join public.plasmids p
                on lower(p.code::text) = c.code
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

# ── Tank pair query (simplified) ─────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _tank_pairs(q: str, limit: int) -> pd.DataFrame:
    with eng.begin() as cx:
        df = _safe(cx, """
            select tank_pair_code, fish_pair_code,
                   mom_fish_code, dad_fish_code,
                   mom_tank_code, dad_tank_code,
                   mom_genotype, dad_genotype,
                   created_at
            from public.v_tank_pairs
            where (:q = '' or
                  tank_pair_code ilike :like or
                  mom_fish_code ilike :like or
                  dad_fish_code ilike :like)
            order by created_at desc nulls last
            limit :lim
        """, {"q": q, "like": f"%{q}%", "lim": limit})
    return df

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
st.success(f"Selected {tp_code} — {mom_code} × {dad_code}")

# ── Recent clutches table (one row per clutch) ───────────────────────────────
st.subheader("Recent clutches for this tank pair")
with eng.begin() as cx:
    recent = _safe(cx, """
      select ci.cross_run_code as cross_code,
             to_char(ci.cross_date,'YYYY-MM-DD') as cross_date,
             coalesce(cl.observed_genotype_pretty,
                      cl.expected_genotype_pretty,
                      cl.clutch_genotype_pretty) as clutch_genotype,
             cl.clutch_instance_code as clutch_code,
             to_char(coalesce(cl.created_at, ci.created_at),'YYYY-MM-DD') as created
      from public.cross_instances ci
      left join public.clutch_instances cl on cl.cross_instance_id = ci.id
      where ci.tank_pair_code = :tp
      order by coalesce(cl.created_at, ci.created_at) desc nulls last
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
def _expected_rows(m: str, d: str) -> pd.DataFrame:
    with eng.begin() as cx:
        df = _safe(cx, """
            select fish_code, genotype_rollup as g
            from public.v_fish_rich
            where fish_code = any(:codes)
        """, {"codes": [m, d]})
    def toks(s: str) -> list[str]:
        return [p.strip() for p in re.split(r"[;,|]+", s or "") if p.strip()]
    mom_t = toks(" ".join(df.loc[df["fish_code"] == m, "g"].astype(str)))
    dad_t = toks(" ".join(df.loc[df["fish_code"] == d, "g"].astype(str)))
    singles = [{"label": t, "source": "mom"} for t in mom_t] + [
        {"label": t, "source": "dad"} for t in dad_t if t not in mom_t
    ]
    all_single = [r["label"] for r in singles]
    doubles = [{"label": " × ".join(sorted(x)), "source": "double"}
               for x in itertools.combinations(all_single, 2)]
    rows = pd.DataFrame(singles + doubles, columns=["label","source"])
    # resolve plasmid base names per label via SQL (no pandas dtype issues)
    if not rows.empty:
        rows["plasmid_base"] = rows["label"].map(resolve_plasmid_base_sql).fillna("")
    else:
        rows["plasmid_base"] = pd.Series(dtype="string")
    return rows

rows = _expected_rows(mom_code, dad_code)
if rows.empty:
    st.caption("No genotype suggestions found.")
else:
    rows.insert(0, "✓", False)
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

# ── Idempotency + insert logic ───────────────────────────────────────────────
if "xid" not in st.session_state:
    st.session_state["xid"] = str(uuid.uuid4())
xid = st.session_state["xid"]
st.caption(f"idempotency_key = {xid}")

if st.button("⏱ Schedule cross + clutch(es)", type="primary"):
    creator = user.get("email") or user.get("id") or "unknown"
    try:
        with eng.begin() as cx:
            ins = text("""
              insert into public.cross_instances
                (cross_id, id, tank_pair_code, cross_date, created_by, note, idempotency_key)
              values
                (gen_random_uuid(), gen_random_uuid(), :tp, :d, :by, nullif(:note,''), :xid)
              on conflict (idempotency_key) do update
                set note = coalesce(excluded.note, public.cross_instances.note)
              returning id, cross_run_code
            """)
            row = _safe(cx, ins, {"tp": tp_code, "d": str(run_date), "by": creator, "note": note, "xid": xid})
            cross_id = row.iloc[0]["id"]

            if not chosen_labels:
                cx.execute(text("""
                    insert into public.clutch_instances (id, cross_instance_id, tank_pair_code)
                    values (gen_random_uuid(), :cid, :tp)
                """), {"cid": cross_id, "tp": tp_code})
            else:
                for lbl in chosen_labels:
                    cx.execute(text("""
                        insert into public.clutch_instances
                          (id, cross_instance_id, tank_pair_code, expected_genotype_pretty)
                        values
                          (gen_random_uuid(), :cid, :tp, :lbl)
                    """), {"cid": cross_id, "tp": tp_code, "lbl": lbl})

        st.session_state["xid"] = None
        st.success("Cross scheduled successfully.")
    except Exception as e:
        st.error(f"Schedule failed: {e}")