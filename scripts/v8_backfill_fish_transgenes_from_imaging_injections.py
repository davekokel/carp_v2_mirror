#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
from typing import Iterable, Tuple, Set

import pandas as pd
from sqlalchemy import create_engine, text


JFTA_TABLE = "public.join_fish_transgene_alleles"


def _get_engine():
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL not set")
    return create_engine(db_url)


def _read_imaging_injections(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = ["roi_dir", "transgene_base_code", "allele_number"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"imaging_injections CSV missing required columns: {missing}")
    df = df[required].copy()
    df = df.dropna(subset=["roi_dir", "transgene_base_code"])
    df["roi_dir"] = df["roi_dir"].astype(str)
    df["transgene_base_code"] = df["transgene_base_code"].astype(str).str.strip()
    df["allele_number"] = df["allele_number"].astype(int)
    df = df[df["transgene_base_code"] != ""]
    df = df.drop_duplicates(
        subset=["roi_dir", "transgene_base_code", "allele_number"]
    ).reset_index(drop=True)
    return df


def _roi_to_fish_mapping(engine, roi_dirs: Iterable[str]) -> pd.DataFrame:
    """
    Map ROI data_path → fish_id using the imaging schema.

    NOTE: This is currently a *stub* that assumes there is a way to get from
    imaging_rois → imaging_slots → fish_instance.

    TODO: Once the schema is wired, update the SQL below to reflect the real FK chain.
    """
    roi_dirs = list(set(roi_dirs))
    if not roi_dirs:
        return pd.DataFrame(columns=["roi_dir", "fish_id"])

    sql = text(
        """
        WITH input AS (
          SELECT unnest(:roi_dirs::text[]) AS roi_dir
        )
        SELECT
          i.roi_dir,
          f.id AS fish_id
        FROM input inp
        JOIN public.imaging_rois r
          ON r.data_path = inp.roi_dir
        JOIN public.imaging_slots s
          ON s.id = r.slot_id
        -- TODO: fix this join chain once fish is reachable from imaging:
        -- Option A: imaging_slots has fish_instance_id
        -- JOIN public.fish_instance f
        --   ON f.id = s.fish_instance_id
        --
        -- Option B: imaging_slots has clutch_member_id
        -- JOIN public.clutch_members cm
        --   ON cm.id = s.clutch_member_id
        -- JOIN public.fish_instance f
        --   ON f.id = cm.fish_id
        JOIN public.fish_instance f
          ON f.id = s.fish_instance_id  -- <-- adjust this line to your real FK
        ;
        """
    )

    with engine.begin() as cx:
        df = pd.read_sql(sql, cx, params={"roi_dirs": roi_dirs})

    # Ensure expected columns even if result is empty
    if "roi_dir" not in df.columns:
        df["roi_dir"] = []
    if "fish_id" not in df.columns:
        df["fish_id"] = []
    df["roi_dir"] = df["roi_dir"].astype(str)
    df["fish_id"] = df["fish_id"].astype("Int64")
    return df


def _load_existing(engine) -> Set[Tuple[int, str, int]]:
    sql = text(
        f"""
        SELECT fish_id, transgene_base_code, allele_number
        FROM {JFTA_TABLE}
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)
    if df.empty:
        return set()
    df["fish_id"] = df["fish_id"].astype(int)
    df["transgene_base_code"] = df["transgene_base_code"].astype(str)
    df["allele_number"] = df["allele_number"].astype(int)
    return set(
        zip(
            df["fish_id"].tolist(),
            df["transgene_base_code"].tolist(),
            df["allele_number"].tolist(),
        )
    )


def _insert_missing(engine, links: pd.DataFrame) -> int:
    existing = _load_existing(engine)
    rows: list[Tuple[int, str, int]] = []
    for _, row in links.iterrows():
        key = (
            int(row["fish_id"]),
            str(row["transgene_base_code"]),
            int(row["allele_number"]),
        )
        if key in existing:
            continue
        rows.append(key)

    if not rows:
        return 0

    sql = text(
        f"""
        INSERT INTO {JFTA_TABLE} (fish_id, transgene_base_code, allele_number)
        VALUES (:fish_id, :transgene_base_code, :allele_number)
        """
    )

    with engine.begin() as cx:
        for fish_id, base_code, allele_number in rows:
            cx.execute(
                sql,
                {
                    "fish_id": fish_id,
                    "transgene_base_code": base_code,
                    "allele_number": allele_number,
                },
            )

    return len(rows)


def main():
    ap = argparse.ArgumentParser(
        description=(
            "Backfill join_fish_transgene_alleles from imaging_injections "
            "(once imaging → fish links exist)."
        )
    )
    ap.add_argument(
        "--imaging-injections-csv",
        required=True,
        help="Path to imaging_injections.csv (ROI ↔ plasmid mapping)",
    )
    args = ap.parse_args()

    engine = _get_engine()
    inj = _read_imaging_injections(args.imaging_injections_csv)

    if inj.empty:
        print("imaging_injections CSV is empty; nothing to do.")
        return

    # Map roi_dir → fish_id using the imaging schema
    roi_dirs = inj["roi_dir"].unique().tolist()
    roi2fish = _roi_to_fish_mapping(engine, roi_dirs)

    if roi2fish.empty:
        print("No ROI → fish mappings found; check imaging schema/FK wiring.")
        return

    merged = inj.merge(roi2fish, on="roi_dir", how="inner")
    merged = merged[merged["fish_id"].notna()].copy()
    if merged.empty:
        print("No imaging injections had a resolvable fish_id; nothing to insert.")
        return

    merged["fish_id"] = merged["fish_id"].astype(int)

    links = merged[["fish_id", "transgene_base_code", "allele_number"]].drop_duplicates(
        subset=["fish_id", "transgene_base_code", "allele_number"]
    ).reset_index(drop=True)

    if links.empty:
        print("No unique fish ↔ transgene links to insert.")
        return

    inserted = _insert_missing(engine, links)
    print(
        f"Resolved {len(links)} fish ↔ transgene links from imaging; "
        f"inserted {inserted} new rows into {JFTA_TABLE}."
    )


if __name__ == "__main__":
    main()
