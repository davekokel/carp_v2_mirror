# carp_app/ui/pages/180_🗓️_schedule_new_cross.py
from __future__ import annotations

import sys, pathlib, itertools, re
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
    dbg = pd.read_sql(
        text("select current_database() db, inet_server_addr() host, current_user u"),
        cx,
    )
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# ── helpers ──────────────────────────────────────────────────────────────────
def _safe(cx, q: str | TextClause, p=None) -> pd.DataFrame:
    q = q if isinstance(q, TextClause) else text(q)
    return pd.read_sql(q, cx, params=p or {})

def _cols(schema: str, rel: str) -> Set[str]:
    with engine().begin() as cx:
        df = _safe(
            cx,
            text(
                """
            select column_name
            from information_schema.columns
            where table_schema=:s and table_name=:r
            """
            ),
            {"s": schema, "r": rel},
        )
    return set(df["column_name"].tolist())

def _tank_pair_parent_cols() -> Tuple[str, str]:
    c = _cols("public", "tank_pairs")
    for a, b in (("mother_tank_id", "father_tank_id"), ("tank_id_mother", "tank_id_father")):
        if a in c and b in c:
            return a, b
    raise RuntimeError("public.tank_pairs must have mother/father UUID columns.")

def list_tank_pairs(q: str, limit: int) -> pd.DataFrame:
    mom_col, dad_col = _tank_pair_parent_cols()
    tp_cols = _cols("public", "tank_pairs")
    order_clause = (
        "tp.created_at DESC NULLS LAST, tp.tank_pair_code"
        if "created_at" in tp_cols and "tank_pair_code" in tp_cols
        else "tp.created_at DESC NULLS LAST"
        if "created_at" in tp_cols
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

    sql = text(
        f"""
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
    """
    )
    with engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return df.fillna("")

def _get_possible_labels_for_fish(cx, fish_code: str) -> Set[str]:
    if not fish_code:
        return set()
    df = _safe(
        cx,
        text(
            """
      select jfta.transgene_base_code as base_code,
             jfta.allele_number       as allele_number,
             coalesce(
               ta.allele_name,
               ta.allele_nickname,
               jfta.allele_number::text
             ) as allele_label
      from public.fish f
      join public.join_fish_transgene_alleles jfta on jfta.fish_id = f.id
      left join public.transgene_alleles ta
        on ta.transgene_base_code = jfta.transgene_base_code
       and ta.allele_number       = jfta.allele_number
      where f.fish_code = :fc
    """
        ),
        {"fc": fish_code},
    )
    if df.empty:
        return set()
    return set(df.apply(lambda r: f"{r['base_code']}({r['allele_label']})", axis=1).tolist())

@st.cache_data(show_spinner=False)
def expected_labels_for_parents(mom_fc: str, dad_fc: str) -> pd.DataFrame:
    """
    Compute a set of suggested labels based on the parents' transgene alleles.

    Each label is a human-readable allele option. We store the options per clutch in
    clutch_expected_genotypes and derive a summary string for clutch_instances.clutch_genotype.
    """
    if not mom_fc and not dad_fc:
        return pd.DataFrame(columns=["label", "source"])
    with engine().begin() as cx:
        mom = _get_possible_labels_for_fish(cx, mom_fc)
        dad = _get_possible_labels_for_fish(cx, dad_fc)
    labels = [{"label": s, "source": "mom"} for s in sorted(mom)]
    for s in sorted(dad):
        if s not in mom:
            labels.append({"label": s, "source": "dad"})
    singles = [r["label"] for r in labels]
    doubles = [
        {"label": " ; ".join(t), "source": "double"}
        for t in itertools.combinations(singles, 2)
    ]
    out = pd.DataFrame(labels + doubles, columns=["label", "source"])
    return out

def _clutch_geno_rows_from_selected(df_sel: pd.DataFrame) -> List[str]:
    if df_sel.empty:
        return []
    return [str(s) for s in df_sel["label"].astype(str).tolist() if s.strip()]

# ---- genotype parsing helpers for join table --------------------------------
_LABEL_PART_RE = re.compile(r"^\s*([A-Za-z0-9\-]+)\s*\(([^)]+)\)")

def _parse_label_parts(label: str) -> List[str]:
    """Split a combined label like 'A(x) ; B(y)' into ['A(x)', 'B(y)']."""
    parts = [p.strip() for p in re.split(r"\s*;\s*", label or "") if p.strip()]
    return parts

def _resolve_allele_number(cx, base: str, tok_txt: str) -> Optional[int]:
    """
    Resolve allele_number from transgene_alleles for a given base code and token text.
    token may match allele_name, allele_nickname, or allele_number::text.
    """
    row = cx.execute(
        text("""
          SELECT ta.allele_number
          FROM public.transgene_alleles ta
          WHERE ta.transgene_base_code = :base
            AND (
                 ta.allele_name      = :tok
              OR ta.allele_nickname  = :tok
              OR ta.allele_number::text = :tok
            )
          ORDER BY ta.allele_number
          LIMIT 1
        """),
        {"base": base, "tok": tok_txt},
    ).fetchone()
    return int(row[0]) if row else None

def _insert_expected_alleles_for_label(cx, clutch_id: str, label: str, source: str) -> List[str]:
    """
    For a given label row and source ('mom'/'dad'/'double'), parse all allele parts and
    insert rows into public.clutch_expected_genotypes. Returns a list of canonical
    label strings like 'pDQM005(gu104)' that were successfully inserted.
    """
    canon: List[str] = []
    for part in _parse_label_parts(label):
        m = _LABEL_PART_RE.match(part)
        if not m:
            continue
        base = m.group(1).strip()
        tok_txt = m.group(2).strip()
        if not base or not tok_txt:
            continue
        allele_num = _resolve_allele_number(cx, base, tok_txt)
        if allele_num is None:
            continue
        canon_label = f"{base}({tok_txt})"

        cx.execute(
            text("""
              INSERT INTO public.clutch_expected_genotypes
                (clutch_instance_id, transgene_base_code, allele_number, allele_label, source)
              VALUES (:cid, :base, :anum, :lbl, NULLIF(:src,''))
              ON CONFLICT (clutch_instance_id, transgene_base_code, allele_number) DO NOTHING
            """),
            {"cid": clutch_id, "base": base, "anum": allele_num, "lbl": canon_label, "src": source or None},
        )
        canon.append(canon_label)
    return canon

def _insert_clutch(cx, cross_id: str, run_date: date) -> str:
    """
    Insert a clutch for the given cross.

    clutch_date is defined as one day after the cross run_date.
    """
    row = cx.execute(
        text(
            """
          INSERT INTO public.clutch_instances (id, cross_instance_id, clutch_date)
          VALUES (
            gen_random_uuid(),
            :cid,
            (CAST(:d AS date) + interval '1 day')::date
          )
          RETURNING id
        """
        ),
        {"cid": cross_id, "d": str(run_date)},
    ).fetchone()
    return str(row[0])

# ── UI: search & pick tank pair ──────────────────────────────────────────────
with st.form("search"):
    c1, c2 = st.columns([3, 1])
    q = c1.text_input("Search tank pairs (pair code / fish code / tank code)")
    limit = int(c2.number_input("Limit", 50, 2000, 200))
    st.form_submit_button("Apply")

pairs = list_tank_pairs(q or "", limit)
st.subheader("1) Pick a tank pair")
if pairs.empty:
    st.info("No tank pairs found.")
    st.stop()

pairs = pairs.copy()
pairs.insert(0, "✓", False)
sel = st.data_editor(
    pairs[
        [
            "✓",
            "tank_pair_code",
            "mom_fish_code",
            "dad_fish_code",
            "mom_tank_code",
            "dad_tank_code",
            "created_at",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={"✓": st.column_config.CheckboxColumn("✓", default=False)},
)
chosen = sel.loc[sel["✓"]].head(1)
if chosen.empty:
    st.stop()

tp_code = chosen.iloc[0]["tank_pair_code"]
mom_code = chosen.iloc[0]["mom_fish_code"]
dad_code = chosen.iloc[0]["dad_fish_code"]

st.success(f"Selected {tp_code or '(no code)'} — {mom_code or '???'} × {dad_code or '???'}")

# ── Step 2: expected genotype (specific labels optional) ─────────────────────
st.subheader("2) Choose expected genotype labels (optional)")

rows = expected_labels_for_parents(mom_code, dad_code)
if rows.empty:
    st.caption("No parental alleles found.")
    edited = pd.DataFrame(columns=["✓", "label", "source"])
    chosen_labels: List[str] = []
else:
    if "✓" not in rows.columns:
        rows.insert(0, "✓", rows["source"].eq("mom"))
    edited = st.data_editor(
        rows,
        hide_index=True,
        use_container_width=True,
        column_order=["✓", "label", "source"],
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
note = st.text_input("Run note (optional, not stored yet)", "")

if st.button("⏱ Schedule", type="primary"):
    try:
        with engine().begin() as cx:
            # resolve tank_pair_id from code
            tp_id = cx.execute(
                text(
                    "SELECT id FROM public.tank_pairs WHERE tank_pair_code=:tp LIMIT 1"
                ),
                {"tp": tp_code},
            ).scalar()

            if tp_id is None:
                raise RuntimeError(f"Tank pair {tp_code} not found in DB")

            # crosses has: id, cross_run_code, tank_pair_id, created_at
            row = cx.execute(
                text(
                    """
                  WITH ins AS (
                    INSERT INTO public.crosses (id, tank_pair_id, created_at)
                    SELECT gen_random_uuid(), :tp_id, CAST(:d AS date)
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
                """
                ),
                {"tp_id": tp_id, "d": str(run_date)},
            ).fetchone()

            cross_id = str(row[0])
            cross_code = row[1]

            # 1 clutch per Save click
            clutch_id = _insert_clutch(cx, cross_id, run_date)

            # Insert expected-genotype rows per label into clutch_expected_genotypes
            canon_labels_set: Set[str] = set()
            if not edited.empty:
                rows_sel = edited.loc[edited["✓"]] if "✓" in edited.columns else pd.DataFrame()
                for _, r in rows_sel.iterrows():
                    lbl = str(r.get("label") or "").strip()
                    src = str(r.get("source") or "").strip()
                    canon_labels_set.update(_insert_expected_alleles_for_label(cx, clutch_id, lbl, src))

            # Derive a short clutch_genotype summary string from canonical labels
            summary = ""
            if canon_labels_set:
                labels_sorted = sorted(canon_labels_set)
                if len(labels_sorted) == 1:
                    summary = labels_sorted[0]
                elif len(labels_sorted) <= 3:
                    summary = " / ".join(labels_sorted)
                else:
                    summary = f"mixed ({len(labels_sorted)} alleles)"

                cx.execute(
                    text("""
                      UPDATE public.clutch_instances
                      SET clutch_genotype = :g
                      WHERE id = :cid
                    """),
                    {"g": summary, "cid": clutch_id},
                )

            created = 1

        st.success(f"Scheduled cross {cross_code or ''} with {created} clutch(es).")
    except Exception as e:
        st.error(f"Schedule failed: {e}")

# ── Recent clutches for this tank pair ───────────────────────────────────────
st.subheader("Recently scheduled clutches for this pair")
with engine().begin() as cx:
    recent = _safe(
        cx,
        text("""
      SELECT
        -- clutch code: stored code or CI-<idprefix> fallback
        COALESCE(
          v.clutch_code,
          'CI-' || LEFT(v.clutch_instance_id::text, 8)
        ) AS clutch_code,

        -- clutch_genotype summary from table; fallback to mom × dad for legacy rows
        COALESCE(
          NULLIF(v.clutch_genotype,''),
          TRIM(
            BOTH ' × ' FROM (
              COALESCE(NULLIF(v.mom_genotype,''), '?') || ' × ' ||
              COALESCE(NULLIF(v.dad_genotype,''), '?')
            )
          )
        ) AS clutch_genotype,

        -- cross label: cross_code if present, else TP-... @ date
        COALESCE(
          v.cross_code,
          v.tank_pair_code || ' @ ' || COALESCE(v.cross_date::text, '')
        ) AS cross_code,

        v.cross_date,
        v.clutch_created_at
      FROM public.v_clutches_overview v
      WHERE v.tank_pair_code = :tp
      ORDER BY v.clutch_created_at DESC
      LIMIT 20
    """),
        {"tp": tp_code},
    )

if recent.empty:
    st.caption("No recent clutches for this pair.")
else:
    st.dataframe(
        recent[["clutch_code","clutch_genotype","cross_code","cross_date","clutch_created_at"]],
        hide_index=True,
        use_container_width=True,
    )