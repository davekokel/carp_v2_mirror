from __future__ import annotations

from pathlib import Path
import argparse
import pandas as pd

import sys
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from seed_kits.legacy_wrangling_v4.scripts._lib_v4.util import (
    ROI_ROOT_RE,
    CLUSTER_PREFIX_DEFAULT,
    dataset_from_foundation,
    iso_from_yyyymmdd,
    fish_from_roi_name,
    clean_str,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
V4_RAW = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "raw"
V4_WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "working"

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--foundation-list", default=str(V4_RAW / "2025-12-22-161855-foundation_dirs_depth6.txt"))
    ap.add_argument("--experiment-roots", default=str(V4_WORK / "2025-12-22-161855-experiment_roots.tsv"))
    ap.add_argument("--roi-channels", default=str(V4_WORK / "2025-12-22-163559-roi_channels_by_roi_root.tsv"))
    ap.add_argument("--cluster-prefix", default=CLUSTER_PREFIX_DEFAULT)
    ap.add_argument("--out", default=str(V4_WORK / "roi_observations.tsv"))
    args = ap.parse_args()

    foundation_list = Path(args.foundation_list)
    exp_roots = Path(args.experiment_roots)
    roi_ch = Path(args.roi_channels)
    out = Path(args.out)

    for p in [foundation_list, exp_roots]:
        if not p.exists():
            raise SystemExit(f"[STOP] missing required input: {p}")

    df_er = pd.read_csv(exp_roots, sep="\t", low_memory=False)
    df_er.columns = [str(c).strip() for c in df_er.columns]
    df_er["experiment_key"] = df_er["experiment_key"].astype(str)
    exp_keys = set(df_er.loc[df_er["is_experiment"].astype(str).str.lower().eq("true"), "experiment_key"].tolist())
    if not exp_keys:
        raise SystemExit("[STOP] experiment_roots.tsv has 0 is_experiment=true rows")

    df_rc_small = None
    if roi_ch.exists():
        df_rc = pd.read_csv(roi_ch, sep="\t", low_memory=False)
        df_rc.columns = [str(c).strip() for c in df_rc.columns]
        df_rc["roi_root"] = df_rc["roi_root"].astype(str).map(lambda s: clean_str(s).lstrip("./"))
        want = ["roi_root", "cams", "channels", "wavelengths_nm", "file_exts", "n_paths"]
        for c in want:
            if c not in df_rc.columns:
                df_rc[c] = pd.NA
        df_rc_small = df_rc[want].copy().rename(columns={"roi_root": "roi_root_rel"})

    rows = []
    with foundation_list.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = clean_str(line).lstrip("./")
            if not s:
                continue
            m = ROI_ROOT_RE.match(s)
            if not m:
                continue
            foundation_long, exp_key, tail = m.group(1), m.group(2), m.group(3)
            if exp_key not in exp_keys:
                continue

            roi_root_rel = f"{foundation_long}/{exp_key}/{tail}"

            base = Path(roi_root_rel).name.lower()
            if not (base.startswith("fish") or "roi" in base):
                continue

            date_key = exp_key[:8]
            rows.append(
                {
                    "roi_root_rel": roi_root_rel,
                    "roi_dir": args.cluster_prefix + roi_root_rel,
                    "foundation_long": foundation_long,
                    "foundation": dataset_from_foundation(foundation_long),
                    "experiment_key": exp_key,
                    "date_key": date_key,
                    "experiment_date": iso_from_yyyymmdd(date_key),
                    "roi_name": Path(roi_root_rel).name,
                    "fish_label": fish_from_roi_name(Path(roi_root_rel).name),
                }
            )

    if not rows:
        raise SystemExit("[STOP] no ROI roots found after filtering; check snapshot inputs")

    df = pd.DataFrame(rows)

    if df_rc_small is not None:
        df = df.merge(df_rc_small, on=["roi_root_rel"], how="left")
    else:
        for c in ["cams", "channels", "wavelengths_nm", "file_exts", "n_paths"]:
            df[c] = pd.NA

    keep_cols = [
        "roi_root_rel",
        "roi_dir",
        "foundation_long",
        "foundation",
        "experiment_key",
        "date_key",
        "experiment_date",
        "roi_name",
        "fish_label",
        "cams",
        "channels",
        "wavelengths_nm",
        "file_exts",
        "n_paths",
    ]
    for c in keep_cols:
        if c not in df.columns:
            df[c] = pd.NA

    out.parent.mkdir(parents=True, exist_ok=True)
    df[keep_cols].sort_values(["foundation_long", "experiment_key", "roi_root_rel"]).to_csv(out, sep="\t", index=False)
    print(f"[OK] wrote {len(df)} roi observations → {out}")

if __name__ == "__main__":
    main()
