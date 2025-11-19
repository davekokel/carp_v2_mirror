#!/usr/bin/env python
from __future__ import annotations

import re
import csv
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]

UNMAPPED_PATH = ROOT / "seed_kits" / "legacy_import" / "working" / "imaging_unmapped_treatments_with_parents.csv"
CONSTRUCTS_PATH = ROOT / "seed_kits" / "2025-11-15-121231-autoload" / "constructs_plasmid.csv"
OUT_PATH = ROOT / "seed_kits" / "legacy_import" / "working" / "imaging_unmapped_treatments_with_parents_annotated.csv"


def _norm(s: str | None) -> str:
    return (s or "").strip()


def tokenize(text: str) -> List[str]:
    """
    Tokenize a treatment text or parent genotype string into candidate marker/protein tokens.
    Very simple splitter: split on space, /, ;, +, (), :, ',', '='
    """
    if not text:
        return []
    raw = re.split(r"[ \t;/\+\(\):,=]+", text)
    toks: List[str] = []
    for t in raw:
        t = t.strip()
        if not t:
            continue
        # skip numeric-only tokens and pg/units
        if re.fullmatch(r"[0-9\.]+", t):
            continue
        if t.lower() in {"pg", "ng", "um", "µm", "rna", "mrna"}:
            continue
        toks.append(t)
    return toks


def build_construct_index(constructs_csv: Path) -> Dict[str, List[str]]:
    """
    Build a mapping token -> list of plasmid_codes, based on constructs_plasmid.csv.
    Tokens come from plasmid_name, plasmid_nickname, fluor_code, tag_code.
    """
    index: Dict[str, List[str]] = {}
    with constructs_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=",")
        for row in reader:
            base = _norm(row.get("plasmid_code"))
            if not base:
                continue
            fields = [
                row.get("plasmid_name"),
                row.get("plasmid_nickname"),
                row.get("fluor_code"),
                row.get("tag_code"),
            ]
            tokens: List[str] = []
            for field in fields:
                tokens.extend(tokenize(_norm(field)))
            for tok in set(tokens):
                key = tok.lower()
                index.setdefault(key, [])
                if base not in index[key]:
                    index[key].append(base)
    return index


def guess_basecodes_for_row(row: Dict[str, str], construct_index: Dict[str, List[str]]) -> str:
    """
    For a single unmapped treatment row, use treat_text and parent genotype text
    to suggest plasmid_codes.
    """
    treat_text = _norm(row.get("treat_text"))
    female_parents = _norm(row.get("female_parents"))
    male_parents = _norm(row.get("male_parents"))

    toks: List[str] = []
    toks.extend(tokenize(treat_text))
    toks.extend(tokenize(female_parents))
    toks.extend(tokenize(male_parents))

    suggestions: List[str] = []
    for tok in toks:
        key = tok.lower()
        if key in construct_index:
            for base in construct_index[key]:
                if base not in suggestions:
                    suggestions.append(base)

    return ",".join(suggestions)


def main() -> None:
    if not UNMAPPED_PATH.exists():
        raise FileNotFoundError(f"Unmapped treatments CSV not found: {UNMAPPED_PATH}")
    if not CONSTRUCTS_PATH.exists():
        raise FileNotFoundError(f"Constructs CSV not found: {CONSTRUCTS_PATH}")

    # Build construct index
    construct_index = build_construct_index(CONSTRUCTS_PATH)

    # Load unmapped treatments + parents
    with UNMAPPED_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    # Ensure auto_suggested_base_codes column
    if "auto_suggested_base_codes" not in fieldnames:
        fieldnames = list(fieldnames) + ["auto_suggested_base_codes"]

    # Annotate rows
    for row in rows:
        codes = guess_basecodes_for_row(row, construct_index)
        row["auto_suggested_base_codes"] = codes

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Wrote annotated unmapped treatments → {OUT_PATH}")


if __name__ == "__main__":
    main()
