#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


_NULLS = {"", "nan", "none", "na", "n/a", "<na>"}
_BASE_RE = re.compile(r"^([A-Za-z]+)[-_ ]*0*([0-9]+)$")


def _norm_cell(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in _NULLS:
        return ""
    return s


def _canon_base(tok: str) -> str:
    t = _norm_cell(tok)
    if not t:
        raise SystemExit("[STOP] empty token")
    m = _BASE_RE.match(t)
    if not m:
        raise SystemExit(f"[STOP] cannot canonicalize basecode token: {tok!r}")
    return f"{m.group(1).lower()}-{int(m.group(2))}"


def _split_basecodes_strict(cell: str) -> List[str]:
    raw = _norm_cell(cell)
    if not raw:
        return []
    parts = re.split(r"[|,;]+", raw)
    out: List[str] = []
    seen: Set[str] = set()
    for p in parts:
        p = _norm_cell(p)
        if not p:
            continue
        canon = _canon_base(p)
        if canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set")
    print(f"DB_URL={url}")
    return create_engine(url)


def main() -> None:
    eng = get_engine()

    with eng.begin() as cx:
        cols = set(
            r[0]
            for r in cx.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema='raw' AND table_name='legacy_roi_enriched_v9'
                    ORDER BY ordinal_position
                    """
                )
            ).fetchall()
        )

    need = {
        "legacy_clutch_key",
        "treatment_rna_rna_base_code",
        "treatment_rna_rna_base_code_from_enrich",
        "treatment_plasmid_plasmid_base_code",
        "treatment_plasmid_plasmid_base_code_from_enrich",
    }
    missing = sorted(list(need - cols))
    if missing:
        raise SystemExit(f"[STOP] raw.legacy_roi_enriched_v9 missing required columns: {missing}")

    with eng.begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT
                  legacy_clutch_key,
                  treatment_rna_rna_base_code,
                  treatment_rna_rna_base_code_from_enrich,
                  treatment_plasmid_plasmid_base_code,
                  treatment_plasmid_plasmid_base_code_from_enrich
                FROM raw.legacy_roi_enriched_v9
                WHERE coalesce(btrim(legacy_clutch_key),'') <> ''
                """
            ),
            cx,
        )

        cl = pd.read_sql(
            text(
                """
                SELECT
                  c.id::uuid AS clutch_id,
                  c.legacy_clutch_key,
                  t.treat_code
                FROM public.clutches c
                JOIN public.treated_clutches_v11 tc ON tc.clutch_id = c.id
                JOIN public.treatments t ON t.id = tc.treatment_id
                WHERE c.source_system='legacy_imaging'
                  AND coalesce(btrim(c.legacy_clutch_key),'') <> ''
                  AND t.treat_code LIKE 'T-LEGACY-%'
                """
            ),
            cx,
        )

    if cl.empty:
        raise SystemExit("[STOP] no legacy treated clutches found with treat_code LIKE 'T-LEGACY-%'")

    df = df.copy()
    for c in df.columns:
        df[c] = df[c].astype("string").fillna("").map(_norm_cell)

    cl = cl.copy()
    cl["legacy_clutch_key"] = cl["legacy_clutch_key"].astype("string").fillna("").map(_norm_cell)

    df = df.merge(cl[["legacy_clutch_key", "treat_code"]], on="legacy_clutch_key", how="inner")
    if df.empty:
        raise SystemExit("[STOP] join produced 0 rows: raw.legacy_roi_enriched_v9 x clutches(treat_code)")

    def parse_pair(base_col: str, enrich_col: str, row) -> Tuple[Tuple[str, ...], str]:
        a_raw = row.get(base_col, "")
        b_raw = row.get(enrich_col, "")
        a = tuple(_split_basecodes_strict(a_raw)) if a_raw else tuple()
        b = tuple(_split_basecodes_strict(b_raw)) if b_raw else tuple()

        if a and b:
            if set(a) != set(b):
                raise SystemExit(
                    "[STOP] basecode disagreement between columns "
                    f"{base_col}={a_raw!r} vs {enrich_col}={b_raw!r} (canon {a} vs {b}) "
                    f"legacy_clutch_key={row.get('legacy_clutch_key')!r}"
                )
            return tuple(sorted(set(b))), enrich_col

        if b:
            return tuple(sorted(set(b))), enrich_col
        if a:
            return tuple(sorted(set(a))), base_col
        return tuple(), ""

    rows_parsed: List[Dict[str, object]] = []
    used_counts = defaultdict(int)

    for _, r in df.iterrows():
        rnas, used_rna = parse_pair("treatment_rna_rna_base_code", "treatment_rna_rna_base_code_from_enrich", r)
        pls, used_pls = parse_pair("treatment_plasmid_plasmid_base_code", "treatment_plasmid_plasmid_base_code_from_enrich", r)

        if used_rna:
            used_counts[("rna", used_rna)] += 1
        if used_pls:
            used_counts[("plasmid", used_pls)] += 1

        rows_parsed.append(
            {
                "legacy_clutch_key": r["legacy_clutch_key"],
                "treat_code": r["treat_code"],
                "rnas": rnas,
                "plasmids": pls,
            }
        )

    d2 = pd.DataFrame(rows_parsed)

    by_treat: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]] = {}
    for treat_code, g in d2.groupby("treat_code", dropna=False):
        sigs = set((tuple(sorted(set(a))), tuple(sorted(set(b)))) for a, b in zip(g["rnas"].tolist(), g["plasmids"].tolist()))
        if len(sigs) != 1:
            ex = list(sigs)[:5]
            raise SystemExit(f"[STOP] treat_code={treat_code} has multiple distinct ingredient sets (examples={ex})")
        by_treat[str(treat_code)] = next(iter(sigs))

    with eng.begin() as cx:
        c_df = pd.read_sql(text("SELECT id::uuid AS construct_id, lower(base_code) AS base_code FROM public.constructs WHERE coalesce(btrim(base_code),'') <> ''"), cx)
        if c_df.empty:
            raise SystemExit("[STOP] constructs table empty?")
        base_to_id = {r["base_code"]: r["construct_id"] for _, r in c_df.iterrows()}

        t_df = pd.read_sql(text("SELECT id::uuid AS treatment_id, treat_code FROM public.treatments WHERE treat_code LIKE 'T-LEGACY-%'"), cx)
        treat_to_id = {str(r["treat_code"]): r["treatment_id"] for _, r in t_df.iterrows()}

        missing_treats = [tc for tc in by_treat.keys() if tc not in treat_to_id]
        if missing_treats:
            raise SystemExit(f"[STOP] treat_code(s) missing in public.treatments: {missing_treats[:50]}")

        cx.execute(
            text(
                """
                DELETE FROM public.treatment_mix_constructs tmc
                USING public.treatment_mixes tm, public.treatments t
                WHERE tmc.mix_id = tm.id
                  AND tm.treatment_id = t.id
                  AND t.treat_code = ANY(:treat_codes)
                """
            ),
            {"treat_codes": list(by_treat.keys())},
        )

        cx.execute(
            text(
                """
                DELETE FROM public.treatment_mixes tm
                USING public.treatments t
                WHERE tm.treatment_id = t.id
                  AND t.treat_code = ANY(:treat_codes)
                  AND tm.mix_code <> 'M1'
                """
            ),
            {"treat_codes": list(by_treat.keys())},
        )

        cx.execute(
            text(
                """
                INSERT INTO public.treatment_mixes (treatment_id, mix_code, notes, created_at)
                SELECT t.id, 'M1', 'synced_from_raw.legacy_roi_enriched_v9', now()
                FROM public.treatments t
                WHERE t.treat_code = ANY(:treat_codes)
                ON CONFLICT (treatment_id, mix_code) DO UPDATE
                SET notes = EXCLUDED.notes
                """
            ),
            {"treat_codes": list(by_treat.keys())},
        )

        mix_df = pd.read_sql(
            text(
                """
                SELECT tm.id::uuid AS mix_id, t.treat_code
                FROM public.treatment_mixes tm
                JOIN public.treatments t ON t.id = tm.treatment_id
                WHERE t.treat_code = ANY(:treat_codes)
                  AND tm.mix_code = 'M1'
                """
            ),
            cx,
            params={"treat_codes": list(by_treat.keys())},
        )
        mix_by_treat = {str(r["treat_code"]): r["mix_id"] for _, r in mix_df.iterrows()}

        inserts = []
        for treat_code, (rnas, pls) in sorted(by_treat.items()):
            mix_id = mix_by_treat.get(treat_code)
            if not mix_id:
                raise SystemExit(f"[STOP] missing M1 mix row for treat_code={treat_code}")

            for bc in rnas:
                cid = base_to_id.get(bc)
                if not cid:
                    raise SystemExit(f"[STOP] RNA base_code not found in constructs.base_code: {bc!r} treat_code={treat_code}")
                inserts.append({"mix_id": str(mix_id), "construct_id": str(cid), "delivery_form": "rna"})

            for bc in pls:
                cid = base_to_id.get(bc)
                if not cid:
                    raise SystemExit(f"[STOP] plasmid base_code not found in constructs.base_code: {bc!r} treat_code={treat_code}")
                inserts.append({"mix_id": str(mix_id), "construct_id": str(cid), "delivery_form": "plasmid"})

        if inserts:
            cx.execute(
                text(
                    """
                    INSERT INTO public.treatment_mix_constructs (mix_id, construct_id, delivery_form, concentration, notes, created_at)
                    VALUES (:mix_id::uuid, :construct_id::uuid, :delivery_form, NULL, 'synced_from_raw.legacy_roi_enriched_v9', now())
                    ON CONFLICT DO NOTHING
                    """
                ),
                inserts,
            )

        qc = cx.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM public.treatments WHERE treat_code = ANY(:treat_codes)) AS n_treatments_targeted,
                  (SELECT count(*) FROM public.treatment_mixes tm
                     JOIN public.treatments t ON t.id=tm.treatment_id
                     WHERE t.treat_code = ANY(:treat_codes) AND tm.mix_code='M1') AS n_m1_mixes,
                  (SELECT count(*) FROM public.treatment_mix_constructs tmc
                     JOIN public.treatment_mixes tm ON tm.id=tmc.mix_id
                     JOIN public.treatments t ON t.id=tm.treatment_id
                     WHERE t.treat_code = ANY(:treat_codes)) AS n_mix_construct_rows
                """
            ),
            {"treat_codes": list(by_treat.keys())},
        ).first()

    print("[OK] treat_codes_synced", len(by_treat))
    print("[OK] used_column_counts", dict(used_counts))
    if qc is not None:
        print("[QC]", dict(qc._mapping))


if __name__ == "__main__":
    main()
