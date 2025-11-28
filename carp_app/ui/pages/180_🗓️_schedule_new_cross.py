from __future__ import annotations

import sys
import os
import pathlib
from datetime import date, timedelta
from typing import Optional, Tuple, List, Dict

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# -------- repo bootstrap --------
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock() -> None:
        ...
from carp_app.ui.lib.page_engine import engine as _engine

# -------- auth & page --------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 🗓️ Schedule new cross",
    page_icon="🗓️",
    layout="wide",
)
st.title("🗓️ Schedule new cross")


def eng() -> Engine:
    return _engine()


def _norm(s: str | None) -> Optional[str]:
    return s.strip() if isinstance(s, str) else None


# ---------- Step 1: tank pair list (v11 fish star) ----------
def list_tank_pairs(q: str, limit: int) -> pd.DataFrame:
    qn = _norm(q)
    like = f"%{qn}%" if qn else None

    sql = text(
        """
        WITH tm AS (
          SELECT
            t.id::uuid        AS tank_id,
            t.tank_code       AS tank_code,
            t.status          AS status,
            fis.fish_code     AS fish_code,
            fis.treatments_and_transgenes AS genotype
          FROM public.tanks t
          LEFT JOIN public.v11_fish_instance_star fis
            ON fis.tank_id = t.id
          WHERE lower(trim(t.status)) = 'active'
        ),
        mom AS (
          SELECT m.tank_id, m.tank_code, m.fish_code, m.genotype FROM tm m
        ),
        dad AS (
          SELECT d.tank_id, d.tank_code, d.fish_code, d.genotype FROM tm d
        ),
        pairs AS (
          SELECT
            tp.id::uuid        AS tank_pair_id,
            tp.tank_pair_code  AS tank_pair_code,
            tp.created_at      AS created_at,
            mom.fish_code      AS mom_fish_code,
            mom.tank_code      AS mom_tank_code,
            mom.genotype       AS mom_genotype,
            dad.fish_code      AS dad_fish_code,
            dad.tank_code      AS dad_tank_code,
            dad.genotype       AS dad_genotype
          FROM public.tank_pairs tp
          LEFT JOIN mom ON mom.tank_id = tp.mother_tank_id
          LEFT JOIN dad ON dad.tank_id = tp.father_tank_id
        )
        SELECT
          tank_pair_id,
          tank_pair_code,
          created_at,
          mom_fish_code,
          mom_tank_code,
          mom_genotype,
          dad_fish_code,
          dad_tank_code,
          dad_genotype
        FROM pairs
        WHERE (
          :q IS NULL
          OR tank_pair_code ILIKE :ql
          OR mom_tank_code  ILIKE :ql
          OR mom_fish_code  ILIKE :ql
          OR dad_tank_code  ILIKE :ql
          OR dad_fish_code  ILIKE :ql
        )
        ORDER BY created_at DESC NULLS LAST, tank_pair_code
        LIMIT :lim
        """
    )
    params = {"q": qn if qn else None, "ql": like, "lim": int(limit)}
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    for c in df.select_dtypes(include=["object"]).columns:
        df[c] = df[c].astype("string")
    return df


# ---------- Step 1a: parents with v11 standard 6 ----------
def get_parent_detail(tp_id: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          'mother' AS role,
          mt.tank_code AS tank_code,
          mf.fish_code AS fish_code,
          fis.genotype_basecode_code,
          fis.genotype_transgene_allele_code,
          fis.treatments_and_transgenes,
          fis.all_fluor_tag_rollup,
          fis.all_organelle_fluor_rollup
        FROM public.tank_pairs tp
        JOIN public.tanks mt
          ON mt.id = tp.mother_tank_id
        LEFT JOIN public.fish_instances_v10 mf
          ON mf.id = mt.fish_instance_id
        LEFT JOIN public.v11_fish_instance_star fis
          ON fis.fish_instance_id = mf.id
        WHERE tp.id = :tp_id

        UNION ALL

        SELECT
          'father' AS role,
          ft.tank_code AS tank_code,
          ff.fish_code AS fish_code,
          fis.genotype_basecode_code,
          fis.genotype_transgene_allele_code,
          fis.treatments_and_transgenes,
          fis.all_fluor_tag_rollup,
          fis.all_organelle_fluor_rollup
        FROM public.tank_pairs tp
        JOIN public.tanks ft
          ON ft.id = tp.father_tank_id
        LEFT JOIN public.fish_instances_v10 ff
          ON ff.id = ft.fish_instance_id
        LEFT JOIN public.v11_fish_instance_star fis
          ON fis.fish_instance_id = ff.id
        WHERE tp.id = :tp_id

        ORDER BY role;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"tp_id": tp_id})
    return df.fillna("")


# ---------- Step 2: expected genotypes from join_line_alleles ----------
def compute_expected_genotypes_for_tank_pair(tp_id: str) -> pd.DataFrame:
    sql = text(
        """
        WITH mom_line AS (
          SELECT fl.id AS line_id
          FROM public.tank_pairs tp
          JOIN public.tanks mt
            ON mt.id = tp.mother_tank_id
          JOIN public.fish_instances_v10 mf
            ON mf.id = mt.fish_instance_id
          JOIN public.fish_lines fl
            ON fl.id = mf.line_id
          WHERE tp.id = :tp_id
        ),
        dad_line AS (
          SELECT fl.id AS line_id
          FROM public.tank_pairs tp
          JOIN public.tanks ft
            ON ft.id = tp.father_tank_id
          JOIN public.fish_instances_v10 ff
            ON ff.id = ft.fish_instance_id
          JOIN public.fish_lines fl
            ON fl.id = ff.line_id
          WHERE tp.id = :tp_id
        ),
        mom_alleles AS (
          SELECT
            'mother' AS role,
            c.base_code,
            ta.allele_name
          FROM mom_line ml
          JOIN public.join_line_alleles jla
            ON jla.line_id = ml.line_id
          JOIN public.constructs c
            ON c.id = jla.construct_id
          JOIN public.transgene_alleles ta
            ON ta.transgene_base_code = c.base_code
           AND ta.allele_number       = jla.allele_number
        ),
        dad_alleles AS (
          SELECT
            'father' AS role,
            c.base_code,
            ta.allele_name
          FROM dad_line dl
          JOIN public.join_line_alleles jla
            ON jla.line_id = dl.line_id
          JOIN public.constructs c
            ON c.id = jla.construct_id
          JOIN public.transgene_alleles ta
            ON ta.transgene_base_code = c.base_code
           AND ta.allele_number       = jla.allele_number
        )
        SELECT * FROM mom_alleles
        UNION ALL
        SELECT * FROM dad_alleles
        ORDER BY role, base_code, allele_name;
        """
    )
    with eng().begin() as cx:
        alleles_df = pd.read_sql(sql, cx, params={"tp_id": tp_id})

    allele_things: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for _, row in alleles_df.iterrows():
        base = str(row["base_code"])
        allele = str(row["allele_name"])
        key = (base, allele)
        if key in seen:
            continue
        seen.add(key)
        allele_label = f"Tg({base}){allele}"
        allele_things.append(
            {"base_code": base, "allele_name": allele, "label": allele_label}
        )

    n = len(allele_things)
    if n == 0 or n > 10:
        return pd.DataFrame(
            columns=[
                "label",
                "treatment_code",
                "genotype_basecode_code",
                "genotype_transgene_allele_code",
                "treatments_and_transgenes",
                "all_fluor_tag_rollup",
                "all_organelle_fluor_rollup",
                "expected_fraction",
                "expected_percent_label",
                "is_enabled",
                "notes",
            ]
        )

    base_codes = sorted({a["base_code"] for a in allele_things})
    markers: Dict[str, Dict[str, str]] = {}
    if base_codes:
        sql2 = text(
            """
            SELECT
              construct_code,
              fusion_pretty,
              organelle_fluors
            FROM public.v10_constructs_overview
            WHERE construct_code = ANY(:codes)
            """
        )
        with eng().begin() as cx:
            df_mark = pd.read_sql(sql2, cx, params={"codes": base_codes})
        for _, r in df_mark.iterrows():
            markers[str(r["construct_code"])] = {
                "fusion_pretty": r.get("fusion_pretty") or "",
                "organelle_fluor": r.get("organelle_fluors") or "",
            }

    rows = []
    total_masks = 2**n
    for mask in range(1, total_masks):
        subset = [allele_things[i] for i in range(n) if (mask & (i + 1) >> 1) or (mask & (1 << i))]
        subset = sorted(subset, key=lambda a: (a["base_code"], a["allele_name"]))

        base_list = [a["base_code"] for a in subset]
        allele_list = [a["allele_name"] for a in subset]
        label_list = [a["label"] for a in subset]

        genotype_base = ",".join(base_list)
        genotype_alleles = ",".join(allele_list)
        treatments_and_transgenes = "; ".join(label_list)

        fluor_items: List[str] = []
        org_items: List[str] = []
        for base in base_list:
            m = markers.get(base, {})
            if m.get("fusion_pretty"):
                fluor_items.extend(
                    [s.strip() for s in str(m["fusion_pretty"]).split(",") if s.strip()]
                )
            if m.get("organelle_fluor"):
                org_items.extend(
                    [s.strip() for s in str(m["organelle_fluor"]).split(",") if s.strip()]
                )

        all_fluor = ", ".join(sorted(set(fluor_items)))
        all_org = ", ".join(sorted(set(org_items)))

        rows.append(
            {
                "label": None,  # fill with thing1, thing2,... below
                "treatment_code": None,
                "genotype_basecode_code": genotype_base,
                "genotype_transgene_allele_code": genotype_alleles,
                "treatments_and_transgenes": treatments_and_transgenes,
                "all_fluor_tag_rollup": all_fluor,
                "all_organelle_fluor_rollup": all_org,
                "expected_fraction": None,
                "expected_percent_label": "",
                "is_enabled": True,
                "notes": None,
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(
        ["genotype_basecode_code", "genotype_transgene_allele_code"],
        ignore_index=True,
    )
    df["label"] = [f"thing{i+1}" for i in range(len(df))]
    return df


# ---------- Step 3+4: upsert cross & clutch, write expected rows ----------
def upsert_cross_and_clutch_for_tank_pair(
    tp_id: str,
    run_date: date,
    expected_rows: pd.DataFrame,
) -> Tuple[str, str, str, str]:
    cross_date = run_date
    clutch_date = run_date + timedelta(days=1)
    d_cross = str(cross_date)
    d_clutch = str(clutch_date)

    with eng().begin() as cx:
        cross_sql = text(
            """
            WITH new_id AS (
              SELECT gen_random_uuid() AS id
            ),
            ins AS (
              INSERT INTO public.crosses (
                id,
                tank_pair_id,
                female_fish_id,
                male_fish_id,
                created_at,
                cross_run_code
              )
              SELECT
                new_id.id                         AS id,
                :tp_id                            AS tank_pair_id,
                mf.id                             AS female_fish_id,
                ff.id                             AS male_fish_id,
                CAST(:d_cross AS date)            AS created_at,
                'CR-' || left(new_id.id::text, 8) AS cross_run_code
              FROM new_id
              JOIN public.tank_pairs tp
                ON tp.id = :tp_id
              JOIN public.tanks mt
                ON mt.id = tp.mother_tank_id
              JOIN public.fish_instances_v10 mf
                ON mf.id = mt.fish_instance_id
              JOIN public.tanks ft
                ON ft.id = tp.father_tank_id
              JOIN public.fish_instances_v10 ff
                ON ff.id = ft.fish_instance_id
              WHERE NOT EXISTS (
                SELECT 1
                FROM public.crosses c
                WHERE c.tank_pair_id = :tp_id
                  AND DATE(c.created_at) = CAST(:d_cross AS date)
              )
              RETURNING id, cross_run_code
            ),
            sel AS (
              SELECT id, cross_run_code
              FROM ins
              UNION ALL
              SELECT id, cross_run_code
              FROM public.crosses c
              WHERE c.tank_pair_id = :tp_id
                AND DATE(c.created_at) = CAST(:d_cross AS date)
                AND NOT EXISTS (SELECT 1 FROM ins)
            )
            SELECT id, cross_id, cross_run_code FROM (
              SELECT id, id AS cross_id, cross_run_code FROM ins
              UNION ALL
              SELECT id, id AS cross_id, cross_run_code FROM public.crosses c
              WHERE c.tank_pair_id = :tp_id
                AND DATE(c.created_at) = CAST(:d_cross AS date)
                AND NOT EXISTS (SELECT 1 FROM ins)
            ) s
            LIMIT 1;
            """
        )
        cross_row = cx.execute(cross_sql, {"tp_id": tp_id, "d_cross": d_cross}).fetchone()
        if not cross_row:
            raise RuntimeError("Failed to insert or locate cross for tank pair.")
        cross_id, cross_id_, cross_run_code = cross_row  # cross_id_ == id

        clutch_code = f"CL-{str(cross_id)[:8]}"

        clutch_sql = text(
            """
            WITH new_id AS (
              SELECT gen_random_uuid() AS id
            ),
            ins AS (
              INSERT INTO public.clutches (
                id,
                clutch_code,
                cross_id,
                clutch_date
              )
              SELECT
                new_id.id              AS id,
                :clutch_code           AS clutch_code,
                :cross_id              AS cross_id,
                CAST(:d_clutch AS date) AS clutch_date
              FROM new_id
              WHERE NOT EXISTS (
                SELECT 1
                FROM public.clutches c
                WHERE c.cross_id = :cross_id
                  AND c.clutch_date = CAST(:d_clutch AS date)
              )
              RETURNING id, clutch_code
            ),
            sel AS (
              SELECT id, clutch_code
              FROM ins
              UNION ALL
              SELECT id, clutch_code
              FROM public.clutches c
              WHERE c.cross_id = :cross_id
                AND c.clutch_date = CAST(:d_clutch AS date)
                AND NOT EXISTS (SELECT 1 FROM ins)
            )
            SELECT id, clutch_code FROM sel LIMIT 1;
            """
        )
        clutch_row = cx.execute(
            clutch_sql,
            {"cross_id": cross_id, "d_clutch": d_clutch, "clutch_code": clutch_code},
        ).fetchone()
        if not clutch_row:
            raise RuntimeError("Failed to insert or locate clutch for cross.")
        clutch_id, clutch_code_out = clutch_row

        if not expected_rows.empty:
            sql_ins = text(
                """
                INSERT INTO public.clutch_expected_genotypes_v11 (
                  id,
                  clutch_id,
                  label,
                  treatment_code,
                  genotype_basecode_code,
                  genotype_transgene_allele_code,
                  treatments_and_transgenes,
                  all_fluor_tag_rollup,
                  all_organelle_fluor_rollup,
                  zygocity_vector,
                  expected_fraction,
                  expected_percent_label,
                  is_enabled,
                  notes
                )
                VALUES (
                  gen_random_uuid(),
                  :clutch_id,
                  :label,
                  :treatment_code,
                  :genotype_basecode_code,
                  :genotype_transgene_allele_code,
                  :treatments_and_transgenes,
                  :all_fluor_tag_rollup,
                  :all_organelle_fluor_rollup,
                  :zygocity_vector,
                  :expected_fraction,
                  :expected_percent_label,
                  :is_enabled,
                  :notes
                );
                """
            )
            for _, r in expected_rows.iterrows():
                eng().execute(
                    sql_ins,
                    {
                        "clutch_id": clutch_id,
                        "label": r.get("label"),
                        "treatment_code": r.get("treatment_code"),
                        "genotype_basecode_code": r.get("genotype_basecode_code"),
                        "genotype_transgene_allele_code": r.get(
                            "genotype_transgene_allele_code"
                        ),
                        "treatments_and_transgenes": r.get("treatments_and_transgenes"),
                        "all_fluor_tag_rollup": r.get("all_fluor_tag_rollup"),
                        "all_organelle_fluor_rollup": r.get(
                            "all_organelle_fluor_rollup"
                        ),
                        "zygocity_vector": None,
                        "expected_fraction": r.get("expected_fraction"),
                        "expected_percent_label": r.get("expected_percent_label"),
                        "is_enabled": bool(r.get("is_enabled", True)),
                        "notes": r.get("notes"),
                    },
                )

    return str(cross_id), str(cross_run_code), str(clutch_id), str(clutch_code_out)


# ---------- UI wiring ----------
with st.form("tank_pair_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        q_raw = st.text_input(
            "Filter tank pairs (tank_pair_code / tank_code / fish_code)",
            "",
        )
    with c2:
        limit_pairs = int(
            st.number_input(
                "Tank pair row limit",
                min_value=10,
                max_value=2000,
                value=200,
                step=50,
            )
        )
    _ = st.form_submit_button("Apply")

pairs = list_tank_pairs(q_raw or "", limit_pairs)

if pairs.empty:
    st.info("No tank pairs match the current filters.")
    st.stop()

st.subheader("Step 1 — Select a tank pair")
tp_view = pairs.copy()
tp_view.insert(0, "✓", False)

tp_grid = st.data_editor(
    tp_view,
    key="tank_pairs_picker_for_cross",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_order=[
        "✓",
        "tank_pair_id",
        "tank_pair_code",
        "mom_fish_code",
        "mom_tank_code",
        "mom_genotype",
        "dad_fish_code",
        "dad_tank_code",
        "dad_genotype",
        "created_at",
    ],
)

tp_sel = tp_grid.loc[tp_grid["✓"] == True] if "✓" in tp_grid.columns else pd.DataFrame()
if tp_sel.empty:
    st.info("Select a tank pair above to schedule a cross.")
    st.stop()

tp_row = tp_sel.iloc[0]
tp_id = tp_row["tank_pair_id"]
tp_code = tp_row["tank_pair_code"]

st.success(f"Selected tank pair: {tp_code}")

# Step 1a: parent pivot
st.subheader("Step 1a — Parents (tanks, fish, v11 genotype standard 6)", anchor=False)
parents_df = get_parent_detail(tp_id)

mother = parents_df[parents_df["role"] == "mother"].iloc[0] if (parents_df["role"] == "mother").any() else None
father = parents_df[parents_df["role"] == "father"].iloc[0] if (parents_df["role"] == "father").any() else None

def _pv(row: Optional[pd.Series], col: str) -> str:
    if row is None:
        return ""
    return row.get(col, "")

pivot_rows = [
    ("Fish code",              _pv(mother, "fish_code"),                  _pv(father, "fish_code")),
    ("Tank code",              _pv(mother, "tank_code"),                  _pv(father, "tank_code")),
    ("Genotype basecode code", _pv(mother, "genotype_basecode_code"),     _pv(father, "genotype_basecode_code")),
    ("Genotype transgene/allele code", _pv(mother, "genotype_transgene_allele_code"), _pv(father, "genotype_transgene_allele_code")),
    ("Treatments & transgenes", _pv(mother, "treatments_and_transgenes"), _pv(father, "treatments_and_transgenes")),
    ("Fluor::tag rollup",      _pv(mother, "all_fluor_tag_rollup"),       _pv(father, "all_fluor_tag_rollup")),
    ("Organelle-fluor rollup", _pv(mother, "all_organelle_fluor_rollup"), _pv(father, "all_organelle_fluor_rollup")),
]

pivot_df = pd.DataFrame(pivot_rows, columns=["Field", "Mother", "Father"])
st.dataframe(pivot_df, use_container_width=True)

# Step 2: expected offspring genotypes (allele subsets, labeled)
st.subheader("Step 2 — Expected offspring genotypes (allele subsets)", anchor=False)
df_expected = compute_expected_genotypes_for_tank_pair(tp_id)

if df_expected.empty:
    st.info(
        "No allele-level genotype information was available for this tank pair, "
        "or there were too many alleles to enumerate safely. You can still save "
        "the cross and clutch; expected genotypes will be added later."
    )
    expected_selected = pd.DataFrame()
else:
    expected_view = df_expected.copy()
    expected_view.insert(0, "✓", True)
    expected_view["is_enabled"] = expected_view["✓"]

    expected_grid = st.data_editor(
        expected_view,
        key="expected_genotypes_picker",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_order=[
            "✓",
            "label",
            "genotype_basecode_code",
            "genotype_transgene_allele_code",
            "treatments_and_transgenes",
            "all_fluor_tag_rollup",
            "all_organelle_fluor_rollup",
        ],
    )

    expected_selected = (
        expected_grid[expected_grid["✓"] == True].copy()
        if "✓" in expected_grid.columns
        else pd.DataFrame()
    )
    if not expected_selected.empty:
        expected_selected["is_enabled"] = True

# Step 3: choose date
st.subheader("Step 3 — Choose cross date")
run_date = st.date_input("Cross date", value=date.today())

# Step 4: save cross + clutch
st.subheader("Step 4 — Save cross + clutch")

if st.button("💾 Schedule cross + clutch", type="primary", use_container_width=True):
    try:
        cross_id, cross_run_code, clutch_id, clutch_code = upsert_cross_and_clutch_for_tank_pair(
            tp_id,
            run_date,
            expected_selected,
        )
        label_str = f"{tp_code} @ {run_date.isoformat()}"
        st.success(
            f"Cross scheduled: {cross_code} ({label_str}) (id={cross_id}); "
            f"Clutch created: {clutch_code} (id={clutch_id}); "
            f"Expected genotype rows saved: {len(expected_selected)}"
        )
    except Exception as e:
        st.error(f"Schedule failed: {type(e).__name__}: {e}")