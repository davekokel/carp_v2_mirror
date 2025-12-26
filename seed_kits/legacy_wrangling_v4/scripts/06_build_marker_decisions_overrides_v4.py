from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import csv

OUT = Path("seed_kits/legacy_wrangling_v4/working/marker_decisions_overrides_v4.csv")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_existing(out_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not out_path.exists():
        raise SystemExit(f"[STOP] missing {out_path}")

    with out_path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        fieldnames = list(r.fieldnames or [])
        if not fieldnames:
            raise SystemExit("[STOP] override sheet has no header row (no fieldnames parsed)")

        rows: list[dict[str, str]] = []
        for row in r:
            rows.append({k: ("" if v is None else str(v)) for k, v in row.items()})
        return rows, fieldnames


def _write_all(out_path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    if not fieldnames:
        raise SystemExit("[STOP] cannot write overrides sheet without fieldnames")
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        if rows:
            w.writerows(rows)


def main() -> None:
    rows, fieldnames = _read_existing(OUT)

    required = [
        "sheet_name",
        "row_1based",
        "dataset_key",
        "windows_path",
        "clusterfs_prefix",
        "decision_key",
        "genotype_base_codes",
        "genotype_allele_codes",
        "treatment_plasmid_base_codes",
        "treatment_rna_base_codes",
        "override_kind",
        "override_locked",
        "override_note",
        "proposed_by",
        "proposed_rule",
        "proposed_at_utc",
    ]
    missing = [c for c in required if c not in set(fieldnames)]
    if missing:
        raise SystemExit(f"[STOP] override sheet missing columns: {missing}")

    locked: set[str] = set()
    for r in rows:
        k = (r.get("decision_key") or "").strip()
        locked_flag = (r.get("override_locked") or "").strip().lower() in ("1", "t", "true", "y", "yes")
        if k and locked_flag:
            locked.add(k)

    now = _utc_now()
    additions: list[dict[str, str]] = []

    def add(decision_key: str, dataset_key: str, windows_path: str, clusterfs_prefix: str, rule: str, note: str) -> None:
        if decision_key in locked:
            return
        additions.append(
            {
                "sheet_name": "",
                "row_1based": "",
                "dataset_key": dataset_key,
                "windows_path": windows_path,
                "clusterfs_prefix": clusterfs_prefix,
                "decision_key": decision_key,
                "genotype_base_codes": "",
                "genotype_allele_codes": "",
                "treatment_plasmid_base_codes": "",
                "treatment_rna_base_codes": "",
                "override_kind": "inferred",
                "override_locked": "false",
                "override_note": note,
                "proposed_by": "06_build_marker_decisions_overrides_v4.py",
                "proposed_rule": rule,
                "proposed_at_utc": now,
            }
        )

    # Placeholder: no inference emitted yet.
    # This script currently only preserves locked/manual rows and provides a stable place to append inferred rows.

    if additions:
        rows.extend(additions)
        _write_all(OUT, required, rows)
    else:
        # keep header-only file as-is; do not rewrite unless we add rows
        pass

    print("[OK] override_sheet", str(OUT))
    print("[QC] existing_rows", len(rows))
    print("[QC] locked_keys", len(locked))
    print("[QC] added_rows", len(additions))


if __name__ == "__main__":
    main()
