from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
RAW = ROOT / "raw"
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_TXT = RAW / "foundation_tiff_files_20251223_140835.txt"

OUT_ROIS = WORKING / "roi_paths_from_foundation_v5.csv"
QC_COUNTS = QC / "roi_paths_from_foundation_v5.qc.tsv"
QC_TOP = QC / "roi_paths_from_foundation_v5.qc_top_roi_paths.tsv"
QC_DROPPED = QC / "roi_paths_from_foundation_v5.qc_dropped_nonroi_samples.tsv"

RE_FISH_ROI = re.compile(r"^fish\d+.*roi\d+.*$", re.IGNORECASE)
RE_ROI_SEG = re.compile(r"^roi\d+([_\-].*)?$", re.IGNORECASE)
RE_PREFIX_ROI = re.compile(r"^[A-Za-z]+_roi\d+([_\-].*)?$", re.IGNORECASE)

RE_CH = re.compile(r"(?:^|[\/_\-])ch(\d+)(?:[\/_\-]|$)", re.IGNORECASE)

def _is_tiff(p: str) -> bool:
    s = p.lower()
    return s.endswith(".tif") or s.endswith(".tiff")

def _derive_roi_path_from_tiff_path(path: str) -> tuple[str | None, str]:
    segs = [s for s in path.strip().lstrip("./").split("/") if s]
    if not segs:
        return None, "empty"

    for i, seg in enumerate(segs):
        if RE_FISH_ROI.match(seg):
            return "/".join(segs[:i+1]), "fish_roi_seg"
        if RE_ROI_SEG.match(seg):
            return "/".join(segs[:i+1]), "roi_seg"
        if RE_PREFIX_ROI.match(seg):
            return "/".join(segs[:i+1]), "prefix_roi_seg"

    return None, "no_roi_segment"

def _extract_ch(path: str) -> int | None:
    m = RE_CH.search(path)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None

def main() -> None:
    if not IN_TXT.exists():
        raise SystemExit(f"[STOP] missing input: {IN_TXT}")

    lines = IN_TXT.read_text(encoding="utf-8", errors="replace").splitlines()
    lines = [l.strip().lstrip("./") for l in lines if l.strip()]
    tiffs = [l for l in lines if _is_tiff(l)]

    derived = []
    dropped = []
    reason_counts: dict[str, int] = {}

    for l in tiffs:
        roi_path, reason = _derive_roi_path_from_tiff_path(l)
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if roi_path is None:
            dropped.append({"tiff_path": l, "reason": reason})
        else:
            derived.append({"roi_path": roi_path, "reason": reason, "ch": _extract_ch(l)})

    df = pd.DataFrame(derived)

    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    if df.empty:
        raise SystemExit("[STOP] no derived roi_path rows")

    # per-roi total
    out = (
        df.groupby("roi_path", dropna=False)
        .size()
        .rename("n_tifs")
        .reset_index()
    )

    # per-roi per-channel
    df2 = df.copy()
    df2["ch_label"] = df2["ch"].apply(lambda x: f"ch{int(x)}" if pd.notna(x) else "noch")
    pv = (
        df2.pivot_table(index="roi_path", columns="ch_label", values="reason", aggfunc="size", fill_value=0)
        .reset_index()
    )
    # rename columns to n_tifs_<label>
    rename = {c: f"n_tifs_{c}" for c in pv.columns if c != "roi_path"}
    pv = pv.rename(columns=rename)

    out = out.merge(pv, on="roi_path", how="left").fillna(0)

    # ensure integer dtype for count cols
    for c in out.columns:
        if c.startswith("n_tifs_") or c == "n_tifs":
            out[c] = out[c].astype(int)

    out = out.sort_values("roi_path").reset_index(drop=True)
    out.to_csv(OUT_ROIS, index=False)

    qc_counts = {
        "foundation_lines": len(lines),
        "tiff_lines": len(tiffs),
        "derived_rows": int(len(df)),
        "unique_roi_paths": int(out["roi_path"].nunique()),
        "dropped_tiff_lines": int(len(dropped)),
        "tifs_with_chN": int(df["ch"].notna().sum()),
        "tifs_without_chN": int(df["ch"].isna().sum()),
    }
    for k in sorted(reason_counts):
        qc_counts[f"reason__{k}"] = int(reason_counts[k])

    pd.DataFrame([qc_counts]).to_csv(QC_COUNTS, sep="\t", index=False)

    top = out.sort_values("n_tifs", ascending=False).head(200)[["roi_path", "n_tifs"]].copy()
    top.to_csv(QC_TOP, sep="\t", index=False)

    if dropped:
        pd.DataFrame(dropped).head(200).to_csv(QC_DROPPED, sep="\t", index=False)
    else:
        pd.DataFrame([{"tiff_path": "", "reason": ""}]).head(0).to_csv(QC_DROPPED, sep="\t", index=False)

    print(f"[OK] wrote {OUT_ROIS} rows={len(out)}")
    print(f"[QC] wrote {QC_COUNTS}")
    print(f"[QC] wrote {QC_TOP}")
    print(f"[QC] wrote {QC_DROPPED}")

if __name__ == "__main__":
    main()
