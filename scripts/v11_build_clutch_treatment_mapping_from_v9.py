from __future__ import annotations

import os
from typing import Dict, List, Set, Tuple

import pandas as pd
import argparse


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


def build_v9_signatures(annotations_csv: str) -> Dict[str, Tuple[str, str]]:
    """
    Build mapping:
        legacy_clutch_key -> (signature, raw_signature_for_debug)

    Signature uses normalized basecodes from:
      - treatment_rna_rna_base_code (if present) or *_from_enrich
      - treatment_plasmid_plasmid_base_code (if present) or *_from_enrich
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
            f"{annotations_csv} must have legacy_clutch_key and one of {rna_candidates}, one of {plasmid_candidates}"
        )

    df = df[["legacy_clutch_key", rna_col, plasmid_col]].copy()

    sig_map: Dict[str, Tuple[str, str]] = {}
    grouped = df.groupby("legacy_clutch_key", dropna=False)
    for key, grp in grouped:
        key_str = str(key or "").strip()
        if not key_str:
            continue

        norm_set: Set[str] = set()
        raw_parts: Set[str] = set()
        for _, row in grp.iterrows():
            rna_raw = str(row[rna_col] or "").strip()
            plasmid_raw = str(row[plasmid_col] or "").strip()
            if rna_raw:
                raw_parts.add(rna_raw)
            if plasmid_raw:
                raw_parts.add(plasmid_raw)
            norm_set.update(_norm_codes(rna_raw))
            norm_set.update(_norm_codes(plasmid_raw))

        if not norm_set:
            continue

        sig_norm = "||".join(sorted(norm_set))
        sig_raw = "||".join(sorted(raw_parts)) if raw_parts else ""
        sig_map[key_str] = (sig_norm, sig_raw)

    return sig_map


def build_v10_signatures(treatments_csv: str) -> Dict[str, Tuple[str, str]]:
    """
    Build mapping:
        signature -> (treatment_code, raw_codes)

    treatments_v10.csv has:
      - treatment_code
      - ingredient_code (one row per ingredient)
    """
    df = pd.read_csv(treatments_csv)

    if "treatment_code" not in df.columns or "ingredient_code" not in df.columns:
        raise RuntimeError("treatments_v10.csv must have 'treatment_code' and 'ingredient_code' columns")

    sig2info: Dict[str, Tuple[str, str]] = {}
    grouped = df.groupby("treatment_code", dropna=False)

    for tcode, grp in grouped:
        tcode_str = str(tcode or "").strip()
        if not tcode_str:
            continue

        norm_set: Set[str] = set()
        raw_codes: Set[str] = set()
        for _, row in grp.iterrows():
            raw = str(row["ingredient_code"] or "").strip()
            if raw:
                raw_codes.add(raw)
            norm = _norm_code_single(raw)
            if norm:
                norm_set.add(norm)

        if not norm_set:
            continue

        sig_norm = "||".join(sorted(norm_set))
        sig_raw = "||".join(sorted(raw_codes)) if raw_codes else ""
        sig2info.setdefault(sig_norm, (tcode_str, sig_raw))

    return sig2info


def load_legacy_clutches(clutches_csv: str) -> Dict[str, str]:
    """
    legacy_clutch_key -> clutch_code from legacy_clutches_v9.csv.
    """
    df = pd.read_csv(clutches_csv)

    key_col = "legacy_clutch_key"
    code_col = "clutch_code"

    required_cols = [key_col, code_col]
    for col in required_cols:
        if col not in df.columns:
            raise RuntimeError(f"{clutches_csv} must have columns {required_cols}")

    mapping: Dict[str, str] = {}
    for _, row in df.iterrows():
        key = str(row[key_col] or "").strip()
        code = str(row[code_col] or "").strip()
        if key and code:
            mapping[key] = code

    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(description="Build clutch↔treatment mapping from v9 ROI annotations")
    parser.add_argument(
        "--roi-csv",
        required=True,
        help="Path to legacy_imaging_annotations_for_db_v9_compat.csv (must include legacy_clutch_key + treatment basecode columns)",
    )
    parser.add_argument(
        "--out-csv",
        required=True,
        help="Where to write clutch_treatment_mapping_v11.csv",
    )
    args = parser.parse_args()

    annotations_csv = args.roi_csv
    clutches_csv = "seed_kits/legacy_wrangling_v2/working/legacy_clutches_v9.csv"
    treatments_csv = "seed_kits/2025-11-15-121231-autoload/treatments_v10.csv"
    out_csv = args.out_csv

    print(f"[INFO] Reading v9 annotations from: {annotations_csv}")
    v9_sig = build_v9_signatures(annotations_csv)
    print(f"[INFO] v9: legacy_clutch_key → signature: {len(v9_sig)} entries")

    print(f"[INFO] Reading v10 treatments from: {treatments_csv}")
    v10_sig = build_v10_signatures(treatments_csv)
    print(f"[INFO] v10: signature → treatment_code: {len(v10_sig)} entries")

    key2clutch = load_legacy_clutches(clutches_csv)
    print(f"[INFO] legacy_clutch_key → clutch_code: {len(key2clutch)} entries")

    rows: List[Dict[str, str]] = []
    for key, (sig_norm, sig_raw_v9) in v9_sig.items():
        clutch_code = key2clutch.get(key, "")
        if not clutch_code:
            continue
        t_info = v10_sig.get(sig_norm)
        if not t_info:
            continue
        treat_code, sig_raw_v10 = t_info
        rows.append(
            {
                "legacy_clutch_key": key,
                "clutch_code": clutch_code,
                "signature_norm": sig_norm,
                "v9_signature_raw": sig_raw_v9,
                "v10_signature_raw": sig_raw_v10,
                "treatment_code": treat_code,
            }
        )

    if not rows:
        print("[WARN] No clutch/treatment pairs inferred; nothing to write.")
        return

    out_df = pd.DataFrame(rows)
    out_df.sort_values(["clutch_code", "treatment_code"], inplace=True)
    out_df.to_csv(out_csv, index=False)
    print(f"[OK] Wrote {len(out_df)} clutch/treatment mapping row(s) to {out_csv}")


if __name__ == "__main__":
    main()
