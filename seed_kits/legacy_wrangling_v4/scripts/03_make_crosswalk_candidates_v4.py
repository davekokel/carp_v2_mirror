from __future__ import annotations

from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
V4_WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "working"
V4_SCRIPTS = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "scripts"

ROI_OBS = V4_WORK / "roi_observations.tsv"
SHEET = V4_WORK / "imaging_sheet_normalized.tsv"

OUT_CAND = V4_WORK / "crosswalk_candidates.tsv"
OUT_TEMPLATE = V4_WORK / "crosswalk_manual.tsv"


def clean(x) -> str:
    if x is None:
        return ""
    s = str(x).replace("¬†", " ").replace("\u00a0", " ").strip()
    s = " ".join(s.split())
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s


def main() -> None:
    for p in [ROI_OBS, SHEET]:
        if not p.exists():
            raise SystemExit(f"[STOP] missing required input: {p}")

    rois = pd.read_csv(ROI_OBS, sep="\t", low_memory=False)
    rois.columns = [str(c).strip() for c in rois.columns]
    for c in ["foundation", "experiment_key", "experiment_date", "roi_dir", "roi_root_rel"]:
        if c not in rois.columns:
            rois[c] = ""

    rois["foundation"] = rois["foundation"].map(clean)
    rois["experiment_key"] = rois["experiment_key"].map(clean)
    rois["experiment_date"] = rois["experiment_date"].map(clean)
    rois["roi_dir"] = rois["roi_dir"].map(clean)
    rois["roi_root_rel"] = rois["roi_root_rel"].map(clean)

    sheet = pd.read_csv(SHEET, sep="\t", low_memory=False)
    sheet.columns = [str(c).strip() for c in sheet.columns]

    for c in [
        "date_mount",
        "mount_id",
        "ZF female genotype",
        "ZF male genotype",
        "additional plasmids injected",
        "additional mRNAs injected",
        "additonal dye and chemicals",
        "comments",
        "Data evaluation comments",
        "foundation_guess",
        "experiment_key_guess",
    ]:
        if c not in sheet.columns:
            sheet[c] = ""

    for c in sheet.columns:
        if sheet[c].dtype == object or str(sheet[c].dtype).startswith("string"):
            sheet[c] = sheet[c].map(clean)

    def norm_date(x: str) -> str:
        if not x:
            return ""
        dt = pd.to_datetime(x, errors="coerce")
        if pd.isna(dt):
            return ""
        return dt.date().isoformat()

    sheet["date_mount_iso"] = sheet["date_mount"].map(norm_date)
    sheet["mount_id_norm"] = pd.to_numeric(sheet["mount_id"], errors="coerce")

    roi_by_date = (
        rois[rois["experiment_date"].ne("")]
        .groupby("experiment_date", as_index=False)
        .agg(
            roi_foundations=("foundation", lambda s: ";".join(sorted({x for x in s if x}))),
            roi_experiment_keys=("experiment_key", lambda s: ";".join(sorted({x for x in s if x}))),
            n_roi_roots=("roi_dir", "count"),
        )
    )

    def row_sig(r) -> str:
        parts = []
        parts.append(f"mount_id={clean(r.get('mount_id'))}")
        fg = clean(r.get("foundation_guess"))
        if fg:
            parts.append(f"foundation_guess={fg}")
        ekg = clean(r.get("experiment_key_guess"))
        if ekg:
            parts.append(f"experiment_key_guess={ekg}")
        f = clean(r.get("ZF female genotype"))
        m = clean(r.get("ZF male genotype"))
        if f:
            parts.append(f"F={f}")
        if m:
            parts.append(f"M={m}")
        pls = clean(r.get("additional plasmids injected"))
        rnas = clean(r.get("additional mRNAs injected"))
        dyes = clean(r.get("additonal dye and chemicals"))
        if pls:
            parts.append(f"plasmids={pls}")
        if rnas:
            parts.append(f"rnas={rnas}")
        if dyes:
            parts.append(f"dyes={dyes}")
        cm = clean(r.get("comments"))
        if cm:
            parts.append(f"comments={cm[:120]}")
        dec = clean(r.get("Data evaluation comments"))
        if dec:
            parts.append(f"eval={dec[:120]}")
        return " | ".join(parts)

    sheet_by_date = (
        sheet[sheet["date_mount_iso"].ne("")]
        .groupby("date_mount_iso", as_index=False)
        .agg(
            n_sheet_rows=("date_mount_iso", "count"),
            mount_ids=("mount_id", lambda s: ";".join(sorted({x for x in s if x}))),
            sheet_rows=("mount_id", lambda _: ""),
        )
    )

    rows = []
    for d, grp in sheet[sheet["date_mount_iso"].ne("")].groupby("date_mount_iso"):
        sigs = [row_sig(r._asdict()) for r in grp.itertuples(index=False)]
        sigs = [s for s in sigs if s]
        rows.append({"date_mount": d, "sheet_rows": " || ".join(sigs)})

    sheet_rows_df = pd.DataFrame(rows)

    cand = sheet_by_date.merge(sheet_rows_df, left_on="date_mount_iso", right_on="date_mount", how="left")
    cand = cand.drop(columns=["date_mount_iso"])
    cand = cand.merge(roi_by_date, on="date_mount", how="left")

    for c in ["roi_foundations", "roi_experiment_keys"]:
        if c not in cand.columns:
            cand[c] = ""
        cand[c] = cand[c].fillna("").astype(str)

    for c in ["n_roi_roots"]:
        if c not in cand.columns:
            cand[c] = 0
        cand[c] = pd.to_numeric(cand[c], errors="coerce").fillna(0).astype(int)

    cand = cand.sort_values(["date_mount"], ascending=[True]).reset_index(drop=True)

    OUT_CAND.parent.mkdir(parents=True, exist_ok=True)
    cand.to_csv(OUT_CAND, sep="\t", index=False)

    if not OUT_TEMPLATE.exists():
        OUT_TEMPLATE.write_text(
            "foundation\texperiment_key\tdate_mount\tmount_id\tnotes\n",
            encoding="utf-8",
        )

    print("[OK] wrote:", OUT_CAND)
    print("[OK] wrote:", OUT_TEMPLATE)
    print("[OK] dates_in_sheet:", int(cand["date_mount"].nunique()))
    print("[OK] dates_with_any_rois:", int((cand["n_roi_roots"] > 0).sum())


if __name__ == "__main__":
    main()
