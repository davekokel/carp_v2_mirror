# carp_app/ui/pages/180_🗓️_schedule_new_cross.py
from __future__ import annotations

import sys, pathlib, os, itertools, re
from datetime import date
from typing import List, Optional, Set, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text
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

# ── helpers ──────────────────────────────────────────────────────────────────
def _safe(cx, q: str | TextClause, p=None) -> pd.DataFrame:
    q = q if isinstance(q, TextClause) else text(q)
    return pd.read_sql(q, cx, params=p or {})

def _cols(schema: str, rel: str) -> Set[str]:
    with engine().begin() as cx:
        df = _safe(cx, text("""
            select column_name
            from information_schema.columns
            where table_schema=:s and table_name=:r
        """), {"s": schema, "r": rel})
    return set(df["column_name"].tolist())

def _tank_pair_parent_cols() -> Tuple[str, str]:
    c = _cols("public", "tank_pairs")
    for a, b in (("mother_tank_id","father_tank_id"), ("tank_id_mother","tank_id_father")):
        if a in c and b in c:
            return a, b
    raise RuntimeError("public.tank_pairs must have mother/father UUID columns.")

def list_tank_pairs(q: str, limit: int) -> pd.DataFrame:
    mom_col, dad_col = _tank_pair_parent_cols()
    tp_cols = _cols("public", "tank_pairs")
    order_clause = (
        "tp.created_at DESC NULLS LAST, tp.tank_pair_code" if "created_at" in tp_cols and "tank_pair_code" in tp_cols
        else "tp.created_at DESC NULLS LAST" if "created_at" in tp_cols
        else "tp.tank_pair_code"
    )
    like = f"%{q.strip()}%" if q and q.strip() else None
    params = {"lim": int(limit)}
    where_sql = ""
    if like:
        params["like"] = like
        where_sql = (
            "WHERE ("
            "tp.tank_pair_code ILIKE :like OR "
            "m.fish_code ILIKE :like OR "
            "d.fish_code ILIKE :like OR "
            "m.tank_code ILIKE :like OR "
            "d.tank_code ILIKE :like)"
        )
    created_sel = "tp.created_at" if "created_at" in tp_cols else "NULL::timestamptz"

    sql = text(f"""
        WITH t AS (
          SELECT t.id::uuid AS tank_id, t.tank_code, f.fish_code
          FROM public.tanks t
          JOIN public.fish  f ON f.id = t.fish_id
        )
        SELECT
          tp.id::text       AS tank_pair_id,
          tp.tank_pair_code AS tank_pair_code,
          {created_sel}     AS created_at,
          m.fish_code       AS mom_fish_code,
          d.fish_code       AS dad_fish_code,
          m.tank_code       AS mom_tank_code,
          d.tank_code       AS dad_tank_code
        FROM public.tank_pairs tp
        LEFT JOIN t AS m ON m.tank_id = tp.{mom_col}
        LEFT JOIN t AS d ON d.tank_id = tp.{dad_col}
        {where_sql}
        ORDER BY {order_clause}
        LIMIT :lim
    """)
    with engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return df.fillna("")

def _get_possible_labels_for_fish(cx, fish_code: str) -> Set[str]:
    if not fish_code:
        return set()
    df = _safe(cx, text("""
      select jfta.transgene_base_code as base_code,
             jfta.allele_number       as allele_number,
             coalesce(ta.allele_name, ta.allele_nickname, jfta.allele_number::text) as allele_label
      from public.fish f
      join public.join_fish_transgene_alleles jfta on jfta.fish_id = f.id
      left join public.transgene_alleles ta
        on ta.transgene_base_code = jfta.transgene_base_code
       and ta.allele_number       = jfta.allele_number
      where f.fish_code = :fc
    """), {"fc": fish_code})
    if df.empty:
        return set()
    return set(df.apply(lambda r: f"{r['base_code']}({r['allele_label']})", axis=1).tolist())

@st.cache_data(show_spinner=False)
def expected_labels_for_parents(mom_fc: str, dad_fc: str) -> pd.DataFrame:
    if not mom_fc and not dad_fc:
        return pd.DataFrame(columns=["label","source"])
    with engine().begin() as cx:
        mom = _get_possible_labels_for_fish(cx, mom_fc)
        dad = _get_possible_labels_for_fish(cx, dad_fc)
    labels = [{"label": s, "source": "mom"} for s in sorted(mom)]
    for s in sorted(dad):
        if s not in mom:
            labels.append({"label": s, "source": "dad"})
    singles = [r["label"] for r in labels]
    doubles = [{"label": " ; ".join(t), "source": "double"} for t in itertools.combinations(singles, 2)]
    out = pd.DataFrame(labels + doubles, columns=["label","source"])
    return out

def _clutch_geno_rows_from_selected(df_sel: pd.DataFrame) -> List[str]:
    if df_sel.empty:
        return []
    return [str(s) for s in df_sel["label"].astype(str).tolist() if s.strip()]

def _upsert_expected_from_label(cx, clutch_id: str, label: str) -> None:
    """
    Persist expected transgene allele(s) for a clutch from a selected label.
    Supports "BASE(allele)" and combo labels like "A(x) ; B(y)".
    Resolves allele_number by name/nickname or by numeric token (safely).
    """
    if not (label or "").strip():
        return

    parts = [p.strip() for p in re.split(r"\s*;\s*", label) if p.strip()]
    for part in parts:
        m_base = re.match(r"^\s*([A-Za-z0-9\-]+)\s*\(", part)
        m_tok  = re.search(r"\(([^\)]+)\)", part)
        base = m_base.group(1) if m_base else None
        tok_txt = (m_tok.group(1).strip() if m_tok else "") if m_tok else ""
        if not base:
            continue

        tok_num = int(tok_txt) if tok_txt.isdigit() else None

        # Try name/nickname or numeric token (no unsafe cast)
        allele_num = cx.execute(
            text("""
              SELECT ta.allele_number
              FROM public.transgene_alleles ta
              WHERE ta.transgene_base_code = :base
                AND (
                     (:tok_txt <> '' AND (ta.allele_name = :tok_txt OR ta.allele_nickname = :tok_txt))
                  OR (:tok_num IS NOT NULL AND ta.allele_number = :tok_num)
                )
              ORDER BY ta.allele_number
              LIMIT 1
            """),
            {"base": base, "tok_txt": tok_txt, "tok_num": tok_num}
        ).scalar()

        # Fallback: if no token match but the base exists, use the first allele
        if allele_num is None:
            allele_num = cx.execute(
                text("""
                  SELECT ta.allele_number
                  FROM public.transgene_alleles ta
                  WHERE ta.transgene_base_code = :base
                  ORDER BY ta.allele_number
                  LIMIT 1
                """),
                {"base": base}
            ).scalar()

        if allele_num is None:
            continue

        cx.execute(
            text("""
              INSERT INTO public.join_clutch_transgene_alleles
                (clutch_instance_id, transgene_base_code, allele_number)
              VALUES (:cid, :base, :anum)
              ON CONFLICT DO NOTHING
            """),
            {"cid": clutch_id, "base": base, "anum": int(allele_num)}
        )

# ── UI: search & pick tank pair ──────────────────────────────────────────────
with st.form("search"):
    c1, c2 = st.columns([3,1])
    q = c1.text_input("Search tank pairs (pair code / fish code / tank code)")
    limit = int(c2.number_input("Limit", 50, 2000, 200))
    st.form_submit_button("Apply")

pairs = list_tank_pairs(q or "", limit)
st.subheader("1) Pick a tank pair")
if pairs.empty:
    st.info("No tank pairs found."); st.stop()

pairs = pairs.copy()
pairs.insert(0, "✓", False)
sel = st.data_editor(
    pairs[["✓","tank_pair_code","mom_fish_code","dad_fish_code","mom_tank_code","dad_tank_code","created_at"]],
    hide_index=True, use_container_width=True,
    column_config={"✓": st.column_config.CheckboxColumn("✓", default=False)},
)
chosen = sel.loc[sel["✓"]].head(1)
if chosen.empty:
    st.stop()

tp_code   = chosen.iloc[0]["tank_pair_code"]
mom_code  = chosen.iloc[0]["mom_fish_code"]
dad_code  = chosen.iloc[0]["dad_fish_code"]

st.success(f"Selected {tp_code or '(no code)'} — {mom_code or '???'} × {dad_code or '???'}")

# ── Step 2: expected genotype (specific labels optional) ─────────────────────
st.subheader("2) Choose expected genotype labels (optional)")

rows = expected_labels_for_parents(mom_code, dad_code)
if rows.empty:
    st.caption("No parental alleles found.")
    edited = pd.DataFrame(columns=["✓","label","source"])
    chosen_labels: List[str] = []
else:
    if "✓" not in rows.columns:
        rows.insert(0, "✓", rows["source"].eq("mom"))
    edited = st.data_editor(
        rows, hide_index=True, use_container_width=True,
        column_order=["✓","label","source"],
        column_config={
            "✓": st.column_config.CheckboxColumn("✓", default=False),
            "label": st.column_config.TextColumn("Expected label", disabled=True),
            "source": st.column_config.TextColumn("from", disabled=True, width="small"),
        },
        height=260,
    )
    chosen_labels = _clutch_geno_rows_from_selected(edited.loc[edited["✓"]])
st.caption(f"{len(chosen_labels)} specific label(s) selected")

# ── Step 3: schedule cross & clutches ────────────────────────────────────────
st.subheader("3) Schedule cross & create clutches")
run_date = st.date_input("Run date", value=date.today())
note = st.text_input("Run note (optional)", "")

def _insert_clutch(cx, cross_id: str, label: Optional[str]) -> str:
    """
    Insert a clutch for (cross_id, label). If one already exists with the same
    normalized label, return its id (idempotent).
    """
    q = text("""
      WITH ins AS (
        INSERT INTO public.clutch_instances (id, cross_instance_id, clutch_genotype_pretty)
        VALUES (gen_random_uuid(), :cid, COALESCE(:lbl,''))
        ON CONFLICT (cross_instance_id, normalized_genotype) DO NOTHING
        RETURNING id
      ),
      sel AS (
        SELECT id FROM ins
        UNION ALL
        SELECT id
        FROM public.clutch_instances
        WHERE cross_instance_id = :cid
          AND normalized_genotype = regexp_replace(lower(COALESCE(:lbl,'')), '[^a-z0-9]+', '', 'g')
          AND NOT EXISTS (SELECT 1 FROM ins)
      )
      SELECT id FROM sel LIMIT 1;
    """)
    row = cx.execute(q, {"cid": cross_id, "lbl": (label or "")}).fetchone()
    return str(row[0])

if st.button("⏱ Schedule", type="primary"):
    try:
        with engine().begin() as cx:
            # resolve tank_pair_id
            tp_id = cx.execute(
                text("SELECT id FROM public.tank_pairs WHERE tank_pair_code=:tp LIMIT 1"),
                {"tp": tp_code}
            ).scalar()

            # idempotent cross for (tank_pair_id, date(created_at))
            row = cx.execute(
                text("""
                  WITH ins AS (
                    INSERT INTO public.crosses (id, tank_pair_id, created_at, note)
                    SELECT gen_random_uuid(), :tp_id, CAST(:d AS date), :note
                    WHERE NOT EXISTS (
                      SELECT 1 FROM public.crosses
                      WHERE tank_pair_id = :tp_id
                        AND DATE(created_at) = CAST(:d AS date)
                    )
                    RETURNING id, cross_run_code
                  ),
                  sel AS (
                    SELECT id, cross_run_code FROM ins
                    UNION ALL
                    SELECT id, cross_run_code
                    FROM public.crosses
                    WHERE tank_pair_id = :tp_id
                      AND DATE(created_at) = CAST(:d AS date)
                      AND NOT EXISTS (SELECT 1 FROM ins)
                  )
                  SELECT id, cross_run_code FROM sel LIMIT 1;
                """),
                {"tp_id": tp_id, "d": str(run_date), "note": note}
            ).fetchone()
            cross_id = str(row[0])

            # create clutches (one per selected label), and persist expected alleles for each
            created = 0
            seen = set()
            for lbl in chosen_labels:
                cid = _insert_clutch(cx, cross_id, lbl)
                _upsert_expected_from_label(cx, cid, lbl)  # <-- expected links for view rollups
                norm = re.sub(r"[^a-z0-9]+", "", (lbl or "").lower())
                if norm not in seen:
                    seen.add(norm)
                    created += 1

        st.success(f"Scheduled cross {row[1] or ''} with {created} clutch(es).")
    except Exception as e:
        st.error(f"Schedule failed: {e}")

# ── Recent clutches for this tank pair ───────────────────────────────────────
st.subheader("Recently scheduled clutches for this pair")
with engine().begin() as cx:
    recent = _safe(cx, text("""
      SELECT
        ci.clutch_instance_code                  AS clutch_code,
        COALESCE(ci.clutch_genotype_pretty,'')  AS clutch_genotype,
        cr.cross_run_code                        AS cross_code,
        COALESCE(cr.created_at::date, ci.created_at::date) AS cross_date,
        ci.created_at                            AS clutch_created_at
      FROM public.clutch_instances ci
      LEFT JOIN public.crosses cr ON cr.id = ci.cross_instance_id
      WHERE cr.tank_pair_id = (SELECT id FROM public.tank_pairs WHERE tank_pair_code=:tp LIMIT 1)
      ORDER BY ci.created_at DESC
      LIMIT 20
    """), {"tp": tp_code})

if recent.empty:
    st.caption("No recent clutches for this pair.")
else:
    st.dataframe(
        recent[["clutch_code","clutch_genotype","cross_code","cross_date","clutch_created_at"]],
        hide_index=True, use_container_width=True
    )