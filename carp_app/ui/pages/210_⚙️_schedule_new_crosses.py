from __future__ import annotations

import sys
import os
import pathlib
import hashlib
from datetime import date, timedelta
from typing import Optional, Tuple, List, Dict, Any

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

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

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — ⚙️ Schedule new cross",
    page_icon="⚙️",
    layout="wide",
)
st.title("⚙️ Schedule new cross")


def eng() -> Engine:
    return _engine()


def _norm(s: str | None) -> Optional[str]:
    return s.strip() if isinstance(s, str) else None


def _tank_pair_parent_cols() -> Tuple[str, str]:
    sql = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'tank_pairs'
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx)
    cols = df["column_name"].tolist()
    for a, b in (("mother_tank_id", "father_tank_id"),
                 ("tank_id_mother", "tank_id_father")):
        if a in cols and b in cols:
            return a, b
    raise RuntimeError(
        f"tank_pairs missing expected parent columns; found: {cols}"
    )


@st.cache_data(show_spinner=False)
def list_tank_pairs(q: str, limit: int) -> pd.DataFrame:
    qn = _norm(q)
    like = f"%{qn}%" if qn else None
    mom_col, dad_col = _tank_pair_parent_cols()

    sql = text(
        f"""
        WITH pairs AS (
          SELECT
            tp.id::uuid        AS tank_pair_id,
            tp.tank_pair_code  AS tank_pair_code,
            tp.created_at      AS created_at,
            mt.id              AS mom_tank_id,
            mt.tank_code       AS mom_tank_code,
            mf.fish_code       AS mom_fish_code,
            mfi.genotype_pretty AS mom_genotype,
            ft.id              AS dad_tank_id,
            ft.tank_code       AS dad_tank_code,
            ff.fish_code       AS dad_fish_code,
            ffi.genotype_pretty AS dad_genotype
          FROM public.tank_pairs tp
          LEFT JOIN public.tanks mt
                 ON mt.id = tp.{mom_col}
          LEFT JOIN public.fish_instances_v10 mf
                 ON mf.id = mt.fish_instance_id
          LEFT JOIN public.v11_fish_instance_star mfi
                 ON mfi.fish_instance_id = mf.id
          LEFT JOIN public.tanks ft
                 ON ft.id = tp.{dad_col}
          LEFT JOIN public.fish_instances_v10 ff
                 ON ff.id = ft.fish_instance_id
          LEFT JOIN public.v11_fish_instance_star ffi
                 ON ffi.fish_instance_id = ff.id
        )
        SELECT *
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
        LIMIT :lim;
        """
    )
    params = {"q": qn if qn else None, "ql": like, "lim": int(limit)}
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df


def get_parent_detail(tp_id: str) -> pd.DataFrame:
    mom_col, dad_col = _tank_pair_parent_cols()
    sql = text(
        f"""
        WITH tp AS (
          SELECT id, {mom_col} AS mom_tank_id, {dad_col} AS dad_tank_id
          FROM public.tank_pairs
          WHERE id = :tp_id
        ),
        mom AS (
          SELECT
            'mother'                          AS role,
            mt.tank_code                      AS tank_code,
            mf.id                             AS fish_id,
            mf.fish_code                      AS fish_code,
            fis.genotype_basecodes            AS genotype_basecode_code,
            NULL::text                        AS genotype_transgene_allele_code,
            NULL::text                        AS treatments_and_transgenes,
            COALESCE(mr.fluor_tag_rollup, '')       AS all_fluor_tag_rollup,
            COALESCE(mr.organelle_fluor_rollup, '') AS all_organelle_fluor_rollup
          FROM tp
          JOIN public.tanks mt
            ON mt.id = tp.mom_tank_id
          JOIN public.fish_instances_v10 mf
            ON mf.id = mt.fish_instance_id
          JOIN public.v11_fish_instance_star fis
            ON fis.fish_instance_id = mf.id
          LEFT JOIN public.v11_fish_marker_rollups mr
            ON mr.fish_instance_id = mf.id
        ),
        dad AS (
          SELECT
            'father'                          AS role,
            ft.tank_code                      AS tank_code,
            ff.id                             AS fish_id,
            ff.fish_code                      AS fish_code,
            fis.genotype_basecodes            AS genotype_basecode_code,
            NULL::text                        AS genotype_transgene_allele_code,
            NULL::text                        AS treatments_and_transgenes,
            COALESCE(mr.fluor_tag_rollup, '')       AS all_fluor_tag_rollup,
            COALESCE(mr.organelle_fluor_rollup, '') AS all_organelle_fluor_rollup
          FROM tp
          JOIN public.tanks ft
            ON ft.id = tp.dad_tank_id
          JOIN public.fish_instances_v10 ff
            ON ff.id = ft.fish_instance_id
          JOIN public.v11_fish_instance_star fis
            ON fis.fish_instance_id = ff.id
          LEFT JOIN public.v11_fish_marker_rollups mr
            ON mr.fish_instance_id = ff.id
        ),
        parents AS (
          SELECT * FROM mom
          UNION ALL
          SELECT * FROM dad
        )
        SELECT
          p.role,
          p.tank_code,
          p.fish_id,
          p.fish_code,
          p.genotype_basecode_code,
          p.genotype_transgene_allele_code,
          p.treatments_and_transgenes,
          p.all_fluor_tag_rollup,
          p.all_organelle_fluor_rollup,
          fa.allele_canonical_rollup,
          fa.allele_label_rollup
        FROM parents p
        LEFT JOIN public.v11_fish_allele_rollups fa
          ON fa.fish_instance_id = p.fish_id
        ORDER BY p.role;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"tp_id": tp_id})
    return df.fillna("")


def compute_expected_genotypes_for_tank_pair(tp_id: str) -> pd.DataFrame:
    parents = get_parent_detail(tp_id)
    if parents.empty:
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

    # helper: parse "BASE:guN; BASE2:guM" into {base: [token,...]}
    def _parse_alleles(s: Any) -> Dict[str, List[str]]:
        txt = (str(s) if s is not None else "").strip()
        out: Dict[str, List[str]] = {}
        if not txt:
            return out
        for tok in txt.split(";"):
            t = tok.strip()
            if not t:
                continue
            if ":" not in t:
                continue
            base, allele = t.split(":", 1)
            base = base.strip()
            allele = allele.strip()
            if not base or not allele:
                continue
            out.setdefault(base, []).append(f"{base}:{allele}")
        return out

    # helper: parse "BASE || label; BASE2 || label2" into {base: [full_token,...]}
    def _parse_treatments(s: Any) -> Dict[str, List[str]]:
        txt = (str(s) if s is not None else "").strip()
        out: Dict[str, List[str]] = {}
        if not txt:
            return out
        for tok in txt.split(";"):
            t = tok.strip()
            if not t:
                continue
            if "||" in t:
                base_part, rest = t.split("||", 1)
                base = base_part.strip()
            else:
                base = ""
            if base:
                out.setdefault(base, []).append(t)
        return out

    # identify mother/father rows
    mother = parents[parents["role"] == "mother"].iloc[0] if (parents["role"] == "mother").any() else None
    father = parents[parents["role"] == "father"].iloc[0] if (parents["role"] == "father").any() else None

    # allele maps per parent from allele_canonical_rollup
    alleles_m: Dict[str, List[str]] = _parse_alleles(mother["allele_canonical_rollup"]) if mother is not None else {}
    alleles_f: Dict[str, List[str]] = _parse_alleles(father["allele_canonical_rollup"]) if father is not None else {}

    # basecodes present in either parent
    all_bases = sorted(set(alleles_m.keys()) | set(alleles_f.keys()))

    # treatment maps per parent from treatments_and_transgenes
    tx_m = _parse_treatments(mother["treatments_and_transgenes"]) if mother is not None else {}
    tx_f = _parse_treatments(father["treatments_and_transgenes"]) if father is not None else {}

    # fluor / organelle rollups: union of parents (same for all classes for now)
    fluor_union_parts: List[str] = []
    for src in [
        mother["all_fluor_tag_rollup"] if mother is not None else "",
        father["all_fluor_tag_rollup"] if father is not None else "",
    ]:
        txt = (str(src) if src is not None else "").strip()
        if not txt:
            continue
        for tok in txt.split(","):
            t = tok.strip()
            if t and t not in fluor_union_parts:
                fluor_union_parts.append(t)
    fluor_union = ", ".join(fluor_union_parts)

    org_union_parts: List[str] = []
    for src in [
        mother["all_organelle_fluor_rollup"] if mother is not None else "",
        father["all_organelle_fluor_rollup"] if father is not None else "",
    ]:
        txt = (str(src) if src is not None else "").strip()
        if not txt:
            continue
        for tok in txt.split(","):
            t = tok.strip()
            if t and t not in org_union_parts:
                org_union_parts.append(t)
    org_union = ", ".join(org_union_parts)

    # build all genotype combinations across bases
    combos: List[Dict[str, List[str]]] = [dict()]  # start with empty combo

    for base in all_bases:
        m_opts = alleles_m.get(base, [])
        f_opts = alleles_f.get(base, [])
        options: List[List[str]] = []

        # always allow "no allele" (empty set)
        options.append([])

        # mother-only
        if m_opts:
            options.append(m_opts)

        # father-only (if different from mother)
        if f_opts and f_opts != m_opts:
            options.append(f_opts)

        # both parents (if both present and at least one differs)
        if m_opts and f_opts:
            if m_opts != f_opts:
                merged = sorted(set(m_opts + f_opts))
                options.append(merged)

        new_combos: List[Dict[str, List[str]]] = []
        for combo in combos:
            for opt in options:
                new_c = dict(combo)
                if opt:
                    new_c[base] = opt
                else:
                    if base in new_c:
                        new_c.pop(base)
                new_combos.append(new_c)
        # dedupe combos by a stable key
        seen_keys = set()
        deduped: List[Dict[str, List[str]]] = []
        for c in new_combos:
            key_parts = []
            for b in sorted(c.keys()):
                key_parts.append(b + ":" + "|".join(sorted(c[b])))
            key = ";".join(key_parts)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(c)
        combos = deduped

    rows: List[Dict[str, Any]] = []
    for idx, combo in enumerate(combos):
        bases = sorted(combo.keys())
        alleles = []
        for b in bases:
            alleles.extend(sorted(combo[b]))
        genotype_base = ",".join(bases)
        genotype_alleles = "; ".join(alleles)

        # treatments filtered by bases in this genotype
        tx_tokens: List[str] = []
        for b in bases:
            for t in tx_m.get(b, []):
                if t not in tx_tokens:
                    tx_tokens.append(t)
            for t in tx_f.get(b, []):
                if t not in tx_tokens:
                    tx_tokens.append(t)
        treatments = "; ".join(tx_tokens)

        rows.append(
            {
                "label": f"genotype{idx}",
                "treatment_code": None,
                "genotype_basecode_code": genotype_base,
                "genotype_transgene_allele_code": genotype_alleles,
                "treatments_and_transgenes": treatments,
                "all_fluor_tag_rollup": fluor_union,
                "all_organelle_fluor_rollup": org_union,
                "expected_fraction": None,
                "expected_percent_label": "",
                "is_enabled": True,
                "notes": None,
            }
        )

    return pd.DataFrame(rows)


def upsert_cross_and_clutch_for_tank_pair(
    tp_id: str,
    run_date: date,
    expected_rows: pd.DataFrame,
) -> Tuple[str, str, str, str]:
    mom_col, dad_col = _tank_pair_parent_cols()
    cross_date = run_date
    clutch_date = run_date + timedelta(days=1)
    d_cross = str(cross_date)
    d_clutch = str(clutch_date)

    with eng().begin() as cx:
        cross_sql = text(
            f"""
            WITH tp AS (
              SELECT id, {mom_col} AS mom_tank_id, {dad_col} AS dad_tank_id
              FROM public.tank_pairs
              WHERE id = :tp_id
            ),
            new_id AS (
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
                tp.id                              AS tank_pair_id,
                mf.id                              AS female_fish_id,
                ff.id                              AS male_fish_id,
                CAST(:d_cross AS date)             AS created_at,
                'CR-' || left(new_id.id::text, 8)  AS cross_run_code
              FROM new_id
              JOIN tp
                ON tp.id = :tp_id
              JOIN public.tanks mt
                ON mt.id = tp.mom_tank_id
              JOIN public.fish_instances_v10 mf
                ON mf.id = mt.fish_instance_id
              JOIN public.tanks ft
                ON ft.id = tp.dad_tank_id
              JOIN public.fish_instances_v10 ff
                ON ff.id = ft.fish_instance_id
              WHERE NOT EXISTS (
                SELECT 1
                FROM public.crosses c
                WHERE c.tank_pair_id = tp.id
                  AND DATE(c.created_at) = CAST(:d_cross AS date)
              )
              RETURNING id, cross_run_code
            )
            SELECT id, cross_run_code
            FROM ins
            UNION ALL
            SELECT id, cross_run_code
            FROM public.crosses c
            WHERE c.tank_pair_id = :tp_id
              AND DATE(c.created_at) = CAST(:d_cross AS date)
              AND NOT EXISTS (SELECT 1 FROM ins)
            LIMIT 1;
            """
        )
        cross_row = cx.execute(
            cross_sql, {"tp_id": tp_id, "d_cross": d_cross}
        ).fetchone()
        if not cross_row:
            raise RuntimeError("Failed to insert or locate cross for tank pair.")
        cross_id, cross_run_code = cross_row

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
                new_id.id               AS id,
                :clutch_code            AS clutch_code,
                :cross_id               AS cross_id,
                CAST(:d_clutch AS date) AS clutch_date
              FROM new_id
              WHERE NOT EXISTS (
                SELECT 1
                FROM public.clutches c
                WHERE c.cross_id = :cross_id
                  AND c.clutch_date = CAST(:d_clutch AS date)
              )
              RETURNING id, clutch_code
            )
            SELECT id, clutch_code
            FROM ins
            UNION ALL
            SELECT id, clutch_code
            FROM public.clutches c
            WHERE c.cross_id = :cross_id
              AND c.clutch_date = CAST(:d_clutch AS date)
              AND NOT EXISTS (SELECT 1 FROM ins)
            LIMIT 1;
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
        with eng().begin() as cx:
            for _, r in expected_rows.iterrows():
                basecodes = (r.get("genotype_basecode_code") or "").strip()
                alleles = (r.get("genotype_transgene_allele_code") or "").strip()
                if not basecodes:
                    continue

                key = f"{basecodes}|{alleles}"
                gcode = "G-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:10].upper()
                pretty = alleles or basecodes

                res = cx.execute(
                    text(
                        """
                        INSERT INTO public.genotypes_v11 (
                          id,
                          genotype_code,
                          genotype_pretty,
                          genotype_basecodes,
                          created_at
                        )
                        VALUES (
                          gen_random_uuid(),
                          :gcode,
                          :pretty,
                          :basecodes,
                          now()
                        )
                        ON CONFLICT (genotype_code) DO UPDATE
                          SET genotype_pretty    = EXCLUDED.genotype_pretty,
                              genotype_basecodes = EXCLUDED.genotype_basecodes
                        RETURNING id;
                        """
                    ),
                    {"gcode": gcode, "pretty": pretty, "basecodes": basecodes},
                )
                gid = res.scalar()
                if gid is None:
                    gid = cx.execute(
                        text(
                            "SELECT id FROM public.genotypes_v11 WHERE genotype_code = :gcode"
                        ),
                        {"gcode": gcode},
                    ).scalar()
                    if gid is None:
                        continue

                cx.execute(
                    text(
                        """
                        INSERT INTO public.clutch_genotypes_v11 (
                          id,
                          clutch_id,
                          genotype_v11_id,
                          expected_fraction,
                          expected_percent_label,
                          notes
                        )
                        VALUES (
                          gen_random_uuid(),
                          :clutch_id,
                          :gid,
                          :expected_fraction,
                          :expected_percent_label,
                          :notes
                        )
                        ON CONFLICT DO NOTHING;
                        """
                    ),
                    {
                        "clutch_id": clutch_id,
                        "gid": gid,
                        "expected_fraction": r.get("expected_fraction"),
                        "expected_percent_label": r.get("expected_percent_label"),
                        "notes": r.get("notes"),
                    },
                )

    return str(cross_id), str(cross_run_code), str(clutch_id), str(clutch_code_out)


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
    _ = st.form_submit_button("Apply", key="tank_pair_filters_apply")

pairs = list_tank_pairs(q_raw or "", limit_pairs)

if pairs.empty:
    st.info("No tank pairs match the current filters.")
    st.stop()

st.subheader("Step 1 — Select a tank pair", anchor=False)
tp_view = pairs.copy()
tp_view.insert(0, "✓", False)

tp_grid = st.data_editor(
    tp_view[
        [
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
        ]
    ],
    key="tank_pairs_picker_for_cross",
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
)

tp_sel = tp_grid.loc[tp_grid["✓"] == True] if "✓" in tp_grid.columns else pd.DataFrame()
if tp_sel.empty:
    st.info("Select a tank pair above to schedule a cross.")
    st.stop()

tp_row = tp_sel.iloc[0]
tp_id = tp_row["tank_pair_id"]
tp_code = tp_row["tank_pair_code"]

st.success(f"Selected tank pair: {tp_code}")

st.subheader("Step 1a — Parents (tanks, fish, v11 genotype + alleles)", anchor=False)
parents_df = get_parent_detail(tp_id)

mother = parents_df[parents_df["role"] == "mother"].iloc[0] if (
    not parents_df.empty and "mother" in parents_df["role"].values
) else None
father = parents_df[parents_df["role"] == "father"].iloc[0] if (
    not parents_df.empty and "father" in parents_df["role"].values
) else None

def _pv(row: Optional[pd.Series], col: str) -> str:
    if row is None:
        return ""
    return str(row.get(col, "") or "")

pivot_rows = [
    ("Fish code", _pv(mother, "fish_code"), _pv(father, "fish_code")),
    ("Tank code", _pv(mother, "tank_code"), _pv(father, "tank_code")),
    ("Genotype basecode code", _pv(mother, "genotype_basecode_code"), _pv(father, "genotype_basecode_code")),
    ("Genotype transgene/allele code", _pv(mother, "genotype_transgene_allele_code"), _pv(father, "genotype_transgene_allele_code")),
    ("Treatments & transgenes", _pv(mother, "treatments_and_transgenes"), _pv(father, "treatments_and_transgenes")),
    ("Fluor::tag rollup", _pv(mother, "all_fluor_tag_rollup"), _pv(father, "all_fluor_tag_rollup")),
    ("Organelle-fluor rollup", _pv(mother, "all_organelle_fluor_rollup"), _pv(father, "all_organelle_fluor_rollup")),
    ("Allele canonical rollup", _pv(mother, "allele_canonical_rollup"), _pv(father, "allele_canonical_rollup")),
    ("Allele label rollup", _pv(mother, "allele_label_rollup"), _pv(father, "allele_label_rollup")),
]

pivot_df = pd.DataFrame(pivot_rows, columns=["Field", "Mother", "Father"])
st.dataframe(pivot_df, use_container_width=True, hide_index=True)

st.subheader("Step 2 — Expected offspring genotypes (union summary)", anchor=False)
df_expected = compute_expected_genotypes_for_tank_pair(tp_id)

if df_expected.empty:
    st.info(
        "Could not derive any expected genotype information for this tank pair. "
        "You can still save the cross and clutch; expected genotypes can be added later."
    )
    expected_selected = pd.DataFrame()
else:
    expected_view = df_expected.copy()
    expected_view.insert(0, "✓", True)
    expected_view["is_enabled"] = expected_view["✓"]

    expected_grid = st.data_editor(
        expected_view[
            [
                "✓",
                "label",
                "genotype_basecode_code",
                "genotype_transgene_allele_code",
                "treatments_and_transgenes",
                "all_fluor_tag_rollup",
                "all_organelle_fluor_rollup",
            ]
        ],
        key="expected_genotypes_picker",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
    )

    expected_selected = (
        expected_grid[expected_grid["✓"] == True].copy()
        if "✓" in expected_grid.columns
        else pd.DataFrame()
    )
    if not expected_selected.empty:
        expected_selected["is_enabled"] = True

st.subheader("Step 3 — Choose cross date", anchor=False)
run_date = st.date_input("Cross date", value=date.today())

st.subheader("Step 4 — Save cross + clutch", anchor=False)

if st.button("💾 Schedule cross + clutch", type="primary", use_container_width=True):
    try:
        cross_id, cross_run_code, clutch_id, clutch_code = (
            upsert_cross_and_clutch_for_tank_pair(
                tp_id,
                run_date,
                expected_selected,
            )
        )
        label_str = f"{tp_code} @ {run_date.isoformat()}"
        st.success(
            f"Cross scheduled: {cross_run_code} ({label_str}) (id={cross_id}); "
            f"Clutch created: {clutch_code} (id={clutch_id}); "
            f"Expected genotype rows saved: {len(expected_selected)}"
        )
    except Exception as e:
        st.error(f"Schedule failed: {type(e).__name__}: {e}")