#!/usr/bin/env python
from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Dict


ROOT = Path(__file__).resolve().parents[1]

UNMAPPED_PATH = ROOT / "seed_kits" / "legacy_import" / "working" / "imaging_unmapped_treatments_with_parents.csv"
CONSTRUCTS_PATH = ROOT / "seed_kits" / "2025-11-15-121231-autoload" / "constructs_plasmid.csv"
OUT_PATH = ROOT / "seed_kits" / "legacy_import" / "working" / "imaging_unmapped_treatments_suggestions_strict.csv"


def _norm(s: str | None) -> str:
    return (s or "").strip()


def load_constructs(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_unmapped(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def main() -> None:
    if not UNMAPPED_PATH.exists():
        raise FileNotFoundError(f"Unmapped treatments CSV not found: {UNMAPPED_PATH}")
    if not CONSTRUCTS_PATH.exists():
        raise FileNotFoundError(f"Constructs CSV not found: {CONSTRUCTS_PATH}")

    constructs = load_constructs(CONSTRUCTS_PATH)
    unmapped = load_unmapped(UNMAPPED_PATH)

    rows_out: List[Dict[str, str]] = []

    for u in unmapped:
        treat_code = _norm(u.get("treat_code"))
        treat_text = _norm(u.get("treat_text"))
        female_parents = _norm(u.get("female_parents"))
        male_parents = _norm(u.get("male_parents"))

        if not treat_code:
            continue

        # For this strict pass: only suggest if plasmid_code appears literally in treat_text
        for c in constructs:
            base = _norm(c.get("plasmid_code"))
            if not base:
                continue
            if base in treat_text:
                rows_out.append(
                    {
                        "treat_code": treat_code,
                        "treat_text": treat_text,
                        "female_parents": female_parents,
                        "male_parents": male_parents,
                        "suggested_plasmid_code": base,
                        "suggested_plasmid_name": _norm(c.get("plasmid_name")),
                    }
                )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "treat_code",
            "treat_text",
            "female_parents",
            "male_parents",
            "suggested_plasmid_code",
            "suggested_plasmid_name",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"[OK] Wrote strict suggestions → {OUT_PATH} ({len(rows_out)} rows)")


if __name__ == "__main__":
    main()
