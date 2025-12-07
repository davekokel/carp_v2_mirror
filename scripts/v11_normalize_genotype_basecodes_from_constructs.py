#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from typing import Dict, Tuple, List

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set")
    print(f"DB_URL={url}")
    return create_engine(url)


def _norm_code(s: str | None) -> str:
    """
    Normalize construct / basecode strings so that legacy variants collide:

      'pDQM005', 'pdqm005', 'pdqm-5', 'PDQM005' → 'pdqm5'
      'MGCO35', 'mgco-35', 'mgco035'          → 'mgco35'
      'pSWIN01', 'pswin-1'                    → 'pswin1'
    """
    if s is None:
        return ""
    t = str(s).strip().lower()
    t = t.replace(" ", "")

    m = re.match(r"^([a-z]+)[\-\_:]*(\d+)$", t)
    if m:
        prefix = m.group(1)
        num = int(m.group(2))
        return f"{prefix}{num}"

    return t.replace("-", "").replace("_", "")


def build_construct_basecode_map(engine: Engine) -> Dict[str, str]:
    """
    Map any construct_code/base_code variant → canonical base_code
    (exact string from constructs.base_code).
    """
    sql = text(
        """
        SELECT
          construct_code,
          base_code
        FROM public.constructs
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    for c in ["construct_code", "base_code"]:
        df[c] = df[c].astype("string").fillna("").str.strip()

    mapping: Dict[str, str] = {}
    for _, r in df.iterrows():
        base = r["base_code"]
        if not base:
            continue
        base_canon = base
        mapping[_norm_code(base)] = base_canon
        if r["construct_code"]:
            mapping[_norm_code(r["construct_code"])] = base_canon

    print(f"[normalize_genotype_basecodes] construct basecode map entries: {len(mapping)}")
    return mapping


def normalize_basecodes(raw: str | None, basecode_map: Dict[str, str]) -> Tuple[str, bool, List[str]]:
    """
    Normalize a comma-separated basecode list.
    Returns: (normalized_string, changed?, unknown_tokens[])
    """
    if raw is None:
        return "", False, []

    tokens = [t.strip() for t in str(raw).split(",")]
    out: List[str] = []
    changed = False
    unknown: List[str] = []

    for tok in tokens:
        if not tok:
            continue
        key = _norm_code(tok)
        canon = basecode_map.get(key)
        if canon:
            out.append(canon)
            if canon != tok:
                changed = True
        else:
            out.append(tok)
            unknown.append(tok)

    normalized = ",".join(out)
    return normalized, changed, unknown


def main() -> None:
    eng = get_engine()
    basecode_map = build_construct_basecode_map(eng)

    with eng.begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT
                  id::text        AS id,
                  genotype_code,
                  genotype_basecodes
                FROM public.genotypes_v11
                """
            ),
            cx,
        )

    if df.empty:
        print("[normalize_genotype_basecodes] no genotypes_v11 rows; nothing to do.")
        return

    total = len(df)
    n_changed = 0
    unknown_tokens: Dict[str, int] = {}

    updates: List[Tuple[str, str]] = []

    for _, row in df.iterrows():
        gid = row["id"]
        raw = row["genotype_basecodes"]
        new_val, changed, unknown = normalize_basecodes(raw, basecode_map)
        if changed:
            n_changed += 1
            updates.append((gid, new_val))
        for tok in unknown:
            unknown_tokens[tok] = unknown_tokens.get(tok, 0) + 1

    print(f"[normalize_genotype_basecodes] genotypes_v11 rows: {total}")
    print(f"[normalize_genotype_basecodes] rows with changed basecodes: {n_changed}")

    if unknown_tokens:
        print("[normalize_genotype_basecodes] basecodes with no construct match (left as-is):")
        for tok, cnt in sorted(unknown_tokens.items(), key=lambda t: (-t[1], t[0])):
            print(f"  - {tok} (rows={cnt})")

    if not updates:
        print("[normalize_genotype_basecodes] no updates needed.")
        return

    with eng.begin() as cx:
        for gid, basecodes in updates:
            cx.execute(
                text(
                    """
                    UPDATE public.genotypes_v11
                    SET genotype_basecodes = :bc
                    WHERE id = :id;
                    """
                ),
                {"bc": basecodes, "id": gid},
            )

    print("[normalize_genotype_basecodes] updates applied.")


if __name__ == "__main__":
    main()
