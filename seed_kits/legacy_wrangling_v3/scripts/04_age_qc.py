from pathlib import Path
import re
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
IN_CSV = REPO_ROOT / "seed_kits" / "legacy_wrangling_v3" / "working" / "output_from_linking_v5.csv"
OUT_DIR = REPO_ROOT / "seed_kits" / "legacy_wrangling_v3" / "working" / "qc_age"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_SUMMARY = OUT_DIR / "age_qc_summary.csv"
OUT_MISMATCH = OUT_DIR / "age_qc_mismatches.csv"
OUT_NO_HINT = OUT_DIR / "age_qc_missing_hint.csv"
OUT_NO_DATES = OUT_DIR / "age_qc_missing_dates.csv"
OUT_GAP = OUT_DIR / "age_qc_mount_vs_imaged_gap.csv"

def nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a")

def parse_stage_to_hpf(s) -> float | None:
    if not nonempty(s):
        return None
    txt = str(s).strip().lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(hpf|dpf)", txt)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2)
    if unit == "hpf":
        return val
    if unit == "dpf":
        return val * 24.0
    return None

def hours_between(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a - b).dt.total_seconds() / 3600.0

def main() -> None:
    if not IN_CSV.exists():
        raise SystemExit(f"missing IN_CSV: {IN_CSV}")

    df = pd.read_csv(IN_CSV, low_memory=False)

    required = ["roi_dir", "dev_stage_hints", "Date born", "Date imaged", "date_mount"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"04_age_qc.py: missing required cols: {missing}")

    born = pd.to_datetime(df["Date born"], errors="coerce")
    imaged = pd.to_datetime(df["Date imaged"], errors="coerce")
    mounted = pd.to_datetime(df["date_mount"], errors="coerce")

    df["hint_hpf"] = df["dev_stage_hints"].apply(parse_stage_to_hpf)

    df["calc_hpf_imaged"] = hours_between(imaged, born)
    df["calc_hpf_mount"] = hours_between(mounted, born)

    df["delta_hpf_imaged"] = df["calc_hpf_imaged"] - df["hint_hpf"]
    df["delta_hpf_mount"] = df["calc_hpf_mount"] - df["hint_hpf"]

    df["abs_delta_imaged"] = df["delta_hpf_imaged"].abs()
    df["abs_delta_mount"] = df["delta_hpf_mount"].abs()

    df["mount_to_imaged_hours"] = hours_between(imaged, mounted)

    have_hint = df["hint_hpf"].notna()
    have_born = born.notna()
    have_imaged = imaged.notna()
    have_mounted = mounted.notna()

    comparable_imaged = have_hint & have_born & have_imaged
    comparable_mount = have_hint & have_born & have_mounted
    comparable_any = comparable_imaged | comparable_mount

    best_abs = pd.Series([pd.NA] * len(df), dtype="float")
    best_delta = pd.Series([pd.NA] * len(df), dtype="float")
    best_kind = pd.Series([pd.NA] * len(df), dtype="object")

    both = comparable_imaged & comparable_mount
    only_i = comparable_imaged & ~comparable_mount
    only_m = comparable_mount & ~comparable_imaged

    choose_imaged = both & (df["abs_delta_imaged"] <= df["abs_delta_mount"])
    choose_mount = both & (df["abs_delta_mount"] < df["abs_delta_imaged"])

    best_abs[choose_imaged] = df.loc[choose_imaged, "abs_delta_imaged"]
    best_delta[choose_imaged] = df.loc[choose_imaged, "delta_hpf_imaged"]
    best_kind[choose_imaged] = "Date imaged"

    best_abs[choose_mount] = df.loc[choose_mount, "abs_delta_mount"]
    best_delta[choose_mount] = df.loc[choose_mount, "delta_hpf_mount"]
    best_kind[choose_mount] = "date_mount"

    best_abs[only_i] = df.loc[only_i, "abs_delta_imaged"]
    best_delta[only_i] = df.loc[only_i, "delta_hpf_imaged"]
    best_kind[only_i] = "Date imaged"

    best_abs[only_m] = df.loc[only_m, "abs_delta_mount"]
    best_delta[only_m] = df.loc[only_m, "delta_hpf_mount"]
    best_kind[only_m] = "date_mount"

    df["best_abs_delta_hpf"] = best_abs
    df["best_delta_hpf"] = best_delta
    df["best_date_used"] = best_kind

    tol_hpf = 12.0
    mism = df[comparable_any & (df["best_abs_delta_hpf"] > tol_hpf)].copy()

    summary = pd.DataFrame([{
        "n_total": len(df),
        "n_have_hint": int(have_hint.sum()),
        "n_have_born": int(have_born.sum()),
        "n_have_imaged": int(have_imaged.sum()),
        "n_have_mount": int(have_mounted.sum()),
        "n_comparable_imaged": int(comparable_imaged.sum()),
        "n_comparable_mount": int(comparable_mount.sum()),
        "n_comparable_any": int(comparable_any.sum()),
        "tol_hpf": tol_hpf,
        "n_mismatch_gt_tol": int((comparable_any & (df["best_abs_delta_hpf"] > tol_hpf)).sum()),
        "best_abs_delta_p50": float(df.loc[comparable_any, "best_abs_delta_hpf"].quantile(0.50)) if comparable_any.any() else None,
        "best_abs_delta_p90": float(df.loc[comparable_any, "best_abs_delta_hpf"].quantile(0.90)) if comparable_any.any() else None,
        "best_abs_delta_p99": float(df.loc[comparable_any, "best_abs_delta_hpf"].quantile(0.99)) if comparable_any.any() else None,
        "chosen_date_used_counts": df.loc[comparable_any, "best_date_used"].value_counts(dropna=False).to_dict(),
    }])
    summary.to_csv(OUT_SUMMARY, index=False)

    cols_m = [c for c in [
        "roi_dir","dataset","date_key","link_source",
        "Date born","date_mount","Date imaged",
        "dev_stage_hints","hint_hpf",
        "calc_hpf_mount","delta_hpf_mount","abs_delta_mount",
        "calc_hpf_imaged","delta_hpf_imaged","abs_delta_imaged",
        "best_date_used","best_delta_hpf","best_abs_delta_hpf",
        "mount_to_imaged_hours",
        "roi_experiment_folder","Data location","img_row_id","key_source",
        "ZF female genotype","ZF male genotype",
        "score_folder","score_hints","score_date_imaged",
        "hit_label","hit_org","hit_fluor","hit_anat","hit_stage",
        "organelle_hints","fluor_hints","anatomy_hints","experiment_label_hints","dev_stage_hints",
    ] if c in mism.columns]
    mism.sort_values("best_abs_delta_hpf", ascending=False).to_csv(OUT_MISMATCH, index=False, columns=cols_m)

    no_hint = df[(have_born & (have_imaged | have_mounted) & (~have_hint))].copy()
    cols_nh = [c for c in ["roi_dir","dataset","date_key","link_source","Date born","date_mount","Date imaged","dev_stage_hints","roi_experiment_folder","Data location"] if c in no_hint.columns]
    no_hint.to_csv(OUT_NO_HINT, index=False, columns=cols_nh)

    no_dates = df[have_hint & (~have_born | (~have_imaged & ~have_mounted))].copy()
    cols_nd = [c for c in ["roi_dir","dataset","date_key","link_source","Date born","date_mount","Date imaged","dev_stage_hints","roi_experiment_folder","Data location"] if c in no_dates.columns]
    no_dates.to_csv(OUT_NO_DATES, index=False, columns=cols_nd)

    gap = df[have_mounted & have_imaged].copy()
    gap["abs_gap_hours"] = gap["mount_to_imaged_hours"].abs()
    gap = gap.sort_values("abs_gap_hours", ascending=False)
    cols_g = [c for c in ["roi_dir","dataset","date_key","link_source","date_mount","Date imaged","mount_to_imaged_hours","abs_gap_hours","Data location","img_row_id"] if c in gap.columns]
    gap.to_csv(OUT_GAP, index=False, columns=cols_g)

    print("IN_CSV", IN_CSV)
    print("OUT_SUMMARY", OUT_SUMMARY)
    print("OUT_MISMATCH", OUT_MISMATCH)
    print("OUT_NO_HINT", OUT_NO_HINT)
    print("OUT_NO_DATES", OUT_NO_DATES)
    print("OUT_GAP", OUT_GAP)
    print("N_TOTAL", len(df))
    print("N_HAVE_HINT", int(have_hint.sum()))
    print("N_COMPARABLE_ANY", int(comparable_any.sum()))
    print("N_MISMATCH_GT_12HPF", int((comparable_any & (df["best_abs_delta_hpf"] > tol_hpf)).sum()))

if __name__ == "__main__":
    main()
