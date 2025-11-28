#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List, Dict, Set

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


ROI_CSV_DEFAULT = "seed_kits/legacy_wrangling_v2/working/legacy_imaging_annotations_for_db_v9.csv"


def get_engine(db_url: Optional[str] = None) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set or passed via --db-url")
    print(f"DB_URL={url}")
    return create_engine(url)


def norm(s: Optional[str]) -> str:
    if s is None:
        return ""
    return str(s).strip()


def load_roi_genotypes(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise SystemExit(f"[load_roi_genotypes] ROI CSV not found: {csv_path}")

    print(f"[load_roi_genotypes] Loading ROI CSV: {csv_path}")
    df = pd.read_csv(csv_path)

    required = ["bruker_roi_id", "genotype_base_codes", "genotype_allele_codes"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"[load_roi_genotypes] Missing required columns: {missing}")

    df = df.copy()
    df["roi_code"] = df["bruker_roi_id"].astype(str).map(lambda x: x.strip())
    df["genotype_base_codes"] = df["genotype_base_codes"].astype(str).map(lambda x: x.strip())
    df["genotype_allele_codes"] = df["genotype_allele_codes"].astype(str).map(lambda x: x.strip())

    mask = (
        (df["genotype_base_codes"] != "") |
        (df["genotype_allele_codes"] != "")
    )
    df = df[mask].copy()

    print(f"[load_roi_genotypes] ROI rows with genotype info: {len(df)}")
    return df[["roi_code", "genotype_base_codes", "genotype_allele_codes"]]


def build_roi_to_clutch_map(engine: Engine) -> pd.DataFrame:
    sql = text("""
        SELECT
          ra.roi_code,
          c.id::text AS clutch_id
        FROM public.imaging_roi_annotations ra
        JOIN public.imaging_slots s ON s.id = ra.slot_id
        JOIN public.imaging_clutch_memberships icm ON icm.slot_id = s.id
        JOIN public.clutches c ON c.id = icm.clutch_id
    """)
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    df = df.copy()
    df["roi_code"] = df["roi_code"].astype(str).map(lambda x: x.strip())
    df["clutch_id"] = df["clutch_id"].astype(str).map(lambda x: x.strip())
    df = df[df["roi_code"] != ""].drop_duplicates()

    print(f"[build_roi_to_clutch_map] DB ROI→clutch rows: {len(df)}")
    return df


def aggregate_genotypes_per_clutch(
    roi_geno: pd.DataFrame,
    roi_to_clutch: pd.DataFrame
) -> pd.DataFrame:

    merged = roi_geno.merge(roi_to_clutch, on="roi_code", how="inner")
    print(f"[aggregate_genotypes_per_clutch] ROI rows with clutch + genotype: {len(merged)}")

    if merged.empty:
        return pd.DataFrame(columns=["clutch_id", "base_codes", "allele_codes"])

    records: List[Dict[str, str]] = []

    for clutch_id, g in merged.groupby("clutch_id"):
        base_vals: Set[str] = set()
        allele_vals: Set[str] = set()

        for v in g["genotype_base_codes"]:
            v = norm(v)
            if v and v.lower() != "nan":
                base_vals.add(v)

        for v in g["genotype_allele_codes"]:
            v = norm(v)
            if v and v.lower() != "nan":
                allele_vals.add(v)

        base_str = ",".join(sorted(base_vals)) if base_vals else ""
        allele_str = ",".join(sorted(allele_vals)) if allele_vals else ""

        if base_str or allele_str:
            records.append({
                "clutch_id": clutch_id,
                "base_codes": base_str,
                "allele_codes": allele_str,
            })

    df_out = pd.DataFrame(records)
    print(f"[aggregate_genotypes_per_clutch] Clutches with aggregated genotype: {len(df_out)}")
    return df_out


def apply_updates(engine: Engine, clutch_geno: pd.DataFrame) -> int:
    if clutch_geno.empty:
        print("[apply_updates] No genotype updates to apply.")
        return 0

    sql = text("""
        UPDATE public.clutches AS c
        SET
          genotype_base_codes   = :base_codes,
          genotype_allele_codes = :allele_codes
        WHERE c.id::text = :clutch_id
          AND (c.genotype_base_codes IS NULL OR c.genotype_base_codes = '')
          AND (c.genotype_allele_codes IS NULL OR c.genotype_allele_codes = '');
    """)

    updated = 0

    with engine.begin() as cx:
        for _, row in clutch_geno.iterrows():
            res = cx.execute(sql, {
                "clutch_id": row["clutch_id"],
                "base_codes": row["base_codes"],
                "allele_codes": row["allele_codes"],
            })
            updated += res.rowcount

    print(f"[apply_updates] Updated {updated} clutch row(s).")
    return updated


def main():
    print("[v11_update_clutch_genotypes_from_rois] START")

    engine = get_engine()
    roi_csv = Path(ROI_CSV_DEFAULT)

    roi_geno = load_roi_genotypes(roi_csv)
    roi_map = build_roi_to_clutch_map(engine)
    clutch_geno = aggregate_genotypes_per_clutch(roi_geno, roi_map)

    apply_updates(engine, clutch_geno)

    print("[v11_update_clutch_genotypes_from_rois] DONE.")


if __name__ == "__main__":
    main()
