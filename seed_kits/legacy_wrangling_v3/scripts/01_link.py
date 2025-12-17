from pathlib import Path
import pandas as pd
import re

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW = REPO_ROOT / "seed_kits" / "legacy_wrangling_v2" / "raw"
WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v3" / "working"
WORK.mkdir(parents=True, exist_ok=True)

ROI_XLSX = RAW / "2025-11-13-092338-korra_aang_roi_root_tiffs_good-3.xlsx"
IMAGING_XLSX = RAW / "2025-11-21-220012-imaging_sheet.xlsx"
HINTS_CSV = WORK / "qc_hint_mining" / "roi_typed_hints_v1.csv"

OUT_LINK = WORK / "output_from_linking_v5.csv"
OUT_LINK_REVIEW = WORK / "output_from_linking_v5_human_review.csv"
OUT_QC_KEYS = WORK / "qc_link_key_coverage.csv"
OUT_QC_AMBIG = WORK / "qc_ambiguous_date_matches.csv"
OUT_QC_UNMATCHED = WORK / "qc_unmatched_roi_dates.csv"


def nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a")


def date_key_from_date(x):
    if not nonempty(x):
        return None
    dt = pd.to_datetime(x, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.strftime("%Y%m%d")


def roi_date_key_from_path(p):
    if not nonempty(p):
        return None
    m = re.search(r"/(20\d{6})[_-]", str(p))
    return m.group(1) if m else None


def foundation_from_data_location(x):
    if not nonempty(x):
        return None
    s = str(x)
    if "Aang_Foundation" in s:
        return "aang"
    if "Korra_Foundation" in s:
        return "korra"
    return None

def dataset_from_path(roi_dir: str) -> str | None:
    if roi_dir is None:
        return None
    s = str(roi_dir)
    if "/Aang_Foundation/" in s:
        return "aang"
    if "/Korra_Foundation/" in s:
        return "korra"
    return None

def roi_experiment_folder(roi_dir):
    if not nonempty(roi_dir):
        return None
    m = re.search(r"/(Aang_Foundation|Korra_Foundation)/([^/]+)", str(roi_dir))
    return m.group(2) if m else None


def img_experiment_folders(x):
    if not nonempty(x):
        return []
    toks = re.split(r"[;,&]| and |\s+", str(x))
    out = []
    for t in toks:
        m = re.search(r"(20\d{6}[_-][A-Za-z0-9-]+)", t)
        if m:
            out.append(m.group(1))
    return list(dict.fromkeys(out))


def norm_token(s):
    s = str(s).lower()
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("\\", "/")
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def split_pipe(s):
    if not nonempty(s):
        return set()
    out = set()
    for x in re.split(r"[|,;]+", str(s)):
        x = norm_token(x)
        if x:
            out.add(x)
    return out


def tokenize_imaging_row(row):
    cols = [
        "Data location",
        "Imaged Locations",
        "Unique Targets",
        "Unique Targets with blanks",
        "ZF female genotype",
        "ZF male genotype",
        "additional plasmids injected",
        "additional mRNAs injected",
        "additonal proteins injected",
        "additonal dye and chemicals",
        "comments",
        "Data evaluation comments",
    ]
    out = set()
    for c in cols:
        if c not in row.index:
            continue
        v = row[c]
        if not nonempty(v):
            continue
        s = str(v)
        for part in re.split(r"[|,;]+", s):
            part = norm_token(part)
            if part:
                out.add(part)
        for m in re.finditer(r"(20\d{6}[_-][A-Za-z0-9-]+)", s):
            out.add(norm_token(m.group(1)))
    return out


def main():
    if not ROI_XLSX.exists():
        raise SystemExit(f"missing ROI xlsx: {ROI_XLSX}")
    if not IMAGING_XLSX.exists():
        raise SystemExit(f"missing imaging xlsx: {IMAGING_XLSX}")
    if not HINTS_CSV.exists():
        raise SystemExit(f"missing hints csv (run roi_hint_apply_v1.py first): {HINTS_CSV}")

    roi = pd.read_excel(ROI_XLSX)
    img_path_aug = WORK / "imaging_sheet_augmented_v3.csv"
    if img_path_aug.exists():
        img0 = pd.read_csv(img_path_aug, low_memory=False)
        print("IMAGING_SOURCE", img_path_aug)
    else:
        img0 = pd.read_excel(IMAGING_XLSX)
        print("IMAGING_SOURCE", IMAGING_XLSX)
    hints = pd.read_csv(HINTS_CSV, low_memory=False)

    need_roi = ["roi_dir", "dataset", "date_experiment", "fish", "roi_name"]
    missing_roi = [c for c in need_roi if c not in roi.columns]
    if missing_roi:
        raise SystemExit(f"ROI xlsx missing cols: {missing_roi}")
    if "date_mount" not in img0.columns:
        raise SystemExit("imaging sheet missing col: date_mount")

    roi = roi.copy()
    roi["roi_dir"] = roi["roi_dir"].astype(str)

    # dataset: trust XLSX, but backfill from path if missing
    roi["dataset"] = roi["dataset"].astype(str).str.lower().str.strip()
    mask_ds = roi["dataset"].isin(["", "nan", "none"])
    roi.loc[mask_ds, "dataset"] = roi.loc[mask_ds, "roi_dir"].apply(dataset_from_path)

    # date_key: always derive from roi_dir
    roi["date_key"] = roi["roi_dir"].apply(roi_date_key_from_path)

    # experiment folder: always derive from roi_dir
    roi["roi_experiment_folder"] = roi["roi_dir"].apply(roi_experiment_folder)

    hints = hints.copy()
    if "roi_dir" not in hints.columns:
        raise SystemExit("hints csv missing roi_dir")
    for c in ["organelle_hints", "fluor_hints", "anatomy_hints", "dev_stage_hints", "experiment_label_hints"]:
        if c not in hints.columns:
            hints[c] = pd.NA

    roi = roi.merge(
        hints[[
            "roi_dir",
            "organelle_hints",
            "fluor_hints",
            "anatomy_hints",
            "dev_stage_hints",
            "experiment_label_hints",
        ]],
        on="roi_dir",
        how="left",
    )

    img0 = img0.copy()
    for c in img0.columns:
        if img0[c].dtype == object or str(img0[c].dtype).startswith("string"):
            img0[c] = (
                img0[c]
                .astype("string")
                .str.replace("¬†", " ", regex=False)
                .str.replace("\u00a0", " ", regex=False)
                .str.replace(r"\s+", " ", regex=True)
                .str.strip()
            )
    img0["img_row_id"] = img0.index.astype(int)

    img0["mount_key"] = img0["date_mount"].apply(date_key_from_date)
    img0["imaged_key"] = img0.get("Date imaged", pd.Series([pd.NA] * len(img0))).apply(date_key_from_date)

    dl = img0.get("Data location", pd.Series([pd.NA] * len(img0)))
    img0["foundation"] = dl.apply(foundation_from_data_location)
    img0["foundation_known"] = img0["foundation"].notna()

    img0["img_experiment_folders"] = dl.apply(img_experiment_folders)
    img0["img_tokens"] = img0.apply(tokenize_imaging_row, axis=1)

    

    img_mount = img0[img0["mount_key"].notna()].copy()
    img_mount["date_key"] = img_mount["mount_key"]
    img_mount["key_source"] = "date_mount"

    img_imaged = img0[img0["imaged_key"].notna()].copy()
    img_imaged["date_key"] = img_imaged["imaged_key"]
    img_imaged["key_source"] = "date_imaged"

    img = pd.concat([img_mount, img_imaged], ignore_index=True)

    roi_dates = roi.groupby(["dataset", "date_key"], dropna=False).size().reset_index(name="n_roi_rows")
    img_dates = img.groupby(["foundation", "date_key"], dropna=False).size().reset_index(name="n_img_rows")
    roi_dates.merge(
        img_dates,
        left_on=["dataset", "date_key"],
        right_on=["foundation", "date_key"],
        how="left",
    ).to_csv(OUT_QC_KEYS, index=False)

    candidates = roi.merge(img, on="date_key", how="left")

    foundation_known = candidates["foundation_known"].fillna(False).astype(bool)
    ok = (~foundation_known) | (candidates["dataset"] == candidates["foundation"])
    candidates = candidates[ok].copy()

    def folder_hit(r):
        ef = r.get("roi_experiment_folder")
        dl = r.get("Data location")
        if not nonempty(ef) or not nonempty(dl):
            return 0
        return 1 if str(ef) in str(dl) else 0

    candidates["folder_hit"] = candidates.apply(folder_hit, axis=1)

    candidates["score_foundation"] = candidates["foundation_known"].fillna(False).astype(bool).astype(int)
    candidates["score_date_imaged"] = candidates.get("key_source", pd.Series([None] * len(candidates))).astype(str).eq("date_imaged").astype(int)

    candidates["roi_org"] = candidates["organelle_hints"].apply(split_pipe)
    candidates["roi_fluor"] = candidates["fluor_hints"].apply(split_pipe)
    candidates["roi_stage"] = candidates["dev_stage_hints"].apply(split_pipe)
    candidates["roi_label"] = candidates["experiment_label_hints"].apply(split_pipe)

    def hit(a, b):
        if not isinstance(a, set) or not isinstance(b, set):
            return 0
        return int(bool(a & b))

    candidates["hit_org"] = candidates.apply(lambda r: hit(r["roi_org"], r["img_tokens"]), axis=1)
    candidates["hit_fluor"] = candidates.apply(lambda r: hit(r["roi_fluor"], r["img_tokens"]), axis=1)
    candidates["hit_stage"] = candidates.apply(lambda r: hit(r["roi_stage"], r["img_tokens"]), axis=1)
    candidates["hit_label"] = candidates.apply(lambda r: hit(r["roi_label"], r["img_tokens"]), axis=1)

    candidates["score_hints"] = (
        candidates["hit_label"] * 3
        + candidates["hit_org"] * 2
        + candidates["hit_fluor"] * 2
        + candidates["hit_stage"] * 1
    )

    # ── ambiguity accounting ──────────────────────────────────────────
    candidates["n_img_candidates_for_roi"] = (
        candidates.groupby("roi_dir")["img_row_id"]
        .transform(lambda s: pd.to_numeric(s, errors="coerce").notna().sum())
    )

    # Prefer folder-hit rows IF ANY exist for this ROI
    has_folder = candidates.groupby("roi_dir")["folder_hit"].transform("max")
    candidates = candidates[(has_folder == 0) | (candidates["folder_hit"] == 1)].copy()

    # Stable numeric tiebreak
    candidates["img_row_sort"] = (
        pd.to_numeric(candidates["img_row_id"], errors="coerce")
        .fillna(1e18)
    )

    # ── final ranking ─────────────────────────────────────────────────
    ranked = candidates.sort_values(
        [
            "roi_dir",
            "folder_hit",
            "score_hints",
            "score_foundation",
            "score_date_imaged",
            "img_row_sort",
        ],
        ascending=[True, False, False, False, False, True],
    )

    ranked_one = ranked.drop_duplicates("roi_dir", keep="first").copy()

    # Drop colliding columns so roi's canonical dataset/date_key/roi_experiment_folder survive as-is
    drop_cols = [c for c in ["dataset", "date_key", "roi_experiment_folder"] if c in ranked_one.columns]
    ranked_one = ranked_one.drop(columns=drop_cols)

    best = roi[["roi_dir", "dataset", "date_key", "roi_experiment_folder"]].merge(
        ranked_one,
        on="roi_dir",
        how="left",
    )

    best["is_ambiguous"] = best["n_img_candidates_for_roi"].fillna(0).astype(int) > 1

    def link_source(r):
        if not nonempty(r.get("img_row_id")):
            return "unmatched"
        if int(r.get("folder_hit", 0) or 0) == 1:
            return "folder+date"
        return "date_key"

    best["link_source"] = best.apply(link_source, axis=1)

    best[best["is_ambiguous"]].to_csv(OUT_QC_AMBIG, index=False)
    best[best["link_source"] == "unmatched"].to_csv(OUT_QC_UNMATCHED, index=False)

    # ── final outputs ────────────────────────────────────────────────
    best.to_csv(OUT_LINK, index=False)

    # Human review: ambiguous first, then unresolved, then clean
    best.sort_values(
        [
            "is_ambiguous",
            "link_source",
            "date_key",
            "roi_experiment_folder",
            "roi_dir",
        ],
        ascending=[False, True, True, True, True],
    ).to_csv(OUT_LINK_REVIEW, index=False)

    print("WROTE", OUT_LINK)
    print("WROTE", OUT_LINK_REVIEW)
    print("WROTE", OUT_QC_KEYS)
    print("WROTE", OUT_QC_AMBIG)
    print("WROTE", OUT_QC_UNMATCHED)
    print("ROI_ROWS", len(roi))
    print("IMG_ROWS", len(img))
    print("LINK_SOURCE_COUNTS")
    print(best["link_source"].value_counts(dropna=False).to_string())
    print("AMBIG_ROIS", int(best["is_ambiguous"].sum()))


if __name__ == "__main__":
    main()
