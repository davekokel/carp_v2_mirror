#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from collections import Counter
import pandas as pd

NULLISH = {"", "nan", "none", "na", "n/a", "<na>"}

def norm_cell(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    return "" if s.lower() in NULLISH else s

def split_cell(s: str) -> list[str]:
    if not s:
        return []
    for sep in [";", "\n", "\r", "\t"]:
        s = s.replace(sep, ",")
    parts = [p.strip() for p in s.split(",")]
    out = []
    for p in parts:
        if not p:
            continue
        if p.lower() in NULLISH:
            continue
        out.append(p)
    return out

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roi-csv", required=True)
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--plasmid-col", default="additional plasmids injected")
    ap.add_argument("--rna-col", default="additional mRNAs injected")
    args = ap.parse_args()

    roi_path = Path(args.roi_csv)
    if not roi_path.exists():
        raise SystemExit(f"ROI CSV not found: {roi_path}")

    df = pd.read_csv(roi_path, low_memory=False)
    for c in (args.plasmid_col, args.rna_col):
        if c not in df.columns:
            raise SystemExit(f"Missing required column in ROI CSV: {c!r}")

    counts = Counter()

    for c, channel in [(args.plasmid_col, "plasmid"), (args.rna_col, "rna")]:
        s = df[c].map(norm_cell)
        for cell in s.tolist():
            for tok in split_cell(cell):
                counts[(channel, tok)] += 1

    rows = []
    for (channel, raw_value), n in sorted(counts.items(), key=lambda x: (x[0][0], -x[1], x[0][1].lower())):
        rows.append(
            {
                "channel": channel,
                "raw_value": raw_value,
                "n_rows": int(n),
                "mapped_base_code": "",
                "dismiss_reason": "",
                "notes": "",
            }
        )

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"[OK] wrote {out} rows={len(rows)}")

if __name__ == "__main__":
    main()
