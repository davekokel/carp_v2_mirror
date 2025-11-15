# carp_app/ui/pages/180_🗓️_schedule_new_cross.py
from __future__ import annotations

import sys, pathlib, itertools, re
from datetime import date
from typing import List, Optional, Set, Tuple, Dict, Any

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

# ── Auth / page setup ────────────────────────────────────────────────────────
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
            text("""
              select column_name
              from information_schema.columns
              where table_schema=:s and table_name=:r
            """),
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
    """
    Enriched tank pair list using v_fish_overview so humans can see genotype/fusions
    directly in the picker.
    """
    mom_col, dad_col = _tank_pair_parent_cols()
    tp_cols = _cols("public", "tank_pairs")
    order_clause = (
        "tp.created_at DESC NULLS LAST, tp.tank_pair_code"
        if "created_at" in tp_cols and "tank_pair_code" in tp_cols
        else "tp.created_at DESC NULLS LAST"
        if "created_at" in tp_cols
        else "tp.tank_pair_code"
    )
    created_sel = "tp.created_at" if "created_at" in tp_cols else "NULL::timestamptz"
    like = f"%{q.strip()}%" if q and q.strip() else None

    sql = text(f"""
        WITH tm AS (
          SELECT t.id::uuid AS tank_id, t.tank_code, f.fish_code
          FROM public.tanks t
          JOIN public.fish  f ON f.id = t.fish_id
        ),
        mom AS (
          SELECT
            m.tank_id,
            m.tank_code,
            m.fish_code,
            vo.genotype_pretty      AS genotype,
            vo.fusions,
            vo.fluors,
            vo.tags,
            vo.markers,
            vo.nickname,
            vo.genetic_background,
            vo.line_building_stage,
            vo.birthday
          FROM tm m
          LEFT JOIN public.v_fish_overview vo ON vo.fish_code_raw = m.fish_code
        ),
        dad AS (
          SELECT
            d.tank_id,
            d.tank_code,
            d.fish_code,
            vo.genotype_pretty      AS genotype,
            vo.fusions,
            vo.fluors,
            vo.tags,
            vo.markers,
            vo.nickname,
            vo.genetic_background,
            vo.line_building_stage,
            vo.birthday
          FROM tm d
          LEFT JOIN public.v_fish_overview vo ON vo.fish_code_raw = d.fish_code
        )
        SELECT
          tp.id::text       AS tank_pair_id,
          tp.tank_pair_code AS tank_pair_code,
          {created_sel}     AS created_at,

          mom.fish_code           AS mom_fish_code,
          mom.tank_code           AS mom_tank_code,
          mom.genotype            AS mom_genotype,
          mom.fusions             AS mom_fusions,
          mom.fluors              AS mom_fluors,
          mom.tags                AS mom_tags,
          mom.markers             AS mom_markers,
          mom.nickname            AS mom_nickname,
          mom.genetic_background  AS mom_genetic_background,
          mom.line_building_stage AS mom_line_building_stage,
          mom.birthday            AS mom_birthday,

          dad.fish_code           AS dad_fish_code,
          dad.tank_code           AS dad_tank_code,
          dad.genotype            AS dad_genotype,
          dad.fusions             AS dad_fusions,
          dad.fluors              AS dad_fluors,
          dad.tags                AS dad_tags,
          dad.markers             AS dad_markers,
          dad.nickname            AS dad_nickname,
          dad.genetic_background  AS dad_genetic_background,
          dad.line_building_stage AS dad_line_building_stage,
          dad.birthday            AS dad_birthday

        FROM public.tank_pairs tp
        LEFT JOIN mom ON mom.tank_id = tp.{mom_col}
        LEFT JOIN dad ON dad.tank_id = tp.{dad_col}
        { "WHERE " + " OR ".join([
            "tp.tank_pair_code ILIKE :like",
            "COALESCE(mom.fish_code,'')   ILIKE :like",
            "COALESCE(dad.fish_code,'')   ILIKE :like",
            "COALESCE(mom.tank_code,'')   ILIKE :like",
            "COALESCE(dad.tank_code,'')   ILIKE :like",
            "COALESCE(mom.genotype,'')    ILIKE :like",
            "COALESCE(dad.genotype,'')    ILIKE :like",
            "COALESCE(mom.fusions,'')     ILIKE :like",
            "COALESCE(dad.fusions,'')     ILIKE :like",
            "COALESCE(mom.fluors,'')      ILIKE :like",
            "COALESCE(dad.fluors,'')      ILIKE :like",
            "COALESCE(mom.tags,'')        ILIKE :like",
            "COALESCE(dad.tags,'')        ILIKE :like",
            "COALESCE(mom.markers,'')     ILIKE :like",
            "COALESCE(dad.markers,'')     ILIKE :like"
          ]) if like else "" }
        ORDER BY {order_clause}
        LIMIT :lim
    """)
    params = {"lim": int(limit)}
    if like:
        params["like"] = like

    with engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return df.fillna("")

def _get_possible_labels_for_fish(cx, fish_code: str) -> Set[str]:
    if not fish_code:
        return set()
    df = _safe(
        cx,
        text("""
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
    """),
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
    public.clutch_expected_genotypes and derive summary strings in v_clutches_overview.
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

# ---- genotype parsing helpers for join + patterns ---------------------------
_LABEL_PART_RE = re.compile(r"^\s*([A-Za-z0-9_\-]+)\s*\(([^)]+)\)")

def _parse_label_parts(label: str) -> List[str]:
    """Split a combined label like 'A(x) ; B(y)' into ['A(x)', 'B(y)']."""
    return [p.strip() for p in re.split(r"\s*;\s*", label or "") if p.strip()]

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
                 lower(ta.allele_name)         = lower(:tok)
              OR lower(ta.allele_nickname)     = lower(:tok)
              OR ta.allele_number::text        = :tok
            )
          ORDER BY ta.allele_number
          LIMIT 1
        """),
        {"base": base, "tok": tok_txt},
    ).fetchone()
    return int(row[0]) if row else None

def _insert_expected_alleles_for_label(
    cx,
    clutch_id: str,
    label: str,
    source: str,
    pattern_index: int,
) -> List[str]:
    """
    For a given label row and source ('mom'/'dad'/'double'), parse all allele parts and
    insert rows into public.clutch_expected_genotypes for the given pattern_index.
    Returns a list of canonical allele labels like 'pDQM005(gu104)' that were inserted.
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
                (clutch_instance_id, pattern_index,
                 transgene_base_code, allele_number, allele_label, source)
              VALUES (:cid, :pidx, :base, :anum, :lbl, NULLIF(:src,''))
              ON CONFLICT (clutch_instance_id, pattern_index, transgene_base_code, allele_number)
              DO NOTHING
            """),
            {
                "cid":  clutch_id,
                "pidx": int(pattern_index),
                "base": base,
                "anum": allele_num,
                "lbl":  canon_label,
                "src":  source or None,
            },
        )
        canon.append(canon_label)
    return canon

def _insert_clutch(cx, cross_id: str, run_date: date) -> str:
    """
    Insert a clutch for the given cross.

    clutch_date is defined as one day after the cross run_date.
    """
    row = cx.execute(
        text("""
          INSERT INTO public.clutch_instances (id, cross_instance_id, clutch_date)
          VALUES (
            gen_random_uuid(),
            :cid,
            (CAST(:d AS date) + interval '1 day')::date
          )
          RETURNING id
        """),
        {"cid": cross_id, "d": str(run_date)},
    ).fetchone()
    return str(row[0])

# ── UI: search & pick tank pair ──────────────────────────────────────────────
with st.form("search"):
    c1, c2 = st.columns([3, 1])
    q = c1.text_input("Search tank pairs (code / fish / genotype / fusions / fluors / tags)")
    limit = int(c2.number_input("Limit", 50, 2000, 200))
    st.form_submit_button("Apply")

pairs = list_tank_pairs(q or "", limit)
st.subheader("1) Pick a tank pair")
if pairs.empty:
    st.info("No tank pairs found.")
    st.stop()

pairs = pairs.copy()
pairs.insert(0, "✓", False)

picker_cols = [
    "tank_pair_code",
    "mom_fish_code", "dad_fish_code",
    "mom_genotype", "dad_genotype",
    "mom_fusions", "dad_fusions",
    "created_at",
]
picker_cols = [c for c in picker_cols if c in pairs.columns]

sel = st.data_editor(
    pairs[["✓"] + picker_cols],
    hide_index=True,
    use_container_width=True,
    column_config={"✓": st.column_config.CheckboxColumn("✓", default=False)},
    key="tank_pair_picker",
)
chosen = sel.loc[sel["✓"]].head(1)
if chosen.empty:
    st.stop()

row_id = pairs.index[sel["✓"]].tolist()[0]
pair_row = pairs.iloc[row_id]

tp_code = pair_row["tank_pair_code"]
mom_code = pair_row["mom_fish_code"]
dad_code = pair_row["dad_fish_code"]

st.success(f"Selected {tp_code or '(no code)'} — {mom_code or '???'} × {dad_code or '???'}")

# ── Mother / Father profile pivots (like overview tank pairs) ───────────────
def _pivot_profile(title: str, d: Dict[str, Any]):
    rows = [
        {"Field": "Fish code",           "Value": d.get("fish_code","")},
        {"Field": "Tank code",           "Value": d.get("tank_code","")},
        {"Field": "Nickname",            "Value": d.get("nickname","")},
        {"Field": "Genetic background",  "Value": d.get("genetic_background","")},
        {"Field": "Line building stage", "Value": d.get("line_building_stage","")},
        {"Field": "Birthday",            "Value": d.get("birthday","")},
        {"Field": "Genotype",            "Value": d.get("genotype","")},
        {"Field": "Fusions",             "Value": d.get("fusions","")},
        {"Field": "Fluors",              "Value": d.get("fluors","")},
        {"Field": "Tags",                "Value": d.get("tags","")},
        {"Field": "Markers",             "Value": d.get("markers","")},
    ]
    st.subheader(title)
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

mom_profile = {
    "fish_code":           pair_row.get("mom_fish_code",""),
    "tank_code":           pair_row.get("mom_tank_code",""),
    "nickname":            pair_row.get("mom_nickname",""),
    "genetic_background":  pair_row.get("mom_genetic_background",""),
    "line_building_stage": pair_row.get("mom_line_building_stage",""),
    "birthday":            pair_row.get("mom_birthday",""),
    "genotype":            pair_row.get("mom_genotype",""),
    "fusions":             pair_row.get("mom_fusions",""),
    "fluors":              pair_row.get("mom_fluors",""),
    "tags":                pair_row.get("mom_tags",""),
    "markers":             pair_row.get("mom_markers",""),
}
dad_profile = {
    "fish_code":           pair_row.get("dad_fish_code",""),
    "tank_code":           pair_row.get("dad_tank_code",""),
    "nickname":            pair_row.get("dad_nickname",""),
    "genetic_background":  pair_row.get("dad_genetic_background",""),
    "line_building_stage": pair_row.get("dad_line_building_stage",""),
    "birthday":            pair_row.get("dad_birthday",""),
    "genotype":            pair_row.get("dad_genotype",""),
    "fusions":             pair_row.get("dad_fusions",""),
    "fluors":              pair_row.get("dad_fluors",""),
    "tags":                pair_row.get("dad_tags",""),
    "markers":             pair_row.get("dad_markers",""),
}

c1, c2 = st.columns(2)
with c1:
    _pivot_profile("Mother — profile", mom_profile)
with c2:
    _pivot_profile("Father — profile", dad_profile)

# ── Step 2: expected genotype (specific labels optional) ─────────────────────
st.subheader("2) Choose expected genotype labels (optional)")

rows = expected_labels_for_parents(mom_code, dad_code)
if rows.empty:
    st.caption("No parental alleles found.")
    edited = pd.DataFrame(columns=["✓", "label", "source"])
    chosen_labels: List[str] = []
else:
    if "✓" not in rows.columns:
        # default: all expected genotypes selected
        rows.insert(0, "✓", True)
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
        key="expected_labels_editor",
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
                text("SELECT id FROM public.tank_pairs WHERE tank_pair_code=:tp LIMIT 1"),
                {"tp": tp_code},
            ).scalar()

            if tp_id is None:
                raise RuntimeError(f"Tank pair {tp_code} not found in DB")

            # crosses has: id, cross_run_code, tank_pair_id, created_at
            row = cx.execute(
                text("""
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
                """),
                {"tp_id": tp_id, "d": str(run_date)},
            ).fetchone()

            cross_id = str(row[0])
            cross_code = row[1]

            # 1 clutch per Save click
            clutch_id = _insert_clutch(cx, cross_id, run_date)

            # Insert expected-genotype rows per pattern index
            pattern_idx = 0
            if not edited.empty:
                rows_sel = edited.loc[edited["✓"]] if "✓" in edited.columns else pd.DataFrame()
                for _, r in rows_sel.iterrows():
                    lbl = str(r.get("label") or "").strip()
                    src = str(r.get("source") or "").strip()
                    pattern_idx += 1
                    _insert_expected_alleles_for_label(
                        cx,
                        clutch_id,
                        lbl,
                        src,
                        pattern_index=pattern_idx,
                    )

        st.success(f"Scheduled cross {cross_code or ''} with 1 clutch.")
    except Exception as e:
        st.error(f"Schedule failed: {e}")

# ── Recently scheduled clutches for this pair ───────────────────────────────
st.subheader("Recently scheduled clutches for this pair")
with engine().begin() as cx:
    recent = _safe(
        cx,
        text("""
      WITH base AS (
        SELECT *
        FROM public.v_clutches_overview v
        WHERE v.tank_pair_code = :tp
        ORDER BY v.clutch_created_at DESC
        LIMIT 20
      ),
      allele_counts AS (
        SELECT
          ceg.clutch_instance_id,
          COUNT(DISTINCT (ceg.transgene_base_code, ceg.allele_number))::int AS n_alleles
        FROM public.clutch_expected_genotypes ceg
        GROUP BY ceg.clutch_instance_id
      ),
      pattern_counts AS (
        SELECT
          ceg.clutch_instance_id,
          COUNT(DISTINCT ceg.pattern_index)::int AS n_genotypes
        FROM public.clutch_expected_genotypes ceg
        WHERE ceg.pattern_index IS NOT NULL
        GROUP BY ceg.clutch_instance_id
      )
      SELECT
        COALESCE(
          b.clutch_code,
          'CI-' || LEFT(b.clutch_instance_id::text, 8)
        ) AS clutch_code,

        COALESCE(ac.n_alleles, 0)    AS n_alleles,
        COALESCE(pc.n_genotypes, 0)  AS n_genotypes,

        CASE
            WHEN ac.n_alleles IS NULL OR ac.n_alleles = 0 THEN
                TRIM(
                BOTH ' × ' FROM (
                    COALESCE(NULLIF(b.mom_genotype,''), '?') || ' × ' ||
                    COALESCE(NULLIF(b.dad_genotype,''), '?')
                )
                )
            WHEN ac.n_alleles = 1 THEN
                COALESCE(b.clutch_genotype_pretty, b.clutch_genotype)
            WHEN ac.n_alleles = 2 THEN
                REPLACE(COALESCE(b.clutch_genotype_pretty, b.clutch_genotype), ', ', ' + ')
            ELSE
                'mixed (' || ac.n_alleles || ' alleles)'
            END AS alleles_rollup,

        COALESCE(
          b.cross_code,
          b.tank_pair_code || ' @ ' || COALESCE(b.cross_date::text, '')
        ) AS cross_code,

        b.cross_date,
        b.clutch_created_at
      FROM base b
      LEFT JOIN allele_counts  ac ON ac.clutch_instance_id = b.clutch_instance_id
      LEFT JOIN pattern_counts pc ON pc.clutch_instance_id = b.clutch_instance_id
      ORDER BY b.clutch_created_at DESC
      """),
        {"tp": tp_code},
    )

if recent.empty:
    st.caption("No recent clutches for this pair.")
else:
    st.dataframe(
    recent[
        ["clutch_code", "n_alleles", "n_genotypes", "alleles_rollup",
         "cross_code", "cross_date", "clutch_created_at"]
    ],
    hide_index=True,
    use_container_width=True,
)