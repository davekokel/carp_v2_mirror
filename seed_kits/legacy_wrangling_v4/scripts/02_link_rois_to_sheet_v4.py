from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


import sys
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from seed_kits.legacy_wrangling_v4.scripts._lib_v4.util import clean_str

REPO_ROOT = Path(__file__).resolve().parents[3]
V4_WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "working"

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roi-observations", default=str(V4_WORK / "roi_observations.tsv"))
    ap.add_argument("--sheet-normalized", default=str(V4_WORK / "imaging_sheet_normalized.tsv"))
    ap.add_argument("--out", default=str(V4_WORK / "roi_sheet_links.tsv"))
    args = ap.parse_args()

    p_roi = Path(args.roi_observations)
    p_sheet = Path(args.sheet_normalized)
    out = Path(args.out)

    for p in [p_roi, p_sheet]:
        if not p.exists():
            raise SystemExit(f"[STOP] missing required input: {p}")

    rois = pd.read_csv(p_roi, sep="\t", low_memory=False)
    sheet = pd.read_csv(p_sheet, sep="\t", low_memory=False)

    rois.columns = [str(c).strip() for c in rois.columns]
    sheet.columns = [str(c).strip() for c in sheet.columns]

    rois["experiment_key"] = rois["experiment_key"].astype(str).map(clean_str)
    rois["foundation"] = rois["foundation"].astype(str).map(clean_str)
    rois["experiment_date"] = rois["experiment_date"].astype(str).map(clean_str)

    sheet["foundation_guess"] = sheet.get("foundation_guess", "").astype(str).map(clean_str)
    sheet["experiment_key_guess"] = sheet.get("experiment_key_guess", "").astype(str).map(clean_str)
    sheet["date_mount"] = sheet.get("date_mount", "").astype(str).map(clean_str)

    links = []
    for r in rois.itertuples(index=False):
        exp_key = getattr(r, "experiment_key")
        fd = getattr(r, "foundation")
        exp_date = getattr(r, "experiment_date")

        cand = sheet
        if exp_key:
            cand = cand[cand["experiment_key_guess"].eq(exp_key)]
        if len(cand) == 0:
            cand = sheet[sheet["date_mount"].eq(exp_date)]
        if fd:
            cand = cand[cand["foundation_guess"].eq(fd)] if len(cand) else cand

        n = int(len(cand))
        if n == 1:
            sid = int(cand.iloc[0]["sheet_row_id"])
            links.append(
                {
                    "roi_root_rel": getattr(r, "roi_root_rel"),
                    "sheet_row_id": sid,
                    "link_method": "experiment_key_guess" if exp_key and sheet[sheet["experiment_key_guess"].eq(exp_key)].shape[0] == 1 else "date_mount_only",
                    "link_score": 1.0,
                    "n_candidates": 1,
                    "is_ambiguous": False,
                    "link_notes": "",
                }
            )
        else:
            links.append(
                {
                    "roi_root_rel": getattr(r, "roi_root_rel"),
                    "sheet_row_id": pd.NA,
                    "link_method": "unlinked" if n == 0 else "ambiguous",
                    "link_score": 0.0,
                    "n_candidates": n,
                    "is_ambiguous": bool(n > 1),
                    "link_notes": "",
                }
            )

    out_df = pd.DataFrame(links)
    out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out, sep="\t", index=False)
    print(f"[OK] wrote {len(out_df)} links → {out}")
    print(f"[QC] linked_exactly_one={int(out_df['sheet_row_id'].notna().sum())} ambiguous={int(out_df['is_ambiguous'].fillna(False).sum())} unlinked={int(out_df['sheet_row_id'].isna().sum())}")

if __name__ == "__main__":
    main()
