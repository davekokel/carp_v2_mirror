#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

OUT_DEFAULT = "seed_kits/legacy_wrangling_v4/working/infer_genotypes_from_roi_folder_plan.tsv"

INFER_SOURCE = "inferred_from_roi_folder"
INFER_RULE = "slug_mode_genotype_v11_id"

def _slug_from_roi_path_sql() -> str:
    """
    Extract folder slug from roi_path:
      /.../(Aang_Foundation|Korra_Foundation)/<experiment_folder>/<roi...>
    Then strip YYYYMMDD_ or YYYYMMDD- prefix and normalize separators.
    """
    return r"""
      lower(
        replace(
          regexp_replace(
            (regexp_match(ira.roi_path, '/(?:Aang_Foundation|Korra_Foundation)/([^/]+)/'))[1],
            '^[0-9]{8}[_-]?', ''
          ),
          '-',
          '_'
        )
      )
    """

def build_plan(engine, batch_id: str) -> pd.DataFrame:
    slug_expr = _slug_from_roi_path_sql()

    sql = text(f"""
    WITH roi_ctx AS (
      SELECT
        ira.roi_path,
        m.clutch_id,
        c.clutch_code,
        c.genotype_v11_id,
        {slug_expr} AS slug
      FROM public.imaging_roi_annotations ira
      JOIN public.imaging_clutch_memberships m ON m.slot_id = ira.slot_id
      JOIN public.clutches c ON c.id = m.clutch_id
      WHERE ira.roi_path IS NOT NULL
    ),
    jct_counts AS (
      SELECT clutch_id, count(*) AS n
      FROM public.join_clutch_treatments
      GROUP BY clutch_id
    ),
    needs AS (
      SELECT DISTINCT
        r.clutch_id,
        r.clutch_code,
        r.slug
      FROM roi_ctx r
      LEFT JOIN jct_counts jc ON jc.clutch_id = r.clutch_id
      WHERE coalesce(btrim(r.slug),'') <> ''
        AND r.genotype_v11_id IS NULL
        AND coalesce(jc.n,0) = 0
    ),
    slug_geno_ranked AS (
      SELECT
        r.slug,
        r.genotype_v11_id::text AS genotype_v11_id,
        count(*) AS n
      FROM roi_ctx r
      WHERE r.genotype_v11_id IS NOT NULL
        AND coalesce(btrim(r.slug),'') <> ''
      GROUP BY 1,2
    ),
    slug_geno_mode AS (
      SELECT DISTINCT ON (slug)
        slug,
        genotype_v11_id,
        n
      FROM slug_geno_ranked
      ORDER BY slug, n DESC, genotype_v11_id
    ),
    plan AS (
      SELECT
        n.slug,
        n.clutch_code,
        n.clutch_id::text AS clutch_id,
        coalesce(gm.genotype_v11_id,'') AS inferred_genotype_v11_id,
        coalesce(gm.n,0) AS support_n
      FROM needs n
      LEFT JOIN slug_geno_mode gm ON gm.slug = n.slug
    )
    SELECT
      :batch_id AS batch_id,
      slug,
      clutch_code,
      clutch_id,
      inferred_genotype_v11_id,
      support_n
    FROM plan
    ORDER BY slug, clutch_code;
    """)

    with engine.begin() as cx:
        df = pd.read_sql(sql, cx, params={"batch_id": batch_id})

    return df

def apply_plan(engine, df_plan: pd.DataFrame, batch_id: str) -> Tuple[int, int]:
    # Only apply where we actually inferred a genotype id
    df = df_plan.copy()
    df["inferred_genotype_v11_id"] = df["inferred_genotype_v11_id"].astype(str).str.strip()
    df = df[df["inferred_genotype_v11_id"].ne("")].copy()
    if df.empty:
        return (0, 0)

    rows = df[["clutch_id","inferred_genotype_v11_id"]].to_dict("records")

    updated = 0
    skipped = 0

    upd = text("""
      UPDATE public.clutches c
      SET
        genotype_v11_id = CAST(:gid AS uuid),
        genotype_infer_source = :src,
        genotype_infer_rule = :rule,
        genotype_infer_batch_id = :batch,
        genotype_inferred_at = now()
      WHERE c.id = CAST(:clutch_id AS uuid)
        AND c.genotype_v11_id IS NULL
    """)

    with engine.begin() as cx:
        for r in rows:
            res = cx.execute(
                upd,
                {
                    "clutch_id": r["clutch_id"],
                    "gid": r["inferred_genotype_v11_id"],
                    "src": INFER_SOURCE,
                    "rule": INFER_RULE,
                    "batch": batch_id,
                },
            )
            if int(res.rowcount or 0) > 0:
                updated += int(res.rowcount or 0)
            else:
                skipped += 1

    return (updated, skipped)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-tsv", default=OUT_DEFAULT)
    ap.add_argument("--batch", default=f"legacy_roi_folder_genotype_infer_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL is not set")

    engine = create_engine(db_url)

    df = build_plan(engine, args.batch)

    out_path = Path(args.out_tsv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, sep="\t", index=False)
    print("[OK] WROTE", out_path, "ROWS", len(df))

    n_need = int(len(df))
    n_can = int((df["inferred_genotype_v11_id"].astype(str).str.strip() != "").sum())
    print(f"[QC] clutches_needing_genotype_and_no_treatment={n_need} clutches_with_inferred_genotype={n_can}")

    if not args.apply:
        print("[OK] dry-run only (use --apply to write to DB)")
        return

    updated, skipped = apply_plan(engine, df, args.batch)
    print(f"[OK] applied genotype inference: updated={updated} skipped={skipped}")

