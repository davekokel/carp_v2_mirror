#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# -----------------------------
# Strict helpers (NO FALLBACKS)
# -----------------------------
_NULLS = {"", "nan", "none", "na", "n/a", "<na>"}


def _norm_cell(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in _NULLS:
        return ""
    return s


_CANON_RE = re.compile(r"^([A-Za-z]+)[-_ ]*0*([0-9]+)$")


def _canon_basecode_strict(tok: str) -> str:
    """
    Strict canonicalization for construct/plasmid basecodes only.

    Examples:
      MGCO01   -> mgco-1
      MGCO-28  -> mgco-28
      pDQM147  -> pdqm-147
      HC-9     -> hc-9
      pswin-1  -> pswin-1

    If it doesn't match the expected basecode pattern, STOP.
    """
    t = _norm_cell(tok)
    if not t:
        raise SystemExit("[STOP] empty basecode token (should not happen)")

    m = _CANON_RE.match(t)
    if not m:
        raise SystemExit(f"[STOP] cannot canonicalize basecode token: {tok!r}")

    prefix = m.group(1).lower()
    num = int(m.group(2))
    return f"{prefix}-{num}"


def _split_basecodes_cell_strict(cell: str) -> List[str]:
    """
    Strictly split a plasmid_base_code cell from the crosswalk sheets.
    Accepts comma/semicolon separators. Every token must canonicalize.
    """
    raw = _norm_cell(cell)
    if not raw:
        return []

    parts = re.split(r"[;,]+", raw)
    out: List[str] = []
    seen: Set[str] = set()
    for p in parts:
        p = _norm_cell(p)
        if not p:
            continue
        canon = _canon_basecode_strict(p)
        if canon not in seen:
            seen.add(canon)
            out.append(canon)

    return out


def _load_crosswalk_strict(path: Path, channel: str) -> Dict[str, List[str]]:
    if not path.exists():
        raise SystemExit(f"[STOP] missing crosswalk xlsx: {path}")

    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]

    if channel == "rna":
        raw_col = "injected_rna"
    elif channel == "plasmid":
        raw_col = "injected_plasmid"
    else:
        raise SystemExit(f"[STOP] invalid channel: {channel!r}")

    need = {raw_col, "plasmid_base_code"}
    missing = sorted(list(need - set(df.columns)))
    if missing:
        raise SystemExit(f"[STOP] {path} missing columns: {missing}")

    mapping: Dict[str, List[str]] = {}
    for _, r in df.iterrows():
        raw_value = _norm_cell(r.get(raw_col))
        if not raw_value:
            continue

        basecodes = _split_basecodes_cell_strict(_norm_cell(r.get("plasmid_base_code")))

        # Strict: if the crosswalk row exists but has no basecodes, keep it as empty,
        # and the builder will STOP if that raw_value appears in the ROI sheet.
        mapping[raw_value] = basecodes

    return mapping


def _resolve_dye_strict(raw: str) -> str:
    """
    Strict dye resolution for legacy imaging sheet.

    The ROI CSV has: "JF 635" (spaces), but dyes.nickname is "JF-635".
    We do NOT infer other dyes; anything else is STOP.
    """
    s = _norm_cell(raw)
    if not s:
        return ""

    s_norm = re.sub(r"\s+", "", s).lower()  # jf635
    if s_norm in {"jf635", "jf-635"}:
        return "JF-635"

    raise SystemExit(f"[STOP] unmapped dye raw value: {raw!r} (expected only JF 635 / JF635 / JF-635)")


def _treat_code_for_signature(sig: str) -> str:
    """
    Deterministic, content-addressed treatment code.
    """
    h = hashlib.sha1(sig.encode("utf-8")).hexdigest()[:8]
    return f"T-LEGACY-{h}"


# -----------------------------
# Main
# -----------------------------
def main() -> None:
    ap = argparse.ArgumentParser(
        description="v10: build legacy treatments_v10.csv from legacy imaging annotations (STRICT crosswalk; no inference)."
    )
    ap.add_argument("--roi-csv", required=True, help="Path to legacy_imaging_annotations_for_db_v9.csv")
    ap.add_argument("--out-csv", required=True, help="Path to write treatments_v10.csv")

    ap.add_argument(
        "--rna-xlsx",
        default=str(ROOT / "seed_kits" / "legacy_wrangling_v2" / "raw" / "Unique_injected_rna__preview_dqm.xlsx"),
        help="Crosswalk: injected_rna -> plasmid_base_code",
    )
    ap.add_argument(
        "--plasmid-xlsx",
        default=str(ROOT / "seed_kits" / "legacy_wrangling_v2" / "raw" / "Unique_injected_plasmid__preview_dqm.xlsx"),
        help="Crosswalk: injected_plasmid -> plasmid_base_code",
    )

    args = ap.parse_args()

    roi_csv = Path(args.roi_csv)
    if not roi_csv.exists():
        raise SystemExit(f"[STOP] ROI CSV not found: {roi_csv}")

    out_csv = Path(args.out_csv)

    # Load ROI CSV (strictly the columns we care about)
    df = pd.read_csv(roi_csv, low_memory=False)
    need_cols = ["additional plasmids injected", "additional mRNAs injected", "additonal dye and chemicals"]
    missing = [c for c in need_cols if c not in df.columns]
    if missing:
        raise SystemExit(f"[STOP] ROI CSV missing required columns: {missing}")

    # Load crosswalks (STRICT: only these decide mapping)
    rna_map = _load_crosswalk_strict(Path(args.rna_xlsx), "rna")
    plasmid_map = _load_crosswalk_strict(Path(args.plasmid_xlsx), "plasmid")

    unmapped_plasmid_counts: Dict[str, int] = {}
    unmapped_rna_counts: Dict[str, int] = {}
    unmapped_dye_counts: Dict[str, int] = {}

    sig_counts: Dict[str, int] = {}

    # Keep a representative mapping of signature -> (plasmids,rnas,dyes) sets
    sig_payload: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]] = {}

    legacy_dye_text_by_token: Dict[str, str] = {}

    for _, row in df.iterrows():
        raw_plasmid = _norm_cell(row.get("additional plasmids injected"))
        raw_rna = _norm_cell(row.get("additional mRNAs injected"))
        raw_dye = _norm_cell(row.get("additonal dye and chemicals"))

        unk_dye_token = ""
        # Special case: ONLY additional_dye_and_chemicals is present.
        # We keep the raw string as the human label, but cannot map it to any basecodes.
        # Make a stable token so treatment_code remains deterministic and unique.
        if raw_dye and (not raw_plasmid) and (not raw_rna):
            h = hashlib.sha1(raw_dye.encode("utf-8")).hexdigest()[:10]
            unk_dye_token = f"legacytext-{h}"


        pls: Set[str] = set()
        rnas: Set[str] = set()
        dyes: Set[str] = set()
        if unk_dye_token:
            dyes.add(unk_dye_token)
            legacy_dye_text_by_token.setdefault(unk_dye_token, raw_dye)


        if raw_plasmid:
            if raw_plasmid not in plasmid_map:
                unmapped_plasmid_counts[raw_plasmid] = unmapped_plasmid_counts.get(raw_plasmid, 0) + 1
                continue  # keep scanning so we can report ALL unmapped values
            bcs = plasmid_map[raw_plasmid]
            if not bcs:
                unmapped_plasmid_counts[raw_plasmid] = unmapped_plasmid_counts.get(raw_plasmid, 0) + 1
                continue
            pls.update(bcs)

        if raw_rna:
            if raw_rna not in rna_map:
                unmapped_rna_counts[raw_rna] = unmapped_rna_counts.get(raw_rna, 0) + 1
                continue
            bcs = rna_map[raw_rna]
            if not bcs:
                unmapped_rna_counts[raw_rna] = unmapped_rna_counts.get(raw_rna, 0) + 1
                continue
            rnas.update(bcs)

        if raw_dye and (not unk_dye_token):
            try:
                dn = _resolve_dye_strict(raw_dye)
            except SystemExit:
                unmapped_dye_counts[raw_dye] = unmapped_dye_counts.get(raw_dye, 0) + 1
                continue
            if dn:
                dyes.add(dn)

        # If nothing injected on this row, ignore it
        if not pls and not rnas and not dyes:
            continue

        sig = f"plasmids={','.join(sorted(pls))}|rnas={','.join(sorted(rnas))}|dyes={','.join(sorted(dyes))}"
        sig_counts[sig] = sig_counts.get(sig, 0) + 1
        if sig not in sig_payload:
            sig_payload[sig] = (tuple(sorted(pls)), tuple(sorted(rnas)), tuple(sorted(dyes)))

    if unmapped_plasmid_counts or unmapped_rna_counts or unmapped_dye_counts:
        print("[STOP] Unmapped injection values detected (must update crosswalks; NO inference):\n")

        if unmapped_plasmid_counts:
            print("[UNMAPPED] plasmid column values:")
            for v, n in sorted(unmapped_plasmid_counts.items(), key=lambda x: (-x[1], x[0])):
                print(f"{n:7d}  {v}")

        if unmapped_rna_counts:
            print("\n[UNMAPPED] rna column values:")
            for v, n in sorted(unmapped_rna_counts.items(), key=lambda x: (-x[1], x[0])):
                print(f"{n:7d}  {v}")

        if unmapped_dye_counts:
            print("\n[UNMAPPED] dye column values:")
            for v, n in sorted(unmapped_dye_counts.items(), key=lambda x: (-x[1], x[0])):
                print(f"{n:7d}  {v}")

        raise SystemExit("[STOP] unmapped injection values")

    if not sig_payload:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            columns=[
                "treatment_code",
                "treatment_name",
                "mix_code",
                "ingredient_type",
                "ingredient_code",
                "concentration",
            ]
        ).to_csv(out_csv, index=False)
        print(f"[OK] wrote 0 row(s) to {out_csv} (no treatment-bearing rows; continuing)")
        return

    # Deterministic ordering
    sigs_sorted = sorted(sig_payload.keys())

    out_rows: List[dict] = []
    for sig in sigs_sorted:
        pls, rnas, dyes = sig_payload[sig]
        tcode = _treat_code_for_signature(sig)
        tname = f"Legacy v9 mix {tcode}"
        if (not pls) and (not rnas) and len(dyes) == 1 and str(dyes[0]).startswith('legacytext-'):
            raw = legacy_dye_text_by_token.get(dyes[0], dyes[0])
            tname = f"Legacy unknown chemical: {raw}"

        mix = "M1"

        for bc in pls:
            out_rows.append(
                {
                    "treatment_code": tcode,
                    "treatment_name": tname,
                    "mix_code": mix,
                    "ingredient_type": "plasmid",
                    "ingredient_code": bc,
                    "concentration": None,
                }
            )

        for bc in rnas:
            out_rows.append(
                {
                    "treatment_code": tcode,
                    "treatment_name": tname,
                    "mix_code": mix,
                    "ingredient_type": "rna",
                    "ingredient_code": bc,
                    "concentration": None,
                }
            )

        for dn in dyes:
            out_rows.append(
                {
                    "treatment_code": tcode,
                    "treatment_name": tname,
                    "mix_code": mix,
                    "ingredient_type": "dye",
                    "ingredient_code": dn,
                    "concentration": None,
                }
            )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(out_rows).to_csv(out_csv, index=False)

    print(f"[OK] wrote {len(out_rows)} row(s) to {out_csv}")
    print(f"[OK] unique signatures: {len(sig_payload)}")
    top = sorted(sig_counts.items(), key=lambda x: (-x[1], x[0]))[:10]
    for sig, n in top:
        print(f"  {n:5d}  {sig}")


if __name__ == "__main__":
    main()
