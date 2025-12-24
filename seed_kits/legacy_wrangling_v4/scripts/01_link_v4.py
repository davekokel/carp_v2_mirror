from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

V4_WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "working"
OUT_LINK = V4_WORK / "output_from_linking_v5.csv"

ROI_OBS = V4_WORK / "roi_observations.tsv"
SHEET_NORM = V4_WORK / "imaging_sheet_normalized.tsv"
LINKS = V4_WORK / "roi_sheet_links.tsv"

CLUSTER_PREFIX = "/clusterfs/vast/abcabc/"

def main() -> None:
    for p in [ROI_OBS, SHEET_NORM, LINKS]:
        if not p.exists():
            raise SystemExit(f"[STOP] missing required input: {p}")

    rois = pd.read_csv(ROI_OBS, sep="\t", low_memory=False)
    rois.columns = [str(c).strip() for c in rois.columns]

    sheet = pd.read_csv(SHEET_NORM, sep="\t", low_memory=False)
    sheet.columns = [str(c).strip() for c in sheet.columns]

    links = pd.read_csv(LINKS, sep="\t", low_memory=False)
    links.columns = [str(c).strip() for c in links.columns]

    need_rois = ["roi_root_rel", "roi_dir", "foundation", "experiment_key", "date_key", "experiment_date", "roi_name", "fish_label"]
    miss_rois = [c for c in need_rois if c not in rois.columns]
    if miss_rois:
        raise SystemExit(f"[STOP] roi_observations.tsv missing columns: {miss_rois}")

    need_links = ["roi_root_rel", "sheet_row_id", "link_method", "link_score", "n_candidates", "is_ambiguous"]
    miss_links = [c for c in need_links if c not in links.columns]
    if miss_links:
        raise SystemExit(f"[STOP] roi_sheet_links.tsv missing columns: {miss_links}")

    if "sheet_row_id" not in sheet.columns:
        raise SystemExit("[STOP] imaging_sheet_normalized.tsv missing sheet_row_id")

    df = rois.copy()

    df = df.merge(
        links[need_links + (["link_notes"] if "link_notes" in links.columns else [])],
        on=["roi_root_rel"],
        how="left",
    )

    sheet_small_cols = [
        "sheet_row_id",
        "date_mount",
        "mount_id",
        "data_location_raw",
        "data_location_posix",
        "data_location_cluster",
        "data_location",
        "foundation_guess",
        "experiment_key_guess",
        "additional_plasmids_injected",
        "additional_mrnas_injected",
        "additional_proteins_injected",
        "additional_dye_and_chemicals",
        "zf_female_genotype",
        "zf_male_genotype",
        "imaged_locations",
        "comments",
        "data_evaluation_comments",
    ]
    for c in sheet_small_cols:
        if c not in sheet.columns:
            sheet[c] = pd.NA

    df = df.merge(
        sheet[sheet_small_cols],
        left_on="sheet_row_id",
        right_on="sheet_row_id",
        how="left",
    )

    df["dataset"] = df["foundation"]
    df["roi_experiment_folder"] = df["experiment_key"]
    df["date_experiment"] = df["experiment_date"]
    df["fish"] = df["fish_label"]
    df["roi_rel"] = df["roi_root_rel"]
    df["roi_tiffs"] = pd.NA

    for c in ["organelle_hints", "fluor_hints", "anatomy_hints", "dev_stage_hints", "experiment_label_hints"]:
        df[c] = pd.NA

    def _choose_data_location(row) -> object:
        for c in ["data_location_cluster", "data_location_raw", "data_location"]:
            v = row.get(c)
            if v is not None:
                s = str(v).strip()
                if s and s.lower() not in ("nan", "none", "na", "n/a", "<na>", "/nan"):
                    return v
        return pd.NA

    df["Data location"] = df.apply(_choose_data_location, axis=1)

    df["date_mount"] = df.get("date_mount", pd.NA)
    df["mount_id"] = df.get("mount_id", pd.NA)

    df["ZF female genotype"] = df.get("zf_female_genotype", pd.NA)
    df["ZF male genotype"] = df.get("zf_male_genotype", pd.NA)

    df["additional plasmids injected"] = df.get("additional_plasmids_injected", pd.NA)
    df["additional mRNAs injected"] = df.get("additional_mrnas_injected", pd.NA)
    df["additonal proteins injected"] = df.get("additional_proteins_injected", pd.NA)
    df["additonal dye and chemicals"] = df.get("additional_dye_and_chemicals", pd.NA)

    df["Date born"] = pd.NA
    df["Time mounted"] = pd.NA
    df["Mounting Orientation"] = pd.NA
    df["Date screened/Initial feedback"] = pd.NA
    df["Date imaged"] = pd.NA
    df["Time placed in scope"] = pd.NA
    df["Start of imaging time"] = pd.NA
    df["End of imaging time"] = pd.NA

    df["Imaged Locations"] = df.get("imaged_locations", pd.NA)
    df["Unique Targets with blanks"] = pd.NA
    df["Unique Targets"] = pd.NA
    df["Dataset size (GB) - raw data only"] = pd.NA
    df["Camera Filters"] = pd.NA
    df["JSON excite map for ZF male"] = pd.NA
    df["JSON excite map for ZF female"] = pd.NA
    df["JSON excite map for plasmid"] = pd.NA
    df["JSON excite map for mRNA"] = pd.NA
    df["comments"] = df.get("comments", pd.NA)
    df["Data evaluation comments"] = df.get("data_evaluation_comments", pd.NA)

    df["inferred_row"] = False
    df["inferred_foundation"] = pd.NA
    df["inferred_experiment_folder"] = pd.NA
    df["inferred_date_key"] = pd.NA
    df["inferred_n_rois"] = pd.NA

    df["img_row_id"] = df["sheet_row_id"]
    df["mount_key"] = pd.NA
    df["imaged_key"] = pd.NA
    df["foundation_known"] = True

    df["img_experiment_folders"] = pd.NA
    df["img_tokens"] = pd.NA
    df["folder_key"] = pd.NA
    df["key_source"] = pd.NA
    df["folder_hit"] = pd.NA
    df["score_foundation"] = df.get("link_score", pd.NA)
    df["score_date_imaged"] = pd.NA

    df["roi_org"] = pd.NA
    df["roi_fluor"] = pd.NA
    df["roi_stage"] = pd.NA
    df["roi_label"] = pd.NA
    df["hit_org"] = pd.NA
    df["hit_fluor"] = pd.NA
    df["hit_stage"] = pd.NA
    df["hit_label"] = pd.NA
    df["score_hints"] = pd.NA

    df["n_img_candidates_for_roi"] = df.get("n_candidates", pd.NA)
    df["img_row_sort"] = pd.NA
    df["is_inferred_row"] = False
    df["is_ambiguous"] = df.get("is_ambiguous", False).fillna(False).astype(bool)
    df["link_source"] = df.get("link_method", "unlinked")

    cols = [
        "roi_dir",
        "dataset",
        "date_key",
        "roi_experiment_folder",
        "date_experiment",
        "fish",
        "roi_rel",
        "roi_name",
        "roi_tiffs",
        "organelle_hints",
        "fluor_hints",
        "anatomy_hints",
        "dev_stage_hints",
        "experiment_label_hints",
        "date_mount",
        "mount_id",
        "ZF female genotype",
        "ZF male genotype",
        "additional plasmids injected",
        "additional mRNAs injected",
        "additonal proteins injected",
        "additonal dye and chemicals",
        "Date born",
        "Time mounted",
        "Mounting Orientation",
        "Date screened/Initial feedback",
        "Date imaged",
        "Time placed in scope",
        "Start of imaging time",
        "End of imaging time",
        "Imaged Locations",
        "Unique Targets with blanks",
        "Unique Targets",
        "Data location",
        "Dataset size (GB) - raw data only",
        "Camera Filters",
        "JSON excite map for ZF male",
        "JSON excite map for ZF female",
        "JSON excite map for plasmid",
        "JSON excite map for mRNA",
        "comments",
        "Data evaluation comments",
        "inferred_row",
        "inferred_foundation",
        "inferred_experiment_folder",
        "inferred_date_key",
        "inferred_n_rois",
        "img_row_id",
        "mount_key",
        "imaged_key",
        "foundation",
        "foundation_known",
        "img_experiment_folders",
        "img_tokens",
        "folder_key",
        "key_source",
        "folder_hit",
        "score_foundation",
        "score_date_imaged",
        "roi_org",
        "roi_fluor",
        "roi_stage",
        "roi_label",
        "hit_org",
        "hit_fluor",
        "hit_stage",
        "hit_label",
        "score_hints",
        "n_img_candidates_for_roi",
        "img_row_sort",
        "is_inferred_row",
        "is_ambiguous",
        "link_source",
    ]

    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA

    OUT_LINK.parent.mkdir(parents=True, exist_ok=True)
    df_out = df[cols].copy()
    df_out.to_csv(OUT_LINK, index=False)
    print(f"[OK] wrote {len(df_out)} rows → {OUT_LINK}")

if __name__ == "__main__":
    main()
