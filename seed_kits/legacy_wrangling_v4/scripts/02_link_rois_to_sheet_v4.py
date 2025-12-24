from __future__ import annotations
import re

def _norm_payload_val(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    s = re.sub(r"\s+", " ", s)
    return s

def _payload_key(row: dict) -> tuple:
    keys = [
        "zf_female_genotype",
        "zf_male_genotype",
        "additional_plasmids_injected",
        "additional_mrnas_injected",
        "additional_proteins_injected",
        "additional_dye_and_chemicals",
    ]
    return tuple(_norm_payload_val(row.get(k)) for k in keys)

def _parse_int(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return None
    s2 = re.sub(r"[^0-9]+", "", s)
    if not s2:
        return None
    try:
        return int(s2)
    except Exception:
        return None

def _equiv_mount_pick(cand_df):
    if cand_df is None or len(cand_df) == 0:
        return None, ""
    rows = cand_df.to_dict(orient="records")
    keys = [_payload_key(r) for r in rows]
    if len(set(keys)) != 1:
        return None, ""

    def sort_key(r):
        mi = _parse_int(r.get("mount_id"))
        sid = _parse_int(r.get("sheet_row_id"))
        return (mi if mi is not None else 10**9, sid if sid is not None else 10**9, str(r.get("sheet_row_id") or ""))

    rows_sorted = sorted(rows, key=sort_key)
    chosen = rows_sorted[0]
    equiv = [str(r.get("mount_id") or "").strip() for r in rows_sorted if str(r.get("mount_id") or "").strip()]
    return chosen, ";".join(equiv)


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

        # Candidate imaging-sheet rows for this ROI.
        # Order:
        #  1) experiment_key_guess == exp_key (if exp_key present)
        #  2) fallback to date_mount (derived from ROI) if empty
        #  3) fallback to exp_date if still empty
        #  4) foundation filter ONLY if candidates have nonblank foundation_guess values
        
        cand = sheet
        if exp_key:
            cand = cand[cand['experiment_key_guess'].eq(exp_key)]
        
        # derive date_mount (YYYY-MM-DD) from ROI row
        date_mount = None
        try:
            v = getattr(r, 'experiment_date', None)
            if v is not None:
                s = str(v).strip()
                if s and s.lower() not in ('nan','none','na','n/a','<na>'):
                    date_mount = s[:10]
        except Exception:
            date_mount = None
        if not date_mount:
            try:
                dk = getattr(r, 'date_key', None)
                s2 = str(dk).strip()
                if len(s2) == 8 and s2.isdigit():
                    date_mount = s2[0:4] + '-' + s2[4:6] + '-' + s2[6:8]
            except Exception:
                date_mount = None
        
        if getattr(cand, 'empty', True) and date_mount:
            cand = sheet[sheet['date_mount'].astype(str).str.strip().eq(str(date_mount))].copy()
        if len(cand) == 0:
            cand = sheet[sheet['date_mount'].eq(exp_date)]
        
        # Only apply fd filter if it won't erase genotype-only rows (foundation_guess blank).
        if fd and len(cand):
            fg = cand.get('foundation_guess', None)
            if fg is not None:
                fg_nonblank = fg.astype(str).str.strip().ne('')
                if bool(fg_nonblank.any()):
                    cand = cand[fg.astype(str).str.strip().eq(fd)]
        
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
            # If multiple candidates are biologically identical, pick deterministically (lowest mount_id).
            chosen, equiv = _equiv_mount_pick(cand)
            if chosen is not None:
                sid = int(chosen.get("sheet_row_id"))
                links.append(
                    {
                        "roi_root_rel": getattr(r, "roi_root_rel"),
                        "sheet_row_id": sid,
                        "link_method": "imaging_sheet_equivalent_mounts",
                        "link_score": 0.99,
                        "n_candidates": n,
                        "is_ambiguous": False,
                        "link_notes": ("equiv_mount_ids=" + equiv) if equiv else "equiv_mounts",
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
