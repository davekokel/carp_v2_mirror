from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
V4_WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "working"

RE_ROI_SLASH = re.compile(r"/roi(?P<idx>\d+)(?:_(?P<label>[A-Za-z0-9][A-Za-z0-9_-]*))?$", re.IGNORECASE)
RE_ROI_UNDERSCORE = re.compile(r"_roi(?P<idx>\d+)(?:_(?P<label>[A-Za-z0-9][A-Za-z0-9_-]*))?$", re.IGNORECASE)

def _clean(s: object) -> str:
    if s is None:
        return ""
    t = str(s).strip()
    return "" if t.lower() in ("nan", "none", "na", "n/a", "<na>") else t

def _yyyymmdd_from_any(v: object) -> str | None:
    s = _clean(v)
    if not s:
        return None
    s2 = s.replace("-", "")
    m = re.search(r"(20\d{6})", s2)
    if m:
        return m.group(1)
    dt = pd.to_datetime(s, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.strftime("%Y%m%d")

def _roi_index_from_path(roi_path: str) -> int | None:
    s = _clean(roi_path)
    if not s:
        return None
    m = RE_ROI_SLASH.search(s) or RE_ROI_UNDERSCORE.search(s)
    if not m:
        return None
    try:
        return int(m.group("idx"))
    except Exception:
        return None

def _bruker_roi_id_from_row(row: pd.Series) -> str:
    for k in ["bruker_roi_id", "roi_name", "roi_dir"]:
        v = row.get(k)
        s = _clean(v)
        if s:
            return s.split("/")[-1]
    return ""

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-csv", default=str(V4_WORK / "output_from_linking_v5.csv"))
    ap.add_argument("--out-csv", default=str(V4_WORK / "legacy_imaging_annotations_for_loader_v9_compat.csv"))
    args = ap.parse_args()

    p_in = Path(args.in_csv)
    p_out = Path(args.out_csv)

    if not p_in.exists():
        raise SystemExit(f"[STOP] missing input: {p_in}")

    df = pd.read_csv(p_in, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    if "roi_dir" not in df.columns:
        raise SystemExit("[STOP] input missing roi_dir")

    df = df.copy()
    df["roi_dir"] = df["roi_dir"].astype(str).str.strip()

    # plate_date_yyyymmdd + plate_date(int) derived from date_mount (preferred) else roi_dir
    ymd = df.get("date_mount", pd.Series([pd.NA] * len(df))).map(_yyyymmdd_from_any)
    ymd2 = df["roi_dir"].map(_yyyymmdd_from_any)
    ymd = ymd.fillna(ymd2)

    df["plate_date_yyyymmdd"] = ymd
    df["plate_date"] = pd.to_numeric(df["plate_date_yyyymmdd"], errors="coerce").astype("Int64")

    # plate grouping: per (plate_date_yyyymmdd, roi_experiment_folder)
    if "roi_experiment_folder" in df.columns:
        grp = df["roi_experiment_folder"].astype(str).str.strip().replace({"nan": ""})
    else:
        grp = df["roi_dir"].astype(str).str.extract(r"/(Aang_Foundation|Korra_Foundation)/([^/]+)")[1].fillna("").astype(str)

    df["plate_group_key"] = grp
    df["plate_id_filled"] = (
        df.groupby("plate_date_yyyymmdd", dropna=False)["plate_group_key"]
          .transform(lambda s: pd.factorize(s)[0] + 1)
          .astype("Int64")
    )

    # slot grouping: per (plate_date_yyyymmdd, plate_id_filled, fish label)
    if "fish" in df.columns:
        slot_key = df["fish"].astype(str).str.strip().str.lower().replace({"nan": ""})
    else:
        slot_key = df["roi_dir"].astype(str).str.extract(r"/(fish[^/]+)(?:/|$)", flags=re.I)[0].fillna("").astype(str).str.lower()

    slot_key = slot_key.where(slot_key != "", "fish_unknown")
    df["slot_key"] = slot_key

    df["slot_id_filled"] = (
        df.groupby(["plate_date_yyyymmdd", "plate_id_filled"], dropna=False)["slot_key"]
          .transform(lambda s: pd.factorize(s)[0] + 1)
          .astype("Int64")
    )

    # roi_index_within_slot
    idx = df["roi_dir"].map(_roi_index_from_path)
    df["roi_index_within_slot"] = idx

    # If missing or duplicates within slot, renumber deterministically by roi_dir
    df["_roi_index_tmp"] = df["roi_index_within_slot"]
    df["_roi_index_tmp"] = df["_roi_index_tmp"].where(df["_roi_index_tmp"].notna(), 0).astype(int)

    df = df.sort_values(
        ["plate_date_yyyymmdd", "plate_id_filled", "slot_id_filled", "_roi_index_tmp", "roi_dir"],
        kind="mergesort",
    ).copy()

    df["roi_index_within_slot"] = (
        df.groupby(["plate_date_yyyymmdd", "plate_id_filled", "slot_id_filled"], sort=False)
          .cumcount()
          .add(1)
          .astype(int)
    )

    # bruker_roi_id
    df["bruker_roi_id"] = df.apply(_bruker_roi_id_from_row, axis=1)
    df["bruker_roi_id"] = df["bruker_roi_id"].astype(str).str.strip()

    # Optional anatomy passthrough
    if "roi_note_anatomy" not in df.columns:
        df["roi_note_anatomy"] = ""

    keep = [
        "plate_date",
        "plate_id_filled",
        "slot_id_filled",
        "roi_index_within_slot",
        "roi_dir",
        "bruker_roi_id",
        "roi_note_anatomy",
    ]
    for c in keep:
        if c not in df.columns:
            df[c] = pd.NA

    p_out.parent.mkdir(parents=True, exist_ok=True)
    df[keep].to_csv(p_out, index=False)

    print("[OK] wrote:", p_out)
    print("[OK] rows:", len(df))
    print("[OK] unique roi_dir:", int(df["roi_dir"].nunique()))
    print("[OK] unique (plate_date, plate_id_filled):", int(df[["plate_date","plate_id_filled"]].drop_duplicates().shape[0]))

if __name__ == "__main__":
    main()
