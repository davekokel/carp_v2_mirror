#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional, Dict, Set, List

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Defaults
DEFAULT_IN_ROI = "seed_kits/legacy_wrangling_v2/working/legacy_imaging_annotations_for_db_v9.csv"
DEFAULT_OUT    = "seed_kits/2025-11-15-121231-autoload/treatments_v10.csv"


# ────────────────── helpers ──────────────────

def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be provided via --db-url or env DB_URL")
    print(f"DB_URL={url}")
    return create_engine(url)


def norm(s: str | None) -> str:
    if s is None:
        return ""
    return str(s).strip()


def split_codes(val: str | None) -> List[str]:
    if val is None:
        return []
    text = str(val)
    if text.lower().strip() in ("", "nan", "none", "na"):
        return []
    parts: List[str] = []
    for chunk in text.replace(";", ",").split(","):
        c = chunk.strip()
        if not c:
            continue
        parts.append(c)
    return parts


def build_construct_lookup(engine: Engine) -> Dict[str, str]:
    """
    alias -> canonical construct_code

    Uses:
      - constructs.construct_code
      - constructs.base_code
      - construct_aliases.alias
    """
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

    lookup: Dict[str, str] = {}
    for _, row in df.iterrows():
        construct_code = norm(row["construct_code"])
        base_code      = norm(row["base_code"])
        alias          = norm(row.get("alias"))

        canon = construct_code or base_code
        if not canon:
            continue

        keys: Set[str] = set()
        for k in (construct_code, base_code, alias):
            k = norm(k)
            if not k:
                continue
            keys.add(k)
            keys.add(k.lower())

        for k in keys:
            lookup[k] = canon

    print(f"[v10_build_legacy_treatments] construct alias keys: {len(lookup)}")
    return lookup


def build_dye_alias_lookup(engine: Engine) -> Dict[str, str]:
    """
    alias -> canonical dye_base_code

    We treat dye_base_code and name as sources of aliases,
    plus space-stripped / lowercased variants so 'JF 635' and 'jf635'
    both resolve to the same dye.
    """
    sql = text(
        """
        SELECT dye_base_code, name
        FROM public.dyes
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    alias_to_base: Dict[str, str] = {}
    for _, row in df.iterrows():
        base = norm(row["dye_base_code"])
        name = norm(row.get("name"))
        if not base:
            continue

        candidates: Set[str] = set()

        for raw in (base, name):
            r = norm(raw)
            if not r:
                continue
            candidates.add(r)
            candidates.add(r.lower())
            candidates.add(r.replace(" ", ""))
            candidates.add(r.replace(" ", "").lower())

        # also add a JF-style alias without spaces if applicable
        b_lower = base.lower().replace(" ", "")
        if "jf" in b_lower and "635" in b_lower:
            candidates.add("JF635")
            candidates.add("jf635")

        for key in candidates:
            alias_to_base[key] = base

    print(f"[v10_build_legacy_treatments] dye alias keys: {len(alias_to_base)}")
    return alias_to_base


def find_plasmid_col(df: pd.DataFrame) -> Optional[str]:
    if "treatment_plasmid_plasmid_base_code_from_enrich" in df.columns:
        return "treatment_plasmid_plasmid_base_code_from_enrich"
    if "treatment_plasmid_plasmid_base_code" in df.columns:
        return "treatment_plasmid_plasmid_base_code"
    return None


def find_extra_dye_col(df: pd.DataFrame) -> Optional[str]:
    for c in df.columns:
        if c.strip().lower() == "additonal dye and chemicals":
            return c
    return None


# ────────────────── main ──────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="v10: build treatments_v10.csv from legacy v9 imaging annotations."
    )
    parser.add_argument(
        "--roi-csv",
        default=DEFAULT_IN_ROI,
        help=f"Path to legacy_imaging_annotations_for_db_v9.csv (default: {DEFAULT_IN_ROI})",
    )
    parser.add_argument(
        "--out-csv",
        default=DEFAULT_OUT,
        help=f"Path to write treatments_v10.csv (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL for construct/dye lookups",
    )
    args = parser.parse_args()

    roi_path = Path(args.roi_csv)
    if not roi_path.exists():
        raise SystemExit(f"[v10_build_legacy_treatments] ROI CSV not found: {roi_path}")

    print(f"[v10_build_legacy_treatments] reading ROI CSV: {roi_path}")
    df = pd.read_csv(roi_path)

    plasmid_col = find_plasmid_col(df)
    extra_dye_col = find_extra_dye_col(df)

    if plasmid_col is None and extra_dye_col is None:
        print("[v10_build_legacy_treatments] No plasmid or extra dye columns; nothing to build.")
        # Still write an empty treatments_v10.csv with the right header
        empty = pd.DataFrame(
            columns=[
                "treatment_code",
                "treatment_name",
                "kind_code",
                "mix_code",
                "ingredient_type",
                "ingredient_code",
                "concentration",
            ]
        )
        out = Path(args.out_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        empty.to_csv(out, index=False)
        print(f"[v10_build_legacy_treatments] wrote EMPTY treatments CSV to {out}")
        return

    engine           = get_engine(args.db_url)
    construct_lookup = build_construct_lookup(engine)
    dye_aliases      = build_dye_alias_lookup(engine)

    # ── 1) Collect signatures from all ROI rows ──────────────────────────────
    records: list[dict] = []

    for _, row in df.iterrows():
        plasmid_raw = row[plasmid_col] if plasmid_col and plasmid_col in df.columns else None
        extra_raw   = row[extra_dye_col] if extra_dye_col and extra_dye_col in df.columns else None

        plasmid_codes = split_codes(plasmid_raw)
        extra_dyes_v9 = split_codes(extra_raw)

        # ---- construct codes via constructs/aliases ----
        construct_codes: Set[str] = set()
        for bc in plasmid_codes:
            key = norm(bc)
            if not key:
                continue
            canon = construct_lookup.get(key) or construct_lookup.get(key.lower())
            if not canon:
                print(f"[v10_build_legacy_treatments] WARN: unknown construct base_code/alias={bc}")
                continue
            construct_codes.add(canon)

        # ---- dye codes via extra_dyes_v9 + aliases ----
        dye_codes_used: Set[str] = set()
        for raw in extra_dyes_v9:
            k = norm(raw)
            if not k:
                continue
            k_norms = {
                k,
                k.lower(),
                k.replace(" ", ""),
                k.replace(" ", "").lower(),
            }
            base = None
            for kk in k_norms:
                if kk in dye_aliases:
                    base = dye_aliases[kk]
                    break
            if base is None:
                print(f"[v10_build_legacy_treatments] WARN: unknown dye_base_code={k}")
                continue
            dye_codes_used.add(base)

        if not construct_codes and not dye_codes_used:
            continue

        construct_sig = ",".join(sorted(construct_codes)) if construct_codes else ""
        dye_sig       = ",".join(sorted(dye_codes_used)) if dye_codes_used else ""
        sig           = f"constructs={construct_sig}|dyes={dye_sig}"

        records.append(
            {
                "signature": sig,
                "construct_codes": sorted(construct_codes),
                "dye_codes": sorted(dye_codes_used),
            }
        )

    if not records:
        print("[v10_build_legacy_treatments] No rows with treatment constructs/dyes; writing header-only CSV.")
        df_out = pd.DataFrame(
            columns=[
                "treatment_code",
                "treatment_name",
                "kind_code",
                "mix_code",
                "ingredient_type",
                "ingredient_code",
                "concentration",
            ]
        )
        out = Path(args.out_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        df_out.to_csv(out, index=False)
        print(f"[v10_build_legacy_treatments] wrote EMPTY treatments CSV to {out}")
        return

    df_sig = (
        pd.DataFrame(records)
        .drop_duplicates(subset=["signature"])
        .reset_index(drop=True)
    )
    print(f"[v10_build_legacy_treatments] unique treatment signatures: {len(df_sig)}")

    # ── 2) Expand to treatments_v10.csv ──────────────────────────────────────
    rows_out: list[dict] = []
    for i, row in df_sig.iterrows():
        constructs: List[str] = row["construct_codes"]
        dyes: List[str]       = row["dye_codes"]

        treat_code = f"T-LEGACY-{i+1:03d}"
        treat_name = f"Legacy v9 mix {i+1}"
        kind_code  = "injection"
        mix_code   = "M1"

        # constructs
        for c_code in constructs:
            rows_out.append(
                {
                    "treatment_code": treat_code,
                    "treatment_name": treat_name,
                    "kind_code": kind_code,
                    "mix_code": mix_code,
                    "ingredient_type": "construct",
                    "ingredient_code": c_code,
                    "concentration": None,
                }
            )

        # dyes
        for d_code in dyes:
            rows_out.append(
                {
                    "treatment_code": treat_code,
                    "treatment_name": treat_name,
                    "kind_code": kind_code,
                    "mix_code": mix_code,
                    "ingredient_type": "dye",
                    "ingredient_code": d_code,
                    "concentration": None,
                }
            )

    df_out = pd.DataFrame(rows_out)
    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(out, index=False)
    print(f"[v10_build_legacy_treatments] wrote {len(df_out)} row(s) to {out}")


if __name__ == "__main__":
    main()
