# carp_app/ui/pages/210_⚙️_schedule_new_cross.py
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


def _marker_rollup(treat_label: str, geno: str, bg: str) -> str:
    t = (treat_label or "").strip()
    g = (geno or "").strip()
    b = (bg or "").strip()
    if t and g:
        return f"{t} > {g}"
    if t:
        return t
    if g:
        return g
    return b


def _cols(schema: str, name: str) -> List[str]:
    sql = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :s AND table_name = :t
        ORDER BY ordinal_position;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"s": schema, "t": name})
    return df["column_name"].astype(str).tolist()


def _tank_pair_parent_cols() -> Tuple[str, str]:
    sql = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'tank_pairs'
        ORDER BY ordinal_position;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx)
    cols = df["column_name"].tolist()
    for a, b in (("mother_tank_id", "father_tank_id"), ("tank_id_mother", "tank_id_father")):
        if a in cols and b in cols:
            return a, b
    raise RuntimeError(f"tank_pairs missing expected parent columns; found: {cols}")


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

            COALESCE(mfis.genetic_background,'') AS mom_background,
            COALESCE(mfis.genotype_tg_style,'') AS mom_geno_tg,
            COALESCE(mfis.treatment_label_tg_style,'') AS mom_treat_tg,
            COALESCE(mfis.genotype_fluortag_style,'') AS mom_geno_fluortag,
            COALESCE(mfis.treatment_label_fluortag_style,'') AS mom_treat_fluortag,
            COALESCE(mfis.genotype_fluororganelle_style,'') AS mom_geno_fluororganelle,
            COALESCE(mfis.treatment_label_fluororganelle_style,'') AS mom_treat_fluororganelle,

            ft.id              AS dad_tank_id,
            ft.tank_code       AS dad_tank_code,
            ff.fish_code       AS dad_fish_code,

            COALESCE(dfis.genetic_background,'') AS dad_background,
            COALESCE(dfis.genotype_tg_style,'') AS dad_geno_tg,
            COALESCE(dfis.treatment_label_tg_style,'') AS dad_treat_tg,
            COALESCE(dfis.genotype_fluortag_style,'') AS dad_geno_fluortag,
            COALESCE(dfis.treatment_label_fluortag_style,'') AS dad_treat_fluortag,
            COALESCE(dfis.genotype_fluororganelle_style,'') AS dad_geno_fluororganelle,
            COALESCE(dfis.treatment_label_fluororganelle_style,'') AS dad_treat_fluororganelle

          FROM public.tank_pairs tp
          LEFT JOIN public.tanks mt
                 ON mt.id = tp.{mom_col}
          LEFT JOIN public.fish_instances_v10 mf
                 ON mf.id = mt.fish_instance_id
          LEFT JOIN public.v11_fish_instance_star_labels mfis
                 ON mfis.fish_instance_id = mf.id

          LEFT JOIN public.tanks ft
                 ON ft.id = tp.{dad_col}
          LEFT JOIN public.fish_instances_v10 ff
                 ON ff.id = ft.fish_instance_id
          LEFT JOIN public.v11_fish_instance_star_labels dfis
                 ON dfis.fish_instance_id = ff.id
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
    df = df.fillna("")

    df["mom_marker_tg"] = df.apply(lambda r: _marker_rollup(r["mom_treat_tg"], r["mom_geno_tg"], r["mom_background"]), axis=1)
    df["mom_marker_fluortag"] = df.apply(lambda r: _marker_rollup(r["mom_treat_fluortag"], r["mom_geno_fluortag"], r["mom_background"]), axis=1)
    df["mom_marker_fluororganelle"] = df.apply(lambda r: _marker_rollup(r["mom_treat_fluororganelle"], r["mom_geno_fluororganelle"], r["mom_background"]), axis=1)

    df["dad_marker_tg"] = df.apply(lambda r: _marker_rollup(r["dad_treat_tg"], r["dad_geno_tg"], r["dad_background"]), axis=1)
    df["dad_marker_fluortag"] = df.apply(lambda r: _marker_rollup(r["dad_treat_fluortag"], r["dad_geno_fluortag"], r["dad_background"]), axis=1)
    df["dad_marker_fluororganelle"] = df.apply(lambda r: _marker_rollup(r["dad_treat_fluororganelle"], r["dad_geno_fluororganelle"], r["dad_background"]), axis=1)

    df["cross_label_tg"] = df.apply(lambda r: f"{r['mom_marker_tg']} × {r['dad_marker_tg']}".strip(), axis=1)
    df["cross_label_fluortag"] = df.apply(lambda r: f"{r['mom_marker_fluortag']} × {r['dad_marker_fluortag']}".strip(), axis=1)
    df["cross_label_fluororganelle"] = df.apply(lambda r: f"{r['mom_marker_fluororganelle']} × {r['dad_marker_fluororganelle']}".strip(), axis=1)

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

            COALESCE(lbl.genetic_background,'') AS genetic_background,

            COALESCE(lbl.genotype_basecodes,'') AS genotype_basecode_code,

            COALESCE(lbl.genotype_tg_style,'')             AS genotype_tg_style,
            COALESCE(lbl.genotype_fluortag_style,'')       AS genotype_fluortag_style,
            COALESCE(lbl.genotype_fluororganelle_style,'') AS genotype_fluororganelle_style,

            COALESCE(lbl.treatment_codes,'')               AS treatment_codes,
            COALESCE(lbl.treatment_label_tg_style,'')      AS treatment_label_tg_style,
            COALESCE(lbl.treatment_label_fluortag_style,'') AS treatment_label_fluortag_style,
            COALESCE(lbl.treatment_label_fluororganelle_style,'') AS treatment_label_fluororganelle_style,

            COALESCE(fa.allele_canonical_rollup,'') AS allele_canonical_rollup,
            COALESCE(fa.allele_label_rollup,'')     AS allele_label_rollup

          FROM tp
          JOIN public.tanks mt
            ON mt.id = tp.mom_tank_id
          JOIN public.fish_instances_v10 mf
            ON mf.id = mt.fish_instance_id
          LEFT JOIN public.v11_fish_instance_star_labels lbl
            ON lbl.fish_instance_id = mf.id
          LEFT JOIN public.v11_fish_allele_rollups fa
            ON fa.fish_instance_id = mf.id
        ),

        dad AS (
          SELECT
            'father'                          AS role,
            ft.tank_code                      AS tank_code,
            ff.id                             AS fish_id,
            ff.fish_code                      AS fish_code,

            COALESCE(lbl.genetic_background,'') AS genetic_background,

            COALESCE(lbl.genotype_basecodes,'') AS genotype_basecode_code,

            COALESCE(lbl.genotype_tg_style,'')             AS genotype_tg_style,
            COALESCE(lbl.genotype_fluortag_style,'')       AS genotype_fluortag_style,
            COALESCE(lbl.genotype_fluororganelle_style,'') AS genotype_fluororganelle_style,

            COALESCE(lbl.treatment_codes,'')               AS treatment_codes,
            COALESCE(lbl.treatment_label_tg_style,'')      AS treatment_label_tg_style,
            COALESCE(lbl.treatment_label_fluortag_style,'') AS treatment_label_fluortag_style,
            COALESCE(lbl.treatment_label_fluororganelle_style,'') AS treatment_label_fluororganelle_style,

            COALESCE(fa.allele_canonical_rollup,'') AS allele_canonical_rollup,
            COALESCE(fa.allele_label_rollup,'')     AS allele_label_rollup

          FROM tp
          JOIN public.tanks ft
            ON ft.id = tp.dad_tank_id
          JOIN public.fish_instances_v10 ff
            ON ff.id = ft.fish_instance_id
          LEFT JOIN public.v11_fish_instance_star_labels lbl
            ON lbl.fish_instance_id = ff.id
          LEFT JOIN public.v11_fish_allele_rollups fa
            ON fa.fish_instance_id = ff.id
        )

        SELECT * FROM mom
        UNION ALL
        SELECT * FROM dad
        ORDER BY role;
        """
    )
    with eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"tp_id": tp_id})
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df.fillna("")


def compute_expected_genotypes_for_tank_pair(tp_id: str) -> pd.DataFrame:
    parents = get_parent_detail(tp_id)
    if parents.empty:
        return pd.DataFrame(
            columns=[
                "label",
                "expected_genotype_basecodes",
                "expected_genotype_alleles",
                "expected_fraction",
                "expected_percent_label",
                "is_enabled",
                "notes",
            ]
        )

    def _parse_alleles(s: Any) -> Dict[str, List[str]]:
        txt = (str(s) if s is not None else "").strip()
        out: Dict[str, List[str]] = {}
        if not txt:
            return out
        for tok in txt.split(";"):
            t = tok.strip()
            if not t or ":" not in t:
                continue
            base, allele = t.split(":", 1)
            base = base.strip()
            allele = allele.strip()
            if not base or not allele:
                continue
            out.setdefault(base, []).append(f"{base}:{allele}")
        return out

    mother = parents[parents["role"] == "mother"].iloc[0] if (parents["role"] == "mother").any() else None
    father = parents[parents["role"] == "father"].iloc[0] if (parents["role"] == "father").any() else None

    alleles_m: Dict[str, List[str]] = _parse_alleles(mother["allele_canonical_rollup"]) if mother is not None else {}
    alleles_f: Dict[str, List[str]] = _parse_alleles(father["allele_canonical_rollup"]) if father is not None else {}

    all_bases = sorted(set(alleles_m.keys()) | set(alleles_f.keys()))
    combos: List[Dict[str, List[str]]] = [dict()]

    for base in all_bases:
        m_opts = alleles_m.get(base, [])
        f_opts = alleles_f.get(base, [])
        options: List[List[str]] = [[]]
        if m_opts:
            options.append(m_opts)
        if f_opts and f_opts != m_opts:
            options.append(f_opts)
        if m_opts and f_opts and m_opts != f_opts:
            options.append(sorted(set(m_opts + f_opts)))

        new_combos: List[Dict[str, List[str]]] = []
        for combo in combos:
            for opt in options:
                new_c = dict(combo)
                if opt:
                    new_c[base] = opt
                else:
                    new_c.pop(base, None)
                new_combos.append(new_c)

        seen = set()
        deduped: List[Dict[str, List[str]]] = []
        for c in new_combos:
            key = ";".join([b + ":" + "|".join(sorted(c[b])) for b in sorted(c.keys())])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(c)
        combos = deduped

    rows: List[Dict[str, Any]] = []
    for idx, combo in enumerate(combos):
        bases = sorted(combo.keys())
        alleles = []
        for b in bases:
            alleles.extend(sorted(combo[b]))
        rows.append(
            {
                "label": f"genotype{idx}",
                "expected_genotype_basecodes": ",".join(bases),
                "expected_genotype_alleles": "; ".join(alleles),
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
) -> Tuple[str, str]:
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
                cross_date,
                created_at,
                cross_run_code
              )
              SELECT
                new_id.id                         AS id,
                tp.id                              AS tank_pair_id,
                mf.id                              AS female_fish_id,
                ff.id                              AS male_fish_id,
                CAST(:d_cross AS date)             AS cross_date,
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
                  AND c.cross_date = CAST(:d_cross AS date)
              )
              RETURNING id, cross_run_code
            )
            SELECT id, cross_run_code
            FROM ins
            UNION ALL
            SELECT id, cross_run_code
            FROM public.crosses c
            WHERE c.tank_pair_id = :tp_id
              AND c.cross_date = CAST(:d_cross AS date)
              AND NOT EXISTS (SELECT 1 FROM ins)
            LIMIT 1;
            """
        )
        cross_row = cx.execute(cross_sql, {"tp_id": tp_id, "d_cross": d_cross}).fetchone()
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

    primary_candidates: List[Tuple[str, float]] = []

    if not expected_rows.empty:
        with eng().begin() as cx:
            for _, r in expected_rows.iterrows():
                basecodes = (r.get("expected_genotype_basecodes") or "").strip()
                alleles = (r.get("expected_genotype_alleles") or "").strip()
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
                        text("SELECT id FROM public.genotypes_v11 WHERE genotype_code = :gcode"),
                        {"gcode": gcode},
                    ).scalar()
                    if gid is None:
                        continue

                base_tokens = [tok.strip() for tok in basecodes.split(",") if tok.strip()]
                for bc in base_tokens:
                    construct_row = cx.execute(
                        text(
                            """
                            SELECT id::uuid AS construct_id
                            FROM public.constructs
                            WHERE base_code = :bc
                            LIMIT 1;
                            """
                        ),
                        {"bc": bc},
                    ).fetchone()
                    if construct_row:
                        construct_id = construct_row._mapping["construct_id"]
                        cx.execute(
                            text(
                                """
                                INSERT INTO public.join_genotype_constructs_v11 (
                                  genotype_id,
                                  construct_id,
                                  created_at
                                )
                                VALUES (
                                  CAST(:gid AS uuid),
                                  CAST(:cid AS uuid),
                                  now()
                                )
                                ON CONFLICT DO NOTHING;
                                """
                            ),
                            {"gid": str(gid), "cid": str(construct_id)},
                        )

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

                frac = r.get("expected_fraction")
                try:
                    frac_val = float(frac) if frac is not None else 0.0
                except Exception:
                    frac_val = 0.0
                primary_candidates.append((str(gid), frac_val))

            if primary_candidates:
                primary_candidates.sort(key=lambda t: t[1], reverse=True)
                primary_gid, _ = primary_candidates[0]
                cx.execute(
                    text(
                        """
                        UPDATE public.clutches
                        SET genotype_v11_id = CAST(:gid AS uuid)
                        WHERE id = CAST(:clutch_id AS uuid)
                          AND genotype_v11_id IS NULL;
                        """
                    ),
                    {"gid": str(primary_gid), "clutch_id": str(clutch_id)},
                )

    return str(cross_run_code), str(clutch_code_out)


def _pv(row: Optional[pd.Series], col: str) -> str:
    if row is None:
        return ""
    return str(row.get(col, "") or "")


def _try_render_expected_labels(basecodes_csv: str) -> Dict[str, str]:
    basecodes = ",".join([t.strip() for t in (basecodes_csv or "").split(",") if t.strip()])
    if not basecodes:
        return {"tg": "", "fluortag": "", "fluororganelle": ""}

    cols = _cols("public", "v11_cross_parent_genotypes_labels")

    candidates = [
        ("genotype_basecodes", "genotype_tg_style", "genotype_fluortag_style", "genotype_fluororganelle_style"),
        ("expected_genotype_basecodes", "expected_genotype_tg_style", "expected_genotype_fluortag_style", "expected_genotype_fluororganelle_style"),
    ]
    for bc_col, tg_col, ft_col, fo_col in candidates:
        if bc_col in cols and tg_col in cols and ft_col in cols and fo_col in cols:
            sql = text(
                f"""
                SELECT
                  COALESCE({tg_col},'') AS tg,
                  COALESCE({ft_col},'') AS fluortag,
                  COALESCE({fo_col},'') AS fluororganelle
                FROM public.v11_cross_parent_genotypes_labels
                WHERE replace(COALESCE({bc_col},''),' ','') = replace(:bc,' ','')
                LIMIT 1;
                """
            )
            with eng().begin() as cx:
                row = cx.execute(sql, {"bc": basecodes}).fetchone()
            if row:
                m = row._mapping
                return {
                    "tg": str(m["tg"] or ""),
                    "fluortag": str(m["fluortag"] or ""),
                    "fluororganelle": str(m["fluororganelle"] or ""),
                }

    return {"tg": "", "fluortag": "", "fluororganelle": ""}


try:
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
    tp_view = pairs[
        [
            "tank_pair_code",
            "cross_label_tg",
            "cross_label_fluortag",
            "cross_label_fluororganelle",
            "mom_fish_code",
            "mom_tank_code",
            "dad_fish_code",
            "dad_tank_code",
            "created_at",
        ]
    ].copy()
    tp_view.insert(0, "✓", False)

    tp_grid = st.data_editor(
        tp_view,
        key="tank_pairs_picker_for_cross",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "✓": st.column_config.CheckboxColumn("✓", default=False),
            "tank_pair_code": st.column_config.TextColumn("Tank pair", disabled=True),
            "cross_label_tg": st.column_config.TextColumn("Cross (tg)", disabled=True, width="large"),
            "cross_label_fluortag": st.column_config.TextColumn("Cross (fluor-tag)", disabled=True, width="large"),
            "cross_label_fluororganelle": st.column_config.TextColumn("Cross (fluor-organelle)", disabled=True, width="large"),
            "mom_fish_code": st.column_config.TextColumn("Mother FSH", disabled=True),
            "mom_tank_code": st.column_config.TextColumn("Mother tank", disabled=True),
            "dad_fish_code": st.column_config.TextColumn("Father FSH", disabled=True),
            "dad_tank_code": st.column_config.TextColumn("Father tank", disabled=True),
            "created_at": st.column_config.DatetimeColumn("Created at", disabled=True),
        },
    )

    tp_sel_mask = tp_grid.get("✓", pd.Series(False, index=tp_grid.index)).fillna(False).astype(bool)
    if not tp_sel_mask.any():
        st.info("Select a tank pair above to schedule a cross.")
        st.stop()

    sel_idx = tp_grid.index[tp_sel_mask].tolist()[0]
    tp_row = pairs.iloc[sel_idx]
    tp_id = str(tp_row["tank_pair_id"])
    tp_code = str(tp_row["tank_pair_code"])

    st.success(f"Selected tank pair: {tp_code}")

    st.subheader("Step 1a — Parents (tanks, fish, marker_rollup + alleles)", anchor=False)

    parents_df = get_parent_detail(tp_id)

    mother = parents_df[parents_df["role"] == "mother"].iloc[0] if (
        not parents_df.empty and "mother" in parents_df["role"].values
    ) else None
    father = parents_df[parents_df["role"] == "father"].iloc[0] if (
        not parents_df.empty and "father" in parents_df["role"].values
    ) else None

    mom_bg = _pv(mother, "genetic_background")
    dad_bg = _pv(father, "genetic_background")

    mom_tg = _marker_rollup(_pv(mother, "treatment_label_tg_style"), _pv(mother, "genotype_tg_style"), mom_bg)
    dad_tg = _marker_rollup(_pv(father, "treatment_label_tg_style"), _pv(father, "genotype_tg_style"), dad_bg)

    mom_ft = _marker_rollup(_pv(mother, "treatment_label_fluortag_style"), _pv(mother, "genotype_fluortag_style"), mom_bg)
    dad_ft = _marker_rollup(_pv(father, "treatment_label_fluortag_style"), _pv(father, "genotype_fluortag_style"), dad_bg)

    mom_fo = _marker_rollup(_pv(mother, "treatment_label_fluororganelle_style"), _pv(mother, "genotype_fluororganelle_style"), mom_bg)
    dad_fo = _marker_rollup(_pv(father, "treatment_label_fluororganelle_style"), _pv(father, "genotype_fluororganelle_style"), dad_bg)

    pivot_rows = [
        ("Fish code", _pv(mother, "fish_code"), _pv(father, "fish_code")),
        ("Tank code", _pv(mother, "tank_code"), _pv(father, "tank_code")),
        ("Marker rollup (tg)", mom_tg, dad_tg),
        ("Marker rollup (fluor-tag)", mom_ft, dad_ft),
        ("Marker rollup (fluor-organelle)", mom_fo, dad_fo),
        ("Treatment codes", _pv(mother, "treatment_codes"), _pv(father, "treatment_codes")),
        ("Allele canonical rollup", _pv(mother, "allele_canonical_rollup"), _pv(father, "allele_canonical_rollup")),
        ("Allele label rollup", _pv(mother, "allele_label_rollup"), _pv(father, "allele_label_rollup")),
    ]
    pivot_df = pd.DataFrame(pivot_rows, columns=["Field", "Mother", "Father"])
    st.dataframe(pivot_df, use_container_width=True, hide_index=True)

    st.subheader("Step 2 — Genotype mixer (preview)", anchor=False)
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

        styles = []
        for _, r in expected_view.iterrows():
            styles.append(_try_render_expected_labels(str(r.get("expected_genotype_basecodes", "") or "")))
        expected_view["expected_tg_style"] = [d["tg"] for d in styles]
        expected_view["expected_fluortag_style"] = [d["fluortag"] for d in styles]
        expected_view["expected_fluororganelle_style"] = [d["fluororganelle"] for d in styles]

        expected_grid = st.data_editor(
            expected_view[
                [
                    "✓",
                    "label",
                    "expected_genotype_basecodes",
                    "expected_genotype_alleles",
                    "expected_tg_style",
                    "expected_fluortag_style",
                    "expected_fluororganelle_style",
                ]
            ],
            key="expected_genotypes_picker",
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "✓": st.column_config.CheckboxColumn("✓", default=True),
                "label": st.column_config.TextColumn("Label", disabled=True),
                "expected_genotype_basecodes": st.column_config.TextColumn("Genotype basecodes", disabled=True, width="large"),
                "expected_genotype_alleles": st.column_config.TextColumn("Alleles", disabled=True, width="large"),
                "expected_tg_style": st.column_config.TextColumn("Expected (tg)", disabled=True, width="large"),
                "expected_fluortag_style": st.column_config.TextColumn("Expected (fluor-tag)", disabled=True, width="large"),
                "expected_fluororganelle_style": st.column_config.TextColumn("Expected (fluor-organelle)", disabled=True, width="large"),
            },
        )

        expected_selected = expected_grid[expected_grid["✓"] == True].copy() if "✓" in expected_grid.columns else pd.DataFrame()

    st.subheader("Step 3 — Choose cross date", anchor=False)
    run_date = st.date_input("Cross date", value=date.today())

    st.subheader("Step 4 — Save cross + clutch", anchor=False)

    if st.button("💾 Schedule cross + clutch", type="primary", use_container_width=True):
        try:
            cross_run_code, clutch_code = upsert_cross_and_clutch_for_tank_pair(
                tp_id,
                run_date,
                expected_selected,
            )
            label_str = f"{tp_code} @ {run_date.isoformat()}"
            st.success(
                f"Cross scheduled: {cross_run_code} ({label_str}); "
                f"Clutch created: {clutch_code}; "
                f"Expected genotype rows saved: {len(expected_selected)}"
            )
        except Exception as e:
            st.error(f"Schedule failed: {type(e).__name__}: {e}")

except Exception as e:
    st.error(f"Page error: {type(e).__name__}: {e}")
    st.stop()