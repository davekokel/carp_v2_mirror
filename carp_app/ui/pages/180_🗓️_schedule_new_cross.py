# carp_app/ui/pages/180_🗓️_schedule_new_cross.py
from __future__ import annotations

import sys, pathlib, re, itertools, uuid, os
from datetime import date
from typing import List, Optional, Set, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.elements import TextClause

# repo root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# auth / engine
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine

# ── Auth + page setup ────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — 🗓 Schedule new cross", page_icon="🗓", layout="wide")
st.title("🗓 Schedule new cross")

with engine().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# ── Small DB helpers ─────────────────────────────────────────────────────────
def _safe(cx, q: str | TextClause, p=None) -> pd.DataFrame:
    q = q if isinstance(q, TextClause) else text(q)
    return pd.read_sql(q, cx, params=p or {})

def _table_exists(schema: str, table: str) -> bool:
    with engine().begin() as cx:
        n = _safe(cx, text("""
            select count(*)::int as n
            from information_schema.tables
            where table_schema=:s and table_name=:t
        """), {"s": schema, "t": table})["n"][0]
    return n > 0

def _cols(schema: str, rel: str) -> Set[str]:
    with engine().begin() as cx:
        df = _safe(cx, text("""
            select column_name
            from information_schema.columns
            where table_schema=:s and table_name=:r
        """), {"s": schema, "r": rel})
    return set(df["column_name"].tolist())

# pick mother/father tank uuid columns from tank_pairs
def _tank_pair_parent_cols() -> Tuple[str, str]:
    c = _cols("public", "tank_pairs")
    for a, b in (("mother_tank_id","father_tank_id"),
                 ("tank_id_mother","tank_id_father")):
        if a in c and b in c:
            return a, b
    raise RuntimeError("public.tank_pairs must have parent UUID columns (mother_tank_id/father_tank_id or tank_id_mother/tank_id_father).")

# ── Tank pair query (NO dependency on v_tank_pairs) ─────────────────────────
@st.cache_data(show_spinner=False)
def list_tank_pairs(q: str, limit: int) -> pd.DataFrame:
    if not _table_exists("public", "tank_pairs"):
        return pd.DataFrame(columns=[
            "tank_pair_code","fish_pair_code","status","created_at","created_by",
            "mom_fish_code","mom_tank_code","mom_genotype",
            "dad_fish_code","dad_tank_code","dad_genotype"
        ])
    mom_col, dad_col = _tank_pair_parent_cols()
    tp_cols = _cols("public", "tank_pairs")

    where, params = [], {}
    if "created_at" in tp_cols:
        order_clause = "tp.created_at desc nulls last, tp.tank_pair_code"
    elif "tank_pair_code" in tp_cols:
        order_clause = "tp.tank_pair_code"
    else:
        order_clause = f"tp.{mom_col}"

    # free text later across joined fields
    params["lim"] = int(limit)
    like = f"%{q.strip()}%" if q and q.strip() else None

    sql = text(f"""
    WITH tp AS (
      SELECT *
      FROM public.tank_pairs tp
      ORDER BY {order_clause}
      LIMIT :lim
    ),
    tm AS (
      SELECT
        vt.tank_uuid::uuid AS tank_id,
        vt.tank_code,
        regexp_replace(vt.tank_code, '^.*\\(([^)]+)\\).*$', '\\1')::text AS fish_code
      FROM public.v_tanks vt
    ),
    geno AS (
      SELECT
        vm.fish_code,
        MAX(vm.genotype_pretty) AS genotype
      FROM public.v_fish_main vm
      GROUP BY vm.fish_code
    )
    SELECT
      {('tp.tank_pair_code' if 'tank_pair_code' in tp_cols else 'NULL::text')}      AS tank_pair_code,
      {('tp.fish_pair_code' if 'fish_pair_code' in tp_cols else 'NULL::text')}      AS fish_pair_code,
      {('tp.status'         if 'status' in tp_cols else "'unknown'::text")}         AS status,
      {('tp.created_by'     if 'created_by' in tp_cols else 'NULL::text')}          AS created_by,
      {('tp.created_at'     if 'created_at' in tp_cols else 'NULL::timestamptz')}   AS created_at,

      tm_m.fish_code  AS mom_fish_code,
      tm_m.tank_code  AS mom_tank_code,
      g_m.genotype    AS mom_genotype,

      tm_d.fish_code  AS dad_fish_code,
      tm_d.tank_code  AS dad_tank_code,
      g_d.genotype    AS dad_genotype
    FROM tp
    LEFT JOIN tm   AS tm_m ON tm_m.tank_id = tp.{mom_col}
    LEFT JOIN tm   AS tm_d ON tm_d.tank_id = tp.{dad_col}
    LEFT JOIN geno AS g_m  ON g_m.fish_code = tm_m.fish_code
    LEFT JOIN geno AS g_d  ON g_d.fish_code = tm_d.fish_code
    { "WHERE (" + " OR ".join([
          "coalesce(tp.tank_pair_code,'') ilike :like"   if 'tank_pair_code' in tp_cols and like else None,
          "coalesce(tp.fish_pair_code,'') ilike :like"   if 'fish_pair_code' in tp_cols and like else None,
          "coalesce(tm_m.fish_code,'') ilike :like"      if like else None,
          "coalesce(tm_d.fish_code,'') ilike :like"      if like else None,
          "coalesce(tm_m.tank_code,'') ilike :like"      if like else None,
          "coalesce(tm_d.tank_code,'') ilike :like"      if like else None,
          "coalesce(g_m.genotype,'') ilike :like"        if like else None,
          "coalesce(g_d.genotype,'') ilike :like"        if like else None,
      ]) + ")" if like else ""
    }
    ORDER BY {order_clause}
    """)
    if like:
        params["like"] = like
    with engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return df.fillna("")

# ── SQL resolver: "label" → plasmid base names (via plasmids) ────────────────
def resolve_plasmid_base_sql(label: str) -> str:
    """
    Resolve a genotype label (e.g., 'pDQM136(gu44)' or 'X ; Y') into a friendly plasmid base name.
    Returns '' when nothing resolves; never returns a bare '+'.
    """
    if not label:
        return ""
    with engine().begin() as cx:
        df = _safe(cx, text(r"""
            WITH labels(lab, ord) AS (
              SELECT CAST(:lab AS text) AS lab, 1::int AS ord
            ),
            parts AS (  -- split on ×, x, or ; (with whitespace)
              SELECT lab, ord, unnest(regexp_split_to_array(lab, '\s*[×x;]\s*')) AS part
              FROM labels
            ),
            codes_raw AS (  -- pull possible plasmid codes: [CODE], pXXXX..., or AA-00...
              SELECT lab, ord, part,
                     array_remove(regexp_matches(part, '\[([A-Za-z0-9\-]+)\]', 'g'), NULL)
                  || array_remove(regexp_matches(part, '\m[pP][A-Za-z]{2,}\d{2,}\M', 'g'), NULL)
                  || array_remove(regexp_matches(part, '\m[A-Z]{2,}-\d{2,}\M', 'g'), NULL)
                     AS code_arr
              FROM parts
            ),
            codes AS (
              SELECT lab, ord, part, lower(code) AS code
              FROM codes_raw, unnest(code_arr) AS code
            ),
            plasmid_names AS (  -- resolve each code to a base name
              SELECT c.lab, c.ord, c.part, p.name::text AS plasmid_name
              FROM codes c
              JOIN public.plasmids p ON lower(p.code::text) = c.code
            ),
            names_per_part AS (  -- one string per part
              SELECT lab, ord, part,
                     string_agg(DISTINCT plasmid_name, ' + ' ORDER BY plasmid_name) AS part_names
              FROM plasmid_names
              GROUP BY lab, ord, part
            ),
            names_per_label AS (  -- join only non-empty part names
              SELECT l.lab, l.ord,
                     COALESCE(
                       NULLIF(
                         string_agg(n.part_names, ' + ' ORDER BY n.part)
                           FILTER (WHERE n.part_names IS NOT NULL AND n.part_names <> ''),
                         ''
                       ), ''
                     ) AS label_plasmid_base
              FROM labels l
              LEFT JOIN names_per_part n ON n.lab = l.lab AND n.ord = l.ord
              GROUP BY l.lab, l.ord
            )
            SELECT COALESCE(label_plasmid_base,'') AS resolved
            FROM names_per_label
        """), {"lab": label})
    if df.empty:
        return ""
    return str(df.iloc[0]["resolved"] or "")

# ── Expected genotype rows from v_fish_main (no v_fish_unified) ─────────────
@st.cache_data(show_spinner=False)
def _expected_rows(m: Optional[str], d: Optional[str]) -> pd.DataFrame:
    codes = [c for c in [m, d] if c]
    if not codes:
        return pd.DataFrame(columns=["label","source","plasmid_base"])
    with engine().begin() as cx:
        df = _safe(cx, text("""
          SELECT vm.fish_code,
                 COALESCE(
                   string_agg(DISTINCT vm.transgene_base_code || '(' || vm.allele_name || ')',
                              ', ' ORDER BY vm.transgene_base_code || '(' || vm.allele_name || ')'),
                   ''
                 ) AS genotype_pretty
          FROM public.v_fish_main vm
          WHERE vm.allele_name IS NOT NULL AND vm.allele_name <> ''
            AND vm.fish_code = ANY(:codes)
          GROUP BY vm.fish_code
        """), {"codes": codes})
    def toks(s: str) -> list[str]:
        return [p.strip() for p in re.split(r"[;,|]+", s or "") if p.strip()]
    mom_t = toks(" ".join(df.loc[df["fish_code"].eq(m), "genotype_pretty"].astype(str))) if m else []
    dad_t = toks(" ".join(df.loc[df["fish_code"].eq(d), "genotype_pretty"].astype(str))) if d else []
    singles = [{"label": t, "source": "mom"} for t in sorted(set(mom_t))] + \
              [{"label": t, "source": "dad"} for t in sorted(set(dad_t)) if t not in set(mom_t)]
    all_single = [r["label"] for r in singles]
    doubles = [{"label": " ; ".join(sorted(x)), "source": "double"} for x in itertools.combinations(all_single, 2)]
    rows = pd.DataFrame(singles + doubles, columns=["label","source"])
    if rows.empty:
        rows["plasmid_base"] = pd.Series(dtype="string")
        return rows
    rows["plasmid_base"] = rows["label"].map(resolve_plasmid_base_sql).fillna("")
    return rows

# ── UI: search & pick tank pair ─────────────────────────────────────────────
with st.form("search"):
    c1, c2 = st.columns([3,1])
    q = c1.text_input("Search tank pairs (pair code / fish code / tank code / genotype)")
    limit = int(c2.number_input("Limit", 50, 2000, 200))
    st.form_submit_button("Apply")

pairs = list_tank_pairs(q or "", limit)
st.subheader("1) Pick a tank pair")
if pairs.empty:
    st.info("No tank pairs found."); st.stop()

# drop defunct column(s) before showing
pairs = pairs.drop(columns=[c for c in ("fish_pair_code",) if c in pairs.columns]).copy()
pairs.insert(0, "✓", False)

sel = st.data_editor(
    pairs,
    hide_index=True,
    use_container_width=True,
    column_config={"✓": st.column_config.CheckboxColumn("✓", default=False)},
)
chosen = sel.loc[sel["✓"]].head(1)
if chosen.empty:
    st.stop()

tp_code   = chosen.iloc[0].get("tank_pair_code", "")
mom_code  = chosen.iloc[0].get("mom_fish_code", "")
dad_code  = chosen.iloc[0].get("dad_fish_code", "")

st.success(f"Selected {tp_code or '(no code)'} — {mom_code or '???'} × {dad_code or '???'}")

# ── Recent clutches table (one row per clutch) ───────────────────────────────
st.subheader("Recent clutches for this tank pair")
with engine().begin() as cx:
    recent = _safe(cx, text("""
      select cr.cross_run_code as cross_code,
             to_char(cr.cross_date,'YYYY-MM-DD') as cross_date,
             coalesce(cl.clutch_genotype_pretty,'') as clutch_genotype,
             coalesce(cl.clutch_instance_code,'')   as clutch_code,
             to_char(coalesce(cl.created_at, cr.created_at),'YYYY-MM-DD') as created
      from public.crosses cr
      left join public.clutch_instances cl on cl.cross_instance_id = cr.id
      where cr.tank_pair_code = :tp
      order by coalesce(cl.created_at, cr.created_at) desc nulls last
      limit 20
    """), {"tp": tp_code})
if recent.empty:
    st.caption("No recent clutches.")
else:
    st.dataframe(recent, hide_index=True, use_container_width=True)

# ── Expected genotypes (singles pre-checked) ─────────────────────────────────
st.subheader("2) Choose run date & expected genotype labels")
run_date: date = st.date_input("Run date", value=date.today())
note = st.text_input("Run note (optional)", "")

rows = _expected_rows(mom_code, dad_code)
if rows.empty:
    st.caption("No genotype suggestions found.")
    chosen_labels: List[str] = []
else:
    if "✓" not in rows.columns:
        rows.insert(0, "✓", rows["source"].eq("single"))
    edited = st.data_editor(
        rows,
        hide_index=True,
        use_container_width=True,
        column_order=["✓","label","plasmid_base","source"],
        column_config={
            "✓":            st.column_config.CheckboxColumn("✓", default=False),
            "label":        st.column_config.TextColumn("Expected genotype label", disabled=True),
            "plasmid_base": st.column_config.TextColumn("Plasmid base name", disabled=True),
            "source":       st.column_config.TextColumn("Type", disabled=True),
        },
    )
    chosen_labels = edited.loc[edited["✓"], "label"].astype(str).tolist()
    st.caption(f"{len(chosen_labels)} selected")

# ── Schedule (idempotent) ────────────────────────────────────────────────────
st.subheader("3) Schedule cross & clutches")
if st.button("⏱ Schedule cross + clutch(es)", type="primary"):
    creator = getattr(user, "email", None) or user.get("email") if isinstance(user, dict) else None
    creator = creator or os.getenv("USER") or os.getenv("USERNAME") or "unknown"
    try:
        labels = [s.strip() for s in (chosen_labels or []) if isinstance(s, str) and s.strip()]
        if not labels:
            st.error("Pick at least one clutch genotype label before scheduling."); st.stop()

        with engine().begin() as cx:
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
                    {"cid": cross_id, "tp": tp_code, "lbl": lbl}
                )

        st.success(f"Cross {cross_code} scheduled with {len(labels)} clutch(es).")
    except Exception as e:
        st.error(f"Schedule failed: {e}")

st.subheader("Scheduled for this tank pair")
def _load_crosses_and_clutches_for_pair(tp_code: str) -> pd.DataFrame:
    if not tp_code:
        return pd.DataFrame(columns=["cross_code","cross_date","clutch_code","clutch_genotype","created"])
    with engine().begin() as cx:
        return _safe(cx, text("""
          select cr.cross_run_code                                     as cross_code,
                 cr.cross_date                                         as cross_date,
                 coalesce(cl.clutch_instance_code,'')                  as clutch_code,
                 coalesce(cl.clutch_genotype_pretty,'')                as clutch_genotype,
                 coalesce(cl.created_at, cr.created_at)::timestamptz   as created
          from public.crosses cr
          left join public.clutch_instances cl on cl.cross_instance_id = cr.id
          where cr.tank_pair_code = :tp
          order by coalesce(cl.created_at, cr.created_at) desc nulls last
          limit 200
        """), {"tp": tp_code})

sched_df = _load_crosses_and_clutches_for_pair(tp_code)
if sched_df.empty:
    st.caption("No scheduled crosses/clutches yet for this tank pair.")
else:
    st.dataframe(
        sched_df[["cross_code","cross_date","clutch_code","clutch_genotype","created"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "cross_code":      st.column_config.TextColumn("Cross code", disabled=True),
            "cross_date":      st.column_config.DateColumn("Cross date", disabled=True, format="YYYY-MM-DD"),
            "clutch_code":     st.column_config.TextColumn("Clutch code", disabled=True),
            "clutch_genotype": st.column_config.TextColumn("Clutch genotype", disabled=True),
            "created":         st.column_config.DatetimeColumn("Created", disabled=True),
        },
    )