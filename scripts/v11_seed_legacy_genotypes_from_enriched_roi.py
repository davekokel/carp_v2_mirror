#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import re
from typing import Dict, List, Set, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: str | None) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set (env DB_URL or --db-url)")
    print(f"DB_URL={url}")
    return create_engine(url)


def normalize_basecode(raw: str | None) -> str | None:
    s = (raw or "").strip()
    if not s:
        return None

    m = re.match(r"^([A-Za-z]+)[-_]?(0*)(\d+)$", s)
    if not m:
        return s.lower()

    prefix = m.group(1).lower()
    digits = m.group(3)
    try:
        num = int(digits)
    except ValueError:
        return s.lower()

    return f"{prefix}-{num}"


def load_roi_basecodes(engine: Engine) -> Dict[str, Tuple[str, str]]:
    """
    legacy_clutch_key (ROI) -> (raw_basecodes, normalized_basecodes)
    """
    sql = text(
        """
        SELECT legacy_clutch_key, genotype_base_codes
        FROM raw.legacy_roi_enriched_v9
        WHERE COALESCE(legacy_clutch_key, '') <> ''
          AND COALESCE(genotype_base_codes, '') <> ''
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    mapping: Dict[str, Tuple[str, str]] = {}

    for _, row in df.iterrows():
        key = (row["legacy_clutch_key"] or "").strip()
        raw_codes = (row["genotype_base_codes"] or "").strip()
        if not key or not raw_codes:
            continue

        parts: List[str] = []
        for token in raw_codes.split("|"):
            t = token.strip()
            if not t:
                continue
            parts.append(t)

        norm_tokens: List[str] = []
        for t in parts:
            nt = normalize_basecode(t)
            if nt:
                norm_tokens.append(nt)

        if not norm_tokens:
            continue

        uniq = sorted(set(norm_tokens))
        norm_str = ",".join(uniq)

        if key in mapping:
            prev_raw, prev_norm = mapping[key]
            combined_raw = f"{prev_raw}|{raw_codes}"
            combined_tokens = set(prev_norm.split(",")) | set(norm_str.split(","))
            combined_norm = ",".join(sorted(combined_tokens))
            mapping[key] = (combined_raw, combined_norm)
        else:
            mapping[key] = (raw_codes, norm_str)

    print(f"[v11_seed_legacy_genotypes_from_enriched_roi] legacy_clutch_key with basecodes: {len(mapping)}")
    return mapping


def load_construct_basecodes(engine: Engine) -> Set[str]:
    sql = text(
        """
        SELECT base_code
        FROM public.constructs
        WHERE COALESCE(base_code, '') <> ''
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    basecodes: Set[str] = set()
    for _, row in df.iterrows():
        bc = normalize_basecode(row["base_code"])
        if bc:
            basecodes.add(bc)
    print(f"[v11_seed_legacy_genotypes_from_enriched_roi] normalized construct basecodes: {len(basecodes)}")
    return basecodes


def verify_tokens_against_constructs(
    roi_basecodes: Dict[str, Tuple[str, str]],
    construct_basecodes: Set[str],
) -> None:
    seen_bad: Set[str] = set()
    for _legacy_key, (_raw, norm) in roi_basecodes.items():
        for t in norm.split(","):
            t = t.strip()
            if not t:
                continue
            if t not in construct_basecodes and t not in seen_bad:
                seen_bad.add(t)

    if seen_bad:
        print("[WARN] normalized genotype basecodes not found in constructs.base_code (normalized):")
        for t in sorted(seen_bad):
            print("  -", t)
    else:
        print("[INFO] all normalized genotype basecodes found in constructs.base_code")


def load_legacy_clutch_key_mapping_from_csv(csv_path: str) -> Dict[str, str]:
    """
    Build mapping from legacy_clutch_key (date_born | parent_female | parent_male)
    -> clutch_code (LCL-xxxx) using legacy_clutches_v9_for_loader.csv.
    """
    p = pd.read_csv(csv_path)

    required_cols = {"date_born", "parent_female", "parent_male", "clutch_code"}
    missing = required_cols - set(p.columns)
    if missing:
        raise SystemExit(
            f"legacy_clutches_v9_for_loader.csv missing required columns {missing}; "
            f"columns={list(p.columns)}"
        )

    def _s(x):
        return "" if pd.isna(x) else str(x).strip()

    p["legacy_clutch_key"] = p.apply(
        lambda r: f"{_s(r['date_born'])} | {_s(r['parent_female'])} | {_s(r['parent_male'])}",
        axis=1,
    )

    mapping: Dict[str, str] = {}
    for _, row in p.iterrows():
        key = row["legacy_clutch_key"]
        code = _s(row["clutch_code"])
        if not key or not code:
            continue
        mapping[key] = code

    print(
        f"[v11_seed_legacy_genotypes_from_enriched_roi] "
        f"legacy_clutch_key -> clutch_code from CSV: {len(mapping)}"
    )
    return mapping


def load_clutch_code_to_id(engine: Engine) -> Dict[str, str]:
    """
    clutch_code -> clutch_id::text for legacy_imaging clutches.
    """
    sql = text(
        """
        SELECT id::text AS clutch_id, clutch_code
        FROM public.clutches
        WHERE COALESCE(source_system, '') = 'legacy_imaging'
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    mapping: Dict[str, str] = {}
    for _, row in df.iterrows():
        code = (row["clutch_code"] or "").strip()
        if not code:
            continue
        mapping[code] = row["clutch_id"]
    print(f"[v11_seed_legacy_genotypes_from_enriched_roi] legacy clutches in DB (by clutch_code): {len(mapping)}")
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
        df = pd.read_sql(sql, cx)

    mapping: Dict[str, str] = {}
    for _, row in df.iterrows():
        base = (row["genotype_basecodes"] or "").strip()
        if not base:
            continue
        mapping[base] = row["genotype_id"]
    print(f"[v11_seed_legacy_genotypes_from_enriched_roi] existing genotypes: {len(mapping)}")
    return mapping


def ensure_genotype(
    engine: Engine,
    norm_basecodes: str,
    raw_basecodes: str,
    existing: Dict[str, str],
) -> str:
    base = norm_basecodes.strip()
    if not base:
        raise ValueError("empty norm_basecodes in ensure_genotype")

    if base in existing:
        return existing[base]

    h = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
    genotype_code = f"LEGACY-{h}"
    genotype_pretty = raw_basecodes.strip() or base

    with engine.begin() as cx:
        gid = cx.execute(
            text(
                """
                INSERT INTO public.genotypes_v11 (
                  id,
                  genotype_code,
                  genotype_pretty,
                  genotype_basecodes,
                  created_at,
                  legacy_label,
                  source_system
                )
                VALUES (
                  gen_random_uuid(),
                  :genotype_code,
                  :genotype_pretty,
                  :genotype_basecodes,
                  now(),
                  :legacy_label,
                  'legacy_roi_enriched_v9'
                )
                RETURNING id::text;
                """
            ),
            {
                "genotype_code": genotype_code,
                "genotype_pretty": genotype_pretty,
                "genotype_basecodes": base,
                "legacy_label": raw_basecodes.strip() or base,
            },
        ).scalar()

    existing[base] = gid
    print(f"[v11_seed_legacy_genotypes_from_enriched_roi] created genotype {gid} for basecodes='{base}'")
    return gid


def apply_genotypes_to_clutches(
    engine: Engine,
    roi_basecodes: Dict[str, Tuple[str, str]],
    key_to_code: Dict[str, str],
    code_to_id: Dict[str, str],
    existing_genotypes: Dict[str, str],
) -> None:
    clutch_to_base: Dict[str, Tuple[str, str]] = {}
    unmatched_keys: List[str] = []

    for legacy_key, (raw, norm) in roi_basecodes.items():
        code = key_to_code.get(legacy_key)
        clutch_id = code_to_id.get(code) if code else None
        if not clutch_id:
            unmatched_keys.append(legacy_key)
            continue
        clutch_to_base[clutch_id] = (raw, norm)

    if unmatched_keys:
        print("[WARN] legacy_clutch_key with basecodes but no matching clutch_code/clutch_id:")
        for k in sorted(unmatched_keys)[:10]:
            print("  -", k)
        if len(unmatched_keys) > 10:
            print(f"  ... and {len(unmatched_keys) - 10} more")

    updated = 0

    with engine.begin() as cx:
        for clutch_id, (raw, norm) in clutch_to_base.items():
            gid_before = cx.execute(
                text(
                    """
                    SELECT genotype_v11_id::text
                    FROM public.clutches
                    WHERE id = :cid;
                    """
                ),
                {"cid": clutch_id},
            ).scalar()

            if gid_before:
                continue

            gid = ensure_genotype(engine, norm, raw, existing_genotypes)

            res = cx.execute(
                text(
                    """
                    UPDATE public.clutches
                    SET genotype_v11_id = CAST(:gid AS uuid)
                    WHERE id = :cid
                      AND genotype_v11_id IS NULL;
                    """
                ),
                {"gid": gid, "cid": clutch_id},
            )
            updated += res.rowcount

    print(f"[v11_seed_legacy_genotypes_from_enriched_roi] set genotype_v11_id for {updated} clutch(es)")


def main() -> None:
    db_url = os.environ.get("DB_URL")
    eng = get_engine(db_url)

    roi_basecodes = load_roi_basecodes(eng)
    construct_basecodes = load_construct_basecodes(eng)
    verify_tokens_against_constructs(roi_basecodes, construct_basecodes)

    legacy_csv = "seed_kits/legacy_wrangling_v2/working/legacy_clutches_v9_for_loader.csv"
    key_to_code = load_legacy_clutch_key_mapping_from_csv(legacy_csv)
    code_to_id = load_clutch_code_to_id(eng)
    existing_genotypes = load_existing_genotypes(eng)

    apply_genotypes_to_clutches(eng, roi_basecodes, key_to_code, code_to_id, existing_genotypes)

    with eng.begin() as cx:
        n_clutches, n_with = cx.execute(
            text(
                """
                SELECT count(*) AS n_clutches,
                       count(genotype_v11_id) AS n_with_genotype
                FROM public.clutches
                WHERE source_system = 'legacy_imaging';
                """
            )
        ).one()
    print(
        f"[v11_seed_legacy_genotypes_from_enriched_roi] SUMMARY: legacy clutches={n_clutches}, with genotype_v11_id={n_with}"
    )


if __name__ == "__main__":
    main()
