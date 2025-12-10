#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.construct_normalizer import normalize_construct_code


def norm(s: str | None) -> str:
    if s is None:
        return ""
    return str(s).strip()


def norm_key(s: str | None) -> str:
    return norm(s).lower()


def norm_optional(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    return s


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def build_construct_lookup(engine: Engine) -> Dict[str, Tuple[str, str]]:
    sql = text(
        """
        SELECT
          c.id::text      AS construct_id,
          c.construct_code,
          c.base_code,
          a.alias
        FROM public.constructs c
        LEFT JOIN public.construct_aliases a
          ON a.construct_id = c.id
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    lookup: Dict[str, Tuple[str, str]] = {}

    for _, row in df.iterrows():
        raw_code = norm(row["construct_code"])
        raw_base = norm(row["base_code"])
        raw_alias = norm(row.get("alias"))

        seed = raw_code or raw_base or raw_alias
        if not seed:
            continue

        canonical = normalize_construct_code(seed)
        if not canonical:
            continue

        cid = norm(row["construct_id"])

        keys = set()

        for raw in (raw_code, raw_base, raw_alias):
            if not raw:
                continue
            s = raw.strip()
            keys.add(s)
            keys.add(s.lower())

        keys.add(canonical)
        keys.add(canonical.lower())

        for k in keys:
            lookup[k] = (cid, canonical)

    print(f"[v10_load_construct_fusions] construct lookup keys: {len(lookup)}")
    return lookup


def build_fluor_lookup(engine: Engine) -> Dict[str, str]:
    """
    v11: build fluor lookup from fluors.nickname/display_name and fluor_aliases.alias.
    Returns mapping from normalized key -> fluor_id (as text).
    """
    sql = text(
        """
        SELECT
          f.id::text   AS fluor_id,
          COALESCE(f.nickname, f.display_name, f.code) AS fluor_label,
          a.alias
        FROM public.fluors f
        LEFT JOIN public.fluor_aliases a
          ON a.fluor_id = f.id
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    lookup: Dict[str, str] = {}
    for _, row in df.iterrows():
        fid = norm(row["fluor_id"])
        label = norm(row["fluor_label"])
        alias = norm(row.get("alias"))

        for raw in (label, alias):
            k = norm_key(raw)
            if not k:
                continue
            lookup[k] = fid

    print(f"[v10_load_construct_fusions] fluor lookup keys: {len(lookup)}")
    return lookup


def build_tag_lookup(engine: Engine) -> Dict[str, str]:
    """
    v11: build tag lookup from tags.nickname/display_name instead of tag_code.
    Returns mapping from normalized key -> tag_id (as text).
    """
    sql = text(
        """
        SELECT
          id::text AS tag_id,
          COALESCE(nickname, display_name, code) AS tag_label
        FROM public.tags
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    lookup: Dict[str, str] = {}
    for _, row in df.iterrows():
        k = norm_key(row["tag_label"])
        if not k:
            continue
        lookup[k] = norm(row["tag_id"])

    print(f"[v10_load_construct_fusions] tag lookup keys: {len(lookup)}")
    return lookup


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v10: load construct_fusions from constructs_plasmid.csv",
    )
    parser.add_argument(
        "--constructs-csv",
        required=True,
        help="Path to constructs_plasmid.csv",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    path = Path(args.constructs_csv)
    if not path.exists():
        raise SystemExit(f"[v10_load_construct_fusions] CSV not found: {path}")

    df = pd.read_csv(path)
    print(f"[v10_load_construct_fusions] read {len(df)} row(s) from {path}")

    required_cols = ["plasmid_code", "fluor_code"]
    for c in required_cols:
        if c not in df.columns:
            raise SystemExit(f"[v10_load_construct_fusions] missing column {c!r} in CSV")

    engine = get_engine(args.db_url)

    construct_lookup = build_construct_lookup(engine)
    fluor_lookup = build_fluor_lookup(engine)
    tag_lookup = build_tag_lookup(engine)

    sql_insert_fusion = text(
        """
        INSERT INTO public.fusions (
          fluor_id,
          tag_id,
          tag_pos,
          created_at
        )
        VALUES (
          :fluor_id,
          :tag_id,
          :tag_pos,
          now()
        )
        ON CONFLICT (fluor_id, tag_id, tag_pos) DO UPDATE SET
          tag_pos = EXCLUDED.tag_pos
        RETURNING id::text AS fusion_id
        """
    )

    sql_find_fusion = text(
        """
        SELECT id::text AS fusion_id
        FROM public.fusions
        WHERE fluor_id = :fluor_id
          AND (
                (tag_id IS NULL AND :tag_id IS NULL)
             OR (tag_id IS NOT NULL AND :tag_id IS NOT NULL AND tag_id = :tag_id)
          )
          AND COALESCE(tag_pos, '') = COALESCE(:tag_pos, '')
        LIMIT 1
        """
    )

    sql_insert_cf = text(
        """
        INSERT INTO public.construct_fusions (
          construct_id,
          fusion_id,
          created_at
        )
        VALUES (
          :construct_id,
          :fusion_id,
          now()
        )
        ON CONFLICT DO NOTHING
        """
    )

    unknown_constructs: set[str] = set()
    unknown_fluors: set[str] = set()
    unknown_tags: set[str] = set()

    inserted_cf = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            plasmid_code_raw = norm(row.get("plasmid_code"))
            fluor_code_raw = norm(row.get("fluor_code"))
            tag_code_raw = norm_optional(row.get("tag_code"))
            tag_pos_raw = norm_optional(row.get("tag_pos"))

            if not plasmid_code_raw:
                continue

            # skip rows where fluor_code is empty or a NaN-ish string
            if not fluor_code_raw or fluor_code_raw.lower() == "nan":
                continue

            canonical = normalize_construct_code(plasmid_code_raw)
            c_match = None
            if canonical:
                c_match = (
                    construct_lookup.get(canonical)
                    or construct_lookup.get(canonical.lower())
                )

            if not c_match:
                c_match = (
                    construct_lookup.get(plasmid_code_raw)
                    or construct_lookup.get(plasmid_code_raw.lower())
                )

            if not c_match:
                if plasmid_code_raw not in unknown_constructs:
                    print(
                        f"[v10_load_construct_fusions] WARN: unknown plasmid_code={plasmid_code_raw!r} (no construct/alias match)"
                    )
                    unknown_constructs.add(plasmid_code_raw)
                continue

            construct_id, canon_code = c_match

            f_key = norm_key(fluor_code_raw)
            fluor_id = fluor_lookup.get(f_key)
            if not fluor_id:
                if fluor_code_raw not in unknown_fluors:
                    print(
                        f"[v10_load_construct_fusions] WARN: unknown fluor_code={fluor_code_raw!r} (no fluors/aliases match)"
                    )
                    unknown_fluors.add(fluor_code_raw)
                continue

            tag_id = None
            if tag_code_raw:
                t_key = norm_key(tag_code_raw)
                tag_id = tag_lookup.get(t_key)
                if not tag_id:
                    # Record the unknown tag and skip this fusion row;
                    # we'll fail at the end if any unknown tags were seen.
                    unknown_tags.add(tag_code_raw)
                    continue

            if tag_id is None:
                tag_pos = None
            else:
                tag_pos = tag_pos_raw

            res = cx.execute(
                sql_find_fusion,
                {"fluor_id": fluor_id, "tag_id": tag_id, "tag_pos": tag_pos},
            ).fetchone()

            if res is not None:
                fusion_id = res._mapping["fusion_id"]
            else:
                res2 = cx.execute(
                    sql_insert_fusion,
                    {"fluor_id": fluor_id, "tag_id": tag_id, "tag_pos": tag_pos},
                ).fetchone()
                fusion_id = res2._mapping["fusion_id"]

            cx.execute(
                sql_insert_cf,
                {"construct_id": construct_id, "fusion_id": fusion_id},
            )
            inserted_cf += 1

    print(f"[v10_load_construct_fusions] linked {inserted_cf} construct_fusions row(s)")
    if unknown_fluors:
        print(
            "[v10_load_construct_fusions] unresolved fluor_code values (after normalization):",
            ", ".join(sorted(unknown_fluors)),
        )
    if unknown_constructs:
        print(
            "[v10_load_construct_fusions] unresolved plasmid_code values:",
            ", ".join(sorted(unknown_constructs)),
        )
    if unknown_tags:
        raise SystemExit(
            "[v10_load_construct_fusions] unknown tag_code(s) in constructs CSV: "
            + ", ".join(sorted(unknown_tags))
            + ". Add these tags to tags.csv (and reload tags) before loading construct fusions."
        )

if __name__ == "__main__":
    main()
