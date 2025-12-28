from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_ROIS = WORKING / "roi_paths_from_foundation_v5.csv"

OUT = WORKING / "roi_path_slugs_v5.csv"
QC_SUMMARY = QC / "roi_path_slugs_v5.qc.tsv"

RE_DATE = re.compile(r"^(\d{8})[_-]?(.*)$", re.IGNORECASE)
RE_MOUNT = re.compile(r"(?i)(?:^|[_-])mount\s*([0-9]+)\b|(?:^|[_-])mount([0-9]+)\b")
RE_PREFIX_ROI = re.compile(r"(?i)^([a-z]+)_roi(\d+)(?:[_-].*)?$")

def main() -> None:
    if not IN_ROIS.exists():
        raise SystemExit(f"[STOP] missing input: {IN_ROIS}")

    df = pd.read_csv(IN_ROIS)
    if "roi_path" not in df.columns:
        raise SystemExit("[STOP] roi_paths_from_foundation_v5.csv missing roi_path")

    df = df.copy()
    df["roi_path"] = df["roi_path"].astype(str).str.strip().str.strip("/")

    parts = df["roi_path"].str.split("/", expand=True)
    df["foundation_root"] = parts[0].fillna("")
    df["experiment_folder"] = parts[1].fillna("")
    df["roi_slug"] = df["roi_path"].str.split("/").str[-1].fillna("")

    exp_date = []
    exp_slug = []
    mount_slug = []

    for v in df["experiment_folder"].tolist():
        s = str(v)

        m = RE_DATE.match(s)
        if m:
            exp_date.append(m.group(1))
            exp_slug.append(m.group(2))
        else:
            exp_date.append("")
            exp_slug.append(s)

        mm = RE_MOUNT.search(s)
        if mm:
            g = mm.group(1) or mm.group(2)
            mount_slug.append(f"mount{g}" if g else "")
        else:
            mount_slug.append("")

    df["experiment_date"] = exp_date
    df["experiment_slug"] = exp_slug
    df["mount_slug"] = mount_slug

    roi_kind = []
    fish_slug = []
    roi_index = []

    for v in df["roi_slug"].tolist():
        s = str(v)
        m = RE_PREFIX_ROI.match(s)
        if m:
            roi_kind.append(m.group(1).lower())
            roi_index.append(m.group(2))
        else:
            roi_kind.append("")
            roi_index.append("")
        fish_slug.append(s if s.lower().startswith("fish") else "")

    df["roi_kind"] = roi_kind
    df["roi_index"] = roi_index
    df["fish_slug"] = fish_slug

    count_cols = [c for c in df.columns if c.startswith("n_tifs")]
    out_cols = [
        "roi_path",
        "foundation_root",
        "experiment_folder",
        "experiment_date",
        "experiment_slug",
        "mount_slug",
        "roi_slug",
        "roi_kind",
        "roi_index",
        "fish_slug",
    ] + count_cols

    out = df[out_cols].copy()
    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)

    qc = {
        "roi_paths": int(len(out)),
        "unique_experiment_folder": int(out["experiment_folder"].nunique()),
        "unique_experiment_slug": int(out["experiment_slug"].nunique()),
        "roi_with_experiment_date": int((out["experiment_date"].astype(str).str.len() == 8).sum()),
        "roi_with_mount_slug": int((out["mount_slug"].astype(str).str.len() > 0).sum()),
        "roi_with_roi_kind": int((out["roi_kind"].astype(str).str.len() > 0).sum()),
        "roi_with_fish_slug": int((out["fish_slug"].astype(str).str.len() > 0).sum()),
    }
    pd.DataFrame([qc]).to_csv(QC_SUMMARY, sep="\t", index=False)

    print(f"[OK] wrote {OUT} rows={len(out)}")
    print(f"[QC] wrote {QC_SUMMARY}")

if __name__ == "__main__":
    main()
