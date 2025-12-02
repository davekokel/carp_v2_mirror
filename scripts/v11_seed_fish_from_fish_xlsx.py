#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import pathlib
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.fish_v11_shared import (
    load_construct_ids,
    ensure_allele_new_or_existing,
    ensure_group_and_genotype_for_alleles,
    ensure_line_for_group,
    create_instances_with_genotype_and_bg,
)


def norm(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip()


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    return create_engine(url)


def load_fish_rows(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"[v11_seed_fish] fish.xlsx not found at {path}")

    df = pd.read_excel(path)

    required_cols = [
        "line_nickname",
        "birthday",
        "genetic_background",
        "instance_stage",
        "transgene_base_code",
        "allele_nickname",
    ]
    for col in required_cols:
        if col not in df.columns:
            raise SystemExit(f"[v11_seed_fish] missing required column: {col}")

    df = df.copy()
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(norm)

    return df


def build_construct_lut(cx) -> Dict[str, str]:
    """
    Build a LUT from various construct code variants to canonical construct_code.
    This lets us map pDQM005 / PDQM005 / PDQM-005 → the actual construct_code stored in constructs.
    """
    df = pd.read_sql(
        "SELECT construct_code, base_code FROM public.constructs",
        cx,
    )

    lut: Dict[str, str] = {}
    for _, r in df.iterrows():
        code = norm(r.get("construct_code"))
        base = norm(r.get("base_code"))

        if not code:
            continue

        variants = set()

        for raw in (code, base):
            if not raw:
                continue
            k = raw
            variants.add(k)
            variants.add(k.lower())
            k_ns = k.replace("-", "").replace(" ", "")
            variants.add(k_ns)
            variants.add(k_ns.lower())

        for v in variants:
            lut[v] = code

    return lut


def main() -> None:
    ENGINE = get_engine()
    FISH_XLSX = "seed_kits/2025-11-15-121231-autoload/fish.xlsx"

    df = load_fish_rows(Path(FISH_XLSX))
    if df.empty:
        print("[v11_seed_fish] no fish rows; skipping")
        return

    with ENGINE.begin() as cx:
        construct_ids_df = load_construct_ids(ENGINE)
        construct_lut = build_construct_lut(cx)

        n_instances_total = 0
        n_lines_created = 0
        n_lines_reused = 0
        skipped_missing_allele_nickname = 0
        skipped_bad_construct_code = 0

        for idx, row in df.iterrows():
            line_nickname = norm(row.get("line_nickname"))
            bg_code = norm(row.get("genetic_background"))
            instance_stage = norm(row.get("instance_stage"))
            birthday = row.get("birthday")
            fish_code = ""  # no explicit fish_code column
            notes = norm(row.get("description"))

            raw_base_code = norm(row.get("transgene_base_code"))
            allele_nickname = norm(row.get("allele_nickname"))

            if not raw_base_code:
                print(f"[ROW {idx}] skipping: no transgene_base_code")
                continue
            if not line_nickname:
                print(f"[ROW {idx}] skipping: no line_nickname")
                continue
            if not bg_code:
                print(f"[ROW {idx}] skipping: no genetic_background (bg_code)")
                continue
            if not allele_nickname:
                print(
                    f"[ROW {idx}] skipping: no allele_nickname for transgene_base_code={raw_base_code}"
                )
                skipped_missing_allele_nickname += 1
                continue

            keys = [
                raw_base_code,
                raw_base_code.lower(),
                raw_base_code.replace("-", "").replace(" ", ""),
                raw_base_code.replace("-", "").replace(" ", "").lower(),
            ]
            canonical_base_code = None
            for k in keys:
                if k in construct_lut:
                    canonical_base_code = construct_lut[k]
                    break

            if not canonical_base_code:
                print(
                    f"[ROW {idx}] skipping: transgene_base_code={raw_base_code} "
                    f"does not match any construct_code/base_code in public.constructs"
                )
                skipped_bad_construct_code += 1
                continue

            base_code = canonical_base_code
            allele_mode = "Create new allele"

            base2, allele_number = ensure_allele_new_or_existing(
                cx,
                transgene_base_code=base_code,
                mode=allele_mode,
                existing_allele_number=None,
                new_allele_nickname=allele_nickname,
            )

            resolved_alleles = [
                {
                    "transgene_base_code": base2,
                    "allele_number": allele_number,
                }
            ]

            fish_group_id, genotype_v11_id, genotype_code = ensure_group_and_genotype_for_alleles(
                cx,
                resolved_alleles=resolved_alleles,
                constructs_ids_df=construct_ids_df,
            )

            line_id, line_code, created_new_line = ensure_line_for_group(
                cx,
                fish_group_id=fish_group_id,
                nickname=line_nickname,
                primary_base_code=base2,
                default_bg_code=bg_code,
            )

            if created_new_line:
                n_lines_created += 1
            else:
                n_lines_reused += 1

            instances: List[Dict[str, Any]] = [
                {
                    "fish_code": fish_code or None,
                    "instance_stage": instance_stage or None,
                    "birthday": birthday,
                    "genetic_background": bg_code,
                    "notes": notes or None,
                }
            ]

            n_instances, n_tanks = create_instances_with_genotype_and_bg(
                cx,
                line_id=line_id,
                line_code=line_code,
                genotype_v11_id=genotype_v11_id,
                instances=instances,
            )

            n_instances_total += n_instances

            print(
                f"[ROW {idx}] line {line_code} (genotype {genotype_code}) "
                f"+ {n_instances} instance(s) ({n_tanks} tank(s))"
            )

        print(
            f"[v11_seed_fish] total instances={n_instances_total}, "
            f"lines created={n_lines_created}, lines reused={n_lines_reused}, "
            f"skipped_missing_allele_nickname={skipped_missing_allele_nickname}, "
            f"skipped_bad_construct_code={skipped_bad_construct_code}"
        )


if __name__ == "__main__":
    main()
