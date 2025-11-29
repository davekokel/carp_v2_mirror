from __future__ import annotations

import os
from typing import Dict, List, Set

import pandas as pd


def _norm_code_single(raw: object) -> str | None:
    """
    Normalize a single construct code like 'MGCO-004', 'MGCO-04', 'MGCO-4' to 'MGCO#4'.
    """
    s = str(raw or "").strip()
    if not s:
        return None
    s_up = s.upper()
    parts = s_up.split("-")
    if len(parts) < 2:
        return None
    prefix = "-".join(parts[:-1])
    num_str = parts[-1]
    try:
        num = int(num_str)
    except ValueError:
        return None
    return f"{prefix}#{num}"


def _norm_codes(raw: object) -> List[str]:
    """
    Normalize a cell of base codes into a sorted, unique list of canonical codes.
    Handles '|' and '+' separators.
    """
    s = str(raw or "").strip()
    if not s:
        return []
    tokens: List[str] = []
    for chunk in s.replace("|", "+").split("+"):
        code = chunk.strip()
        if not code:
            continue
        norm = _norm_code_single(code)
        if norm:
            tokens.append(norm)
    return sorted(set(tokens))


def signatures_from_v9(annotations_csv: str) -> Dict[str, str]:
    """
    legacy_clutch_key -> signature from v9 annotations.

    We prefer treatment_*_base_code (if present), otherwise *_from_enrich.
    """
    df = pd.read_csv(annotations_csv)

    rna_candidates = [
        "treatment_rna_rna_base_code",
        "treatment_rna_rna_base_code_from_enrich",
    ]
    plasmid_candidates = [
        "treatment_plasmid_plasmid_base_code",
        "treatment_plasmid_plasmid_base_code_from_enrich",
    ]

    rna_col = next((c for c in rna_candidates if c in df.columns), None)
    plasmid_col = next((c for c in plasmid_candidates if c in df.columns), None)

    if rna_col is None or plasmid_col is None or "legacy_clutch_key" not in df.columns:
        raise RuntimeError(
            f"v9 CSV must have legacy_clutch_key and one of {rna_candidates}, one of {plasmid_candidates}"
        )

    df = df[["legacy_clutch_key", rna_col, plasmid_col]].copy()

    sig_map: Dict[str, str] = {}
    grouped = df.groupby("legacy_clutch_key", dropna=False)
    for key, grp in grouped:
        key_str = str(key or "").strip()
        if not key_str:
            continue

        norm_set: Set[str] = set()
        for _, row in grp.iterrows():
            norm_set.update(_norm_codes(row[rna_col]))
            norm_set.update(_norm_codes(row[plasmid_col]))

        if not norm_set:
            continue

        sig = "||".join(sorted(norm_set))
        sig_map[key_str] = sig

    return sig_map


def signatures_from_v10(treatments_csv: str) -> Dict[str, str]:
    """
    signature -> treatment_code from treatments_v10.csv.

    treatments_v10.csv has treatment_code + ingredient_code (one row per ingredient).
    """
    df = pd.read_csv(treatments_csv)

    if "treatment_code" not in df.columns or "ingredient_code" not in df.columns:
        raise RuntimeError("treatments_v10.csv must have 'treatment_code' and 'ingredient_code' columns")

    sig2code: Dict[str, str] = {}
    grouped = df.groupby("treatment_code", dropna=False)

    for tcode, grp in grouped:
        tcode_str = str(tcode or "").strip()
        if not tcode_str:
            continue

        norm_set: Set[str] = set()
        for _, row in grp.iterrows():
            norm = _norm_code_single(row["ingredient_code"])
            if norm:
                norm_set.add(norm)

        if not norm_set:
            continue

        sig = "||".join(sorted(norm_set))
        sig2code.setdefault(sig, tcode_str)

    return sig2code


def main() -> None:
    annotations_csv = "seed_kits/legacy_wrangling_v2/working/legacy_imaging_annotations_for_db_v9.csv"
    treatments_csv = "seed_kits/2025-11-15-121231-autoload/treatments_v10.csv"

    print(f"[INFO] Reading v9 annotations from: {annotations_csv}")
    sig_v9 = signatures_from_v9(annotations_csv)
    print(f"[INFO] v9: legacy_clutch_key → signature: {len(sig_v9)} entries")

    print(f"[INFO] Reading v10 treatments from: {treatments_csv}")
    sig_v10 = signatures_from_v10(treatments_csv)
    print(f"[INFO] v10: signature → treatment_code: {len(sig_v10)} entries")

    # Collect sets for comparison
    set_v9 = set(sig_v9.values())
    set_v10 = set(sig_v10.keys())
    inter = set_v9 & set_v10

    print(f"[INFO] Distinct v9 signatures:  {len(set_v9)}")
    print(f"[INFO] Distinct v10 signatures: {len(set_v10)}")
    print(f"[INFO] Intersection size:       {len(inter)}")

    # Show some examples
    print("\n[DEBUG] Sample v9 signatures:")
    for i, (k, s) in enumerate(sig_v9.items()):
        if i >= 10:
            break
        print(f"  v9[{k}] = {s}")

    print("\n[DEBUG] Sample v10 signatures:")
    for i, (s, tcode) in enumerate(sig_v10.items()):
        if i >= 10:
            break
        print(f"  v10[{s}] -> {tcode}")

    if inter:
        print("\n[DEBUG] Sample intersection signatures:")
        for i, s in enumerate(sorted(inter)):
            if i >= 10:
                break
            print(f"  sig={s} v9_count={list(set_v9).count(s)} v10_code={sig_v10.get(s)}")
    else:
        print("\n[WARN] No overlapping signatures between v9 and v10.")


if __name__ == "__main__":
    main()
