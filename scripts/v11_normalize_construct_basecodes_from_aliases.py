#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set")
    print(f"DB_URL={url}")
    return create_engine(url)


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


def canonical_from_alias(alias: str) -> Optional[str]:
    """
    Compute a canonical base_code from a construct alias.

    Examples (case-insensitive):
      'pDQM005'   -> 'pdqm-5'
      'pDQM082'   -> 'pdqm-82'
      'pSWIN01'   -> 'pswin-1'
      'MGCO35'    -> 'mgco-35'
      'mgco-35'   -> 'mgco-35'

    Returns None if the alias is not a recognized plasmid/transgene label.
    """
    s = _norm(alias)
    if not s:
        return None
    low = s.lower()

    # pDQM### style
    m = re.match(r"^(pdqm)(?:-)?0*([0-9]+)$", low)
    if m:
        return f"{m.group(1)}-{int(m.group(2))}"

    # pSWIN### / swin### style
    m = re.match(r"^(pswin|swin)(?:-)?0*([0-9]+)$", low)
    if m:
        return f"pswin-{int(m.group(2))}"

    # MGCO### / mgco###
    m = re.match(r"^(mgco)(?:-)?0*([0-9]+)$", low)
    if m:
        return f"{m.group(1)}-{int(m.group(2))}"

    # Already in canonical "prefix-int"
    if re.match(r"^[a-z0-9]+-[0-9]+$", low):
        return low

    return None


def load_constructs_and_aliases(engine: Engine) -> pd.DataFrame:
    with engine.begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT
                  c.id::text       AS construct_id,
                  c.construct_code,
                  c.base_code,
                  c.legacy_base_code,
                  a.alias
                FROM public.constructs c
                LEFT JOIN public.construct_aliases a
                  ON a.construct_id = c.id
                ORDER BY c.construct_code, a.alias
                """
            ),
            cx,
        )
    for c in ["construct_id", "construct_code", "base_code", "legacy_base_code", "alias"]:
        df[c] = df[c].astype("string").fillna("").str.strip()
    return df


def compute_new_basecodes(df: pd.DataFrame) -> Dict[str, str]:
    """
    For each construct_id, look at its aliases.
    If aliases yield exactly one canonical base_code, propose that as the new base_code.
    If zero or >1 distinct canonical codes, skip that construct.
    """
    proposed: Dict[str, str] = {}
    ambiguous: List[Tuple[str, List[str]]] = []
    none_found = 0

    grouped = df.groupby("construct_id", dropna=False)

    for cid, sub in grouped:
        c_code = sub["construct_code"].iloc[0]
        current = sub["base_code"].iloc[0]

        canon_set = set()
        for alias in sub["alias"].tolist():
            canon = canonical_from_alias(alias)
            if canon:
                canon_set.add(canon)

        if not canon_set:
            none_found += 1
            continue

        if len(canon_set) > 1:
            ambiguous.append((cid, sorted(canon_set)))
            continue

        canon = next(iter(canon_set))
        if canon != current:
            proposed[cid] = canon

    print(f"[normalize] constructs with no canonical alias: {none_found}")
    if ambiguous:
        print("[normalize] WARNING: constructs with ambiguous canonical basecodes from aliases (skipped):")
        for cid, codes in ambiguous[:20]:
            print(f"  construct_id={cid} → {', '.join(codes)}")
        if len(ambiguous) > 20:
            print(f"  ... and {len(ambiguous) - 20} more")

    print(f"[normalize] constructs with a single canonical basecode proposal: {len(proposed)}")
    return proposed


def apply_updates(engine: Engine, df: pd.DataFrame, proposed: Dict[str, str]) -> None:
    if not proposed:
        print("[normalize] No base_code changes to apply.")
        return

    # Preview a few changes
    print("[normalize] Sample proposed changes (up to 20):")
    shown = 0
    for cid, new_bc in list(proposed.items())[:20]:
        row = df[df["construct_id"] == cid].iloc[0]
        print(
            f"  construct_code={row['construct_code']} "
            f"legacy_base_code={row['legacy_base_code'] or row['base_code']} "
            f"base_code_old={row['base_code']} → base_code_new={new_bc}"
        )
        shown += 1
    if len(proposed) > shown:
        print(f"  ... and {len(proposed) - shown} more")

    # Apply updates
    with engine.begin() as cx:
        for cid, new_bc in proposed.items():
            cx.execute(
                text(
                    """
                    UPDATE public.constructs
                    SET base_code = :new_bc
                    WHERE id = CAST(:cid AS uuid);
                    """
                ),
                {"new_bc": new_bc, "cid": cid},
            )

    print("[normalize] base_code updates applied.")


def main() -> None:
    eng = get_engine()
    df = load_constructs_and_aliases(eng)
    proposed = compute_new_basecodes(df)
    apply_updates(eng, df, proposed)


if __name__ == "__main__":
    main()
