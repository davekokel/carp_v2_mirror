#!/usr/bin/env python3
from __future__ import annotations

import os
import argparse
import hashlib
from typing import Dict, List

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: str | None) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def canonical_basecodes(raw: str | None) -> List[str]:
    if raw is None:
        return []
    s = str(raw).strip()
    if not s or s.lower() == "nan":
        return []
    s = s.replace("[", "").replace("]", "")
    parts: List[str] = []
    for token in s.split("|"):
        t = token.strip().strip("'").strip('"')
        if t:
            parts.append(t)
    return sorted(set(parts))


def load_clutch_basecodes_from_roi_csv(roi_csv_path: str) -> Dict[str, str]:
    """
    From legacy_imaging_annotations_for_db_v9.csv:
    legacy_clutch_key -> canonical genotype basecodes string
    """
    df = pd.read_csv(roi_csv_path)
    if "legacy_clutch_key" not in df.columns:
        raise SystemExit("ROI CSV must contain legacy_clutch_key")

    base_col = None
    if "genotype_base_codes" in df.columns:
        base_col = "genotype_base_codes"
    elif "genotype_base_codes_slug" in df.columns:
        base_col = "genotype_base_codes_slug"
    else:
        raise SystemExit(
            "ROI CSV must contain genotype_base_codes or genotype_base_codes_slug"
        )

    clutch_to_codes: Dict[str, List[str]] = {}

    for _, row in df.iterrows():
        key = str(row["legacy_clutch_key"]).strip()
        if not key or key.lower() == "nan":
            continue
        raw_codes = row.get(base_col, "")
        codes = canonical_basecodes(raw_codes)
        if not codes:
            continue
        clutch_to_codes.setdefault(key, []).extend(codes)

    result: Dict[str, str] = {}
    for key, codes in clutch_to_codes.items():
        uniq = sorted(set(codes))
        if not uniq:
            continue
        result[key] = "|".join(uniq)

    print(
        f"[v11_seed_legacy_genotypes_from_v9_csv] clutches with genotype basecodes from ROI CSV: {len(result)}"
    )
    return result


def load_legacy_clutch_to_code_from_clutch_csv(clutch_csv_path: str) -> Dict[str, str]:
    """
    From legacy_clutches_v9.csv:
    legacy_clutch_key -> clutch_code for all 64 clutches.
    """
    df = pd.read_csv(clutch_csv_path)
    missing = [c for c in ("legacy_clutch_key", "clutch_code") if c not in df.columns]
    if missing:
        raise SystemExit(
            f"clutch CSV must contain columns: legacy_clutch_key, clutch_code (missing: {missing})"
        )

    mapping: Dict[str, str] = {}
    for _, row in df.iterrows():
        key = str(row["legacy_clutch_key"]).strip()
        code = str(row["clutch_code"]).strip()
        if not key or key.lower() == "nan":
            continue
        if not code or code.lower() == "nan":
            continue
        mapping[key] = code

    print(
        f"[v11_seed_legacy_genotypes_from_v9_csv] legacy_clutch_key → clutch_code entries from clutch CSV: {len(mapping)}"
    )
    return mapping


def load_existing_genotypes(engine: Engine) -> Dict[str, str]:
    sql = text(
        """
        SELECT id::text AS genotype_id,
               genotype_basecodes
        FROM public.genotypes_v11
        """
    )
    with engine.begin() as cx:
        rows = list(cx.execute(sql))

    mapping: Dict[str, str] = {}
    for genotype_id, basecodes in rows:
        base = (basecodes or "").strip()
        if base:
            mapping[base] = genotype_id
    print(
        f"[v11_seed_legacy_genotypes_from_v9_csv] existing genotypes: {len(mapping)}"
    )
    return mapping


def ensure_genotype(engine: Engine, basecodes: str, existing: Dict[str, str]) -> str:
    base = basecodes.strip()
    if not base:
        raise ValueError("empty basecodes in ensure_genotype")

    if base in existing:
        return existing[base]

    h = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
    genotype_code = f"LEGACY-{h}"
    genotype_pretty = base

    with engine.begin() as cx:
        gid = cx.execute(
            text(
                """
                INSERT INTO public.genotypes_v11 (
                  id,
                  genotype_code,
                  genotype_basecodes,
                  genotype_pretty,
                  created_at
                )
                VALUES (
                  gen_random_uuid(),
                  :genotype_code,
                  :genotype_basecodes,
                  :genotype_pretty,
                  now()
                )
                RETURNING id::text;
                """
            ),
            {
                "genotype_code": genotype_code,
                "genotype_basecodes": base,
                "genotype_pretty": genotype_pretty,
            },
        ).scalar()

    existing[base] = gid
    print(
        f"[v11_seed_legacy_genotypes_from_v9_csv] created genotype {gid} for basecodes='{base}'"
    )
    return gid


def build_clutch_code_to_basecodes(
    clutch_basecodes_by_legacy_key: Dict[str, str],
    legacy_to_clutch_code: Dict[str, str],
) -> Dict[str, str]:
    """
    Combine:
      legacy_clutch_key -> basecodes
      legacy_clutch_key -> clutch_code
    into:
      clutch_code -> basecodes
    """
    result: Dict[str, str] = {}
    for legacy_key, base in clutch_basecodes_by_legacy_key.items():
        clutch_code = legacy_to_clutch_code.get(legacy_key)
        if not clutch_code:
            continue
        clutch_code_clean = clutch_code.strip()
        if not clutch_code_clean:
            continue
        result[clutch_code_clean] = base
    print(
        f"[v11_seed_legacy_genotypes_from_v9_csv] clutch_code → basecodes entries: {len(result)}"
    )
    return result


def apply_genotypes_to_clutches(
    engine: Engine,
    clutch_code_basecodes: Dict[str, str],
    existing_genotypes: Dict[str, str],
) -> None:
    if not clutch_code_basecodes:
        print("[v11_seed_legacy_genotypes_from_v9_csv] no clutches to update")
        return

    updated = 0
    with engine.begin() as cx:
        for clutch_code, base in clutch_code_basecodes.items():
            gid = existing_genotypes.get(base)
            if not gid:
                continue
            res = cx.execute(
                text(
                    """
                    UPDATE public.clutches c
                    SET genotype_v11_id = :gid
                    WHERE c.clutch_code = :clutch_code
                      AND c.genotype_v11_id IS NULL;
                    """
                ),
                {"gid": gid, "clutch_code": clutch_code},
            )
            updated += res.rowcount

    print(
        f"[v11_seed_legacy_genotypes_from_v9_csv] set genotype_v11_id for {updated} clutch(es)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed v11 legacy genotypes from legacy_imaging_annotations_for_db_v9.csv + legacy_clutches_v9.csv"
    )
    parser.add_argument(
        "--roi-csv",
        default="seed_kits/legacy_wrangling_v2/working/legacy_imaging_annotations_for_db_v9.csv",
        help="Path to legacy_imaging_annotations_for_db_v9.csv",
    )
    parser.add_argument(
        "--clutch-csv",
        default="seed_kits/legacy_wrangling_v2/working/legacy_clutches_v9.csv",
        help="Path to legacy_clutches_v9.csv (legacy_clutch_key → clutch_code)",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    engine = get_engine(args.db_url)

    clutch_basecodes_by_legacy = load_clutch_basecodes_from_roi_csv(args.roi_csv)
    if not clutch_basecodes_by_legacy:
        print(
            "[v11_seed_legacy_genotypes_from_v9_csv] no clutch basecodes found in ROI CSV; nothing to do"
        )
        return

    legacy_to_clutch_code = load_legacy_clutch_to_code_from_clutch_csv(args.clutch_csv)
    clutch_code_to_basecodes = build_clutch_code_to_basecodes(
        clutch_basecodes_by_legacy, legacy_to_clutch_code
    )
    if not clutch_code_to_basecodes:
        print(
            "[v11_seed_legacy_genotypes_from_v9_csv] no clutch_code → basecodes mapping; nothing to do"
        )
        return

    existing = load_existing_genotypes(engine)

    distinct_bases = sorted(set(clutch_code_to_basecodes.values()))
    for base in distinct_bases:
        ensure_genotype(engine, base, existing)

    apply_genotypes_to_clutches(engine, clutch_code_to_basecodes, existing)

    with engine.begin() as cx:
        n_clutches, n_with = cx.execute(
            text(
                """
                SELECT count(*) AS n_clutches,
                       count(genotype_v11_id) AS n_with
                FROM public.clutches;
                """
            )
        ).one()
    print(
        f"[v11_seed_legacy_genotypes_from_v9_csv] SUMMARY: clutches={n_clutches}, with genotype_v11_id={n_with}"
    )


if __name__ == "__main__":
    main()
