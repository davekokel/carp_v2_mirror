#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import hashlib
from pathlib import Path
from typing import Dict, List

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from carp_app.pipelines.construct_tokens import canonicalize_tokens, resolve_construct_ids, TokenError


def get_engine(db_url: str | None) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set (env DB_URL or --db-url)")
    print(f"DB_URL={url}")
    return create_engine(url)


def _canon_basecodes(raw: object) -> str | None:
    s = "" if raw is None else str(raw).strip()
    if not s or s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return None
    toks = canonicalize_tokens(s)
    toks = sorted(set(toks))
    return "|".join(toks) if toks else None


def _legacy_genotype_code(basecodes: str) -> str:
    h = hashlib.sha1(basecodes.encode("utf-8")).hexdigest()[:8]
    return f"LEGACY-{h}"


def main() -> None:
    p = argparse.ArgumentParser(description="v11: seed legacy clutch genotypes from ROI-derived clutch_code→basecodes CSV (strict).")
    p.add_argument("--roi-csv", required=True, help="CSV with at least: clutch_code, genotype_basecodes (or geno_base_codes_v9_exp)")
    p.add_argument("--db-url", help="Override DB_URL")
    args = p.parse_args()

    roi_csv = Path(args.roi_csv)
    if not roi_csv.exists():
        raise SystemExit(f"ROI CSV not found: {roi_csv}")

    df = pd.read_csv(roi_csv, low_memory=False)

    if "clutch_code" not in df.columns:
        raise SystemExit("ROI CSV must contain clutch_code")

    base_col = None
    for c in ("genotype_basecodes", "genotype_base_codes", "geno_base_codes_v9_exp", "genotype_base_codes_v9_exp"):
        if c in df.columns:
            base_col = c
            break
    if base_col is None:
        raise SystemExit("ROI CSV must contain one of: genotype_basecodes / geno_base_codes_v9_exp")

    df = df[["clutch_code", base_col]].copy()
    df["clutch_code"] = df["clutch_code"].astype(str).str.strip()
    df["basecodes_raw"] = df[base_col]
    df["basecodes"] = df["basecodes_raw"].apply(_canon_basecodes)
    df = df[(df["clutch_code"] != "") & df["basecodes"].notna()].copy()

    by_clutch: Dict[str, str] = {}
    for clutch_code, g in df.groupby("clutch_code"):
        vals = sorted(set([x for x in g["basecodes"].tolist() if isinstance(x, str) and x.strip()]))
        if not vals:
            continue
        if len(vals) != 1:
            raise SystemExit(f"[STOP] clutch_code={clutch_code} has multiple basecodes after canonicalization: {vals}")
        by_clutch[clutch_code] = vals[0]

    eng = get_engine(args.db_url)

    all_tokens: List[str] = []
    for bc in sorted(set(by_clutch.values())):
        all_tokens.extend(bc.split("|"))

    try:
        construct_ids = resolve_construct_ids(eng, all_tokens)
    except TokenError as e:
        raise SystemExit(f"[STOP] unresolved construct tokens in ROI basecodes: {e}") from e

    upsert_geno_sql = text(
        """
        INSERT INTO public.genotypes_v11 (id, genotype_code, genotype_basecodes, source_system, created_at)
        VALUES (gen_random_uuid(), :genotype_code, :genotype_basecodes, 'legacy_imaging', now())
        ON CONFLICT (genotype_code) DO UPDATE
        SET genotype_basecodes = EXCLUDED.genotype_basecodes
        RETURNING id::uuid AS id;
        """
    )

    update_clutch_sql = text(
        """
        UPDATE public.clutches
        SET genotype_v11_id = CAST(:gid AS uuid)
        WHERE clutch_code = :clutch_code
          AND source_system = 'legacy_imaging';
        """
    )

    insert_join_sql = text(
        """
        INSERT INTO public.join_genotype_constructs_v11 (genotype_id, construct_id, created_at)
        VALUES (CAST(:genotype_id AS uuid), CAST(:construct_id AS uuid), now())
        ON CONFLICT DO NOTHING;
        """
    )

    created_or_updated = 0
    clutch_updates = 0
    join_inserts = 0

    with eng.begin() as cx:
        for clutch_code, basecodes in sorted(by_clutch.items()):
            gcode = _legacy_genotype_code(basecodes)
            gid = cx.execute(upsert_geno_sql, {"genotype_code": gcode, "genotype_basecodes": basecodes}).scalar()
            if gid is None:
                raise SystemExit(f"[STOP] failed to upsert genotype for clutch_code={clutch_code}")
            created_or_updated += 1

            res = cx.execute(update_clutch_sql, {"gid": str(gid), "clutch_code": clutch_code})
            clutch_updates += int(res.rowcount or 0)

            for tok in basecodes.split("|"):
                cid = construct_ids.get(tok.lower())
                if not cid:
                    raise SystemExit(f"[STOP] construct id missing after resolve for token={tok!r}")
                r2 = cx.execute(insert_join_sql, {"genotype_id": str(gid), "construct_id": cid})
                join_inserts += int(r2.rowcount or 0)

        qc = cx.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM public.clutches WHERE source_system='legacy_imaging') AS n_legacy_clutches,
                  (SELECT count(*) FROM public.clutches WHERE source_system='legacy_imaging' AND genotype_v11_id IS NOT NULL) AS n_legacy_with_genotype,
                  (SELECT count(*) FROM public.genotypes_v11 WHERE source_system='legacy_imaging') AS n_legacy_genotypes,
                  (SELECT count(*) FROM public.join_genotype_constructs_v11 j
                     JOIN public.genotypes_v11 g ON g.id=j.genotype_id
                     WHERE g.source_system='legacy_imaging') AS n_join_rows_for_legacy_genotypes;
                """
            )
        ).first()

    print(f"[OK] base_col_used={base_col}")
    print(f"[OK] genotypes_touched={created_or_updated} clutch_updates={clutch_updates} join_inserts={join_inserts}")
    if qc is not None:
        print("[QC]", dict(qc._mapping))


if __name__ == "__main__":
    main()
