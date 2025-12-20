from __future__ import annotations

import argparse
import os
from typing import Dict, List, Set, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

DB_URL = os.getenv("DB_URL")


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


def build_clutch_signatures_from_v9(annotations_csv: str) -> Dict[str, str]:
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


def build_treatment_signatures_from_v10(treatments_csv: str) -> Dict[str, str]:
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


def load_legacy_clutches(clutches_csv: str) -> Dict[str, str]:
    """
    legacy_clutch_key -> clutch_code from legacy_clutches_v9.csv
    (or ..._v9_for_loader.csv).
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
    parser = argparse.ArgumentParser(
        description="Link legacy clutches to treatments via join_clutch_treatments using v9 annotations + treatments_v10.csv"
    )
    parser.add_argument(
        "--annotations-csv",
        required=True,
        help="legacy_imaging_annotations_for_db_v9.csv",
    )
    parser.add_argument(
        "--clutches-csv",
        required=True,
        help="legacy_clutches_v9.csv or legacy_clutches_v9_for_loader.csv (must contain legacy_clutch_key + clutch_code)",
    )
    parser.add_argument(
        "--treatments-csv",
        required=True,
        help="treatments_v10.csv (must contain treatment_code + ingredient_code)",
    )
    args = parser.parse_args()

    if not DB_URL:
        raise RuntimeError("DB_URL is not set in the environment")

    # 1) legacy_clutch_key -> signature from v9 annotations
    clutch_sig = build_clutch_signatures_from_v9(args.annotations_csv)
    print(f"[INFO] v9: legacy_clutch_key → signature: {len(clutch_sig)} entries")

    # 2) signature -> treatment_code from v10 treatments
    sig2code = build_treatment_signatures_from_v10(args.treatments_csv)
    print(f"[INFO] v10: signature → treatment_code: {len(sig2code)} entries")

    # 3) legacy_clutch_key -> clutch_code
    key2clutch = load_legacy_clutches(args.clutches_csv)
    print(f"[INFO] legacy_clutch_key → clutch_code: {len(key2clutch)} entries")

    # 4) build clutch_code -> treatment_code pairs
    pairs: List[Tuple[str, str]] = []
    missing_sig = 0

    for key, sig in clutch_sig.items():
        clutch_code = key2clutch.get(key)
        if not clutch_code:
            continue
        treat_code = sig2code.get(sig)
        if not treat_code:
            missing_sig += 1
            continue
        pairs.append((clutch_code, treat_code))

    seen = set()
    uniq_pairs: List[Tuple[str, str]] = []
    for clutch_code, treat_code in pairs:
        k = (clutch_code, treat_code)
        if k not in seen:
            seen.add(k)
            uniq_pairs.append(k)

    print(f"[INFO] {len(uniq_pairs)} clutch_code/treatment_code pair(s) inferred")
    if uniq_pairs:
        print("[DEBUG] Sample inferred pairs:")
        for i, (cc, tc) in enumerate(uniq_pairs):
            if i >= 10:
                break
            print(f"  {cc} -> {tc}")
    print(f"[INFO] {missing_sig} legacy clutches had signatures with no matching treatment")

    if not uniq_pairs:
        print("[WARN] No pairs inferred; nothing to link.")
        return

    engine = create_engine(DB_URL)

    clutch_codes = sorted({c for c, _ in uniq_pairs})
    treat_codes = sorted({t for _, t in uniq_pairs})

    with engine.begin() as cx:
        clutch_df = pd.read_sql(
            text("""
              SELECT clutch_code, id::text AS clutch_id
              FROM public.clutches
              WHERE clutch_code = ANY(:codes)
            """),
            cx,
            params={"codes": clutch_codes},
        )
        clutch_map = dict(zip(clutch_df["clutch_code"], clutch_df["clutch_id"]))

        treat_df = pd.read_sql(
            text("""
              SELECT treat_code, id::text AS treatment_id
              FROM public.treatments
              WHERE treat_code = ANY(:codes)
            """),
            cx,
            params={"codes": treat_codes},
        )
        treat_map = dict(zip(treat_df["treat_code"], treat_df["treatment_id"]))

        inserted = 0
        skipped_existing = 0
        missing_clutch = 0
        missing_treat = 0

        for clutch_code, treat_code in uniq_pairs:
            cid = clutch_map.get(clutch_code)
            if not cid:
                missing_clutch += 1
                print(f"[WARN] clutch_code '{clutch_code}' not found in public.clutches; skipping")
                continue
            tid = treat_map.get(treat_code)
            if not tid:
                missing_treat += 1
                print(f"[WARN] treat_code '{treat_code}' not found in public.treatments; skipping")
                continue

            exists_df = pd.read_sql(
                text("""
                  SELECT 1
                  FROM public.join_clutch_treatments
                  WHERE clutch_id = CAST(:cid AS uuid)
                    AND treatment_id = CAST(:tid AS uuid)
                  LIMIT 1
                """),
                cx,
                params={"cid": cid, "tid": tid},
            )
            if not exists_df.empty:
                skipped_existing += 1
                continue

            cx.execute(
                text("""
                  INSERT INTO public.join_clutch_treatments
                    (id, clutch_id, treatment_id, applied_at, created_at, notes)
                  VALUES
                    (gen_random_uuid(),
                     CAST(:cid AS uuid),
                     CAST(:tid AS uuid),
                     now(),
                     now(),
                     'legacy_v9/v10_inferred')
                """),
                {"cid": cid, "tid": tid},
            )
            inserted += 1

    print(f"[OK] Inserted {inserted} join_clutch_treatments row(s).")
    print(f"[INFO] Existing links skipped: {skipped_existing}")
    print(f"[INFO] Missing clutch_code:   {missing_clutch}")
    print(f"[INFO] Missing treat_code:    {missing_treat}")
    print(f"[INFO] Missing treatment signatures: {missing_sig}")
    
if __name__ == "__main__":
    main()