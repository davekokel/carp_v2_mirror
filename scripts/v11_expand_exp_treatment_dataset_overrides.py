#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]

OVR = REPO / "seed_kits" / "legacy_wrangling_v3" / "working" / "exp_treatment_dataset_overrides.csv"
ROI = REPO / "seed_kits" / "legacy_wrangling_v3" / "working" / "legacy_imaging_annotations_for_db_v9_compat.csv"
OUT = REPO / "seed_kits" / "legacy_wrangling_v3" / "working" / "exp_treatment_manual_overrides.csv"


def main() -> None:
    if not OVR.exists():
        raise SystemExit(f"[STOP] missing {OVR}")
    if not ROI.exists():
        raise SystemExit(f"[STOP] missing {ROI}")

    df_ovr = pd.read_csv(OVR)
    for c in ("dataset_key", "signature"):
        if c not in df_ovr.columns:
            raise SystemExit(f"[STOP] {OVR} missing required column {c!r}; found={list(df_ovr.columns)}")

    df_roi = pd.read_csv(ROI, low_memory=False)
    df_roi.columns = [str(c).strip() for c in df_roi.columns]
    if "roi_dir" not in df_roi.columns or "bruker_roi_id" not in df_roi.columns:
        raise SystemExit(f"[STOP] {ROI} must contain roi_dir + bruker_roi_id; found={list(df_roi.columns)}")

    rows: list[dict[str, str]] = []
    for r in df_ovr.itertuples(index=False):
        dk = str(getattr(r, "dataset_key", "") or "").strip()
        sig = str(getattr(r, "signature", "") or "").strip()
        if not dk or "/" not in dk or not sig:
            continue

        fnd, slug = dk.split("/", 1)
        pat1 = f"/{fnd}/{slug}/"
        pat2 = f"/{fnd}/Denoising/{slug}/"

        sub = df_roi[
            df_roi["roi_dir"].astype(str).str.contains(pat1, na=False)
            | df_roi["roi_dir"].astype(str).str.contains(pat2, na=False)
        ].copy()

        for roi_code in sub["bruker_roi_id"].astype(str).str.strip().tolist():
            if not roi_code or roi_code.lower() == "nan":
                continue
            rows.append({"dataset_key": dk, "bruker_roi_id": roi_code, "signature": sig})

    out = (
        pd.DataFrame(rows)
        .drop_duplicates(keep="last")
        .sort_values(["dataset_key", "bruker_roi_id"])
        .reset_index(drop=True)
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)

    print("WROTE", OUT)
    print("ROWS", len(out))
    print("DATASETS", out["dataset_key"].nunique())


if __name__ == "__main__":
    main()
