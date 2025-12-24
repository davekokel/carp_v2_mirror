from __future__ import annotations

from pathlib import Path
import argparse
import re
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
V4_WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "working"

IN_DB = V4_WORK / "legacy_imaging_annotations_for_db_v9.csv"
OUT_ROI_V9_COMPAT = V4_WORK / "legacy_imaging_annotations_for_db_v9_compat.csv"

DATEFOLDER_RE = re.compile(r"^\d{8}_.+")
SPLIT_RE = re.compile(r"[\\/]+")

def _nonempty(x) -> bool:
    if x is None:
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan","none","na","n/a","<na>")

def _is_blank_series(s: pd.Series) -> pd.Series:
    return s.isna() | s.astype(str).str.strip().eq("") | s.astype(str).str.strip().str.lower().isin(["nan","none","na","n/a","<na>"])

def _extract_int(pattern: str, s: str) -> int | None:
    m = re.search(pattern, s)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None

def _date_yyyymmdd_from_any(v) -> str | None:
    if not _nonempty(v):
        return None
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    m = re.match(r"^(20\d{6})$", s)
    if m:
        return m.group(1)
    dt = pd.to_datetime(v, errors="coerce")
    if pd.isna(dt):
        m2 = re.match(r"^(20\d{6})", str(v))
        return m2.group(1) if m2 else None
    return dt.strftime("%Y%m%d")

def _plate_date_iso(yyyymmdd: str | None) -> str | None:
    if not _nonempty(yyyymmdd):
        return None
    if not re.match(r"^20\d{6}$", str(yyyymmdd)):
        return None
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"

def _extract_datefolder_tokens(roi_dir: str) -> list[str]:
    if roi_dir is None or (isinstance(roi_dir, float) and pd.isna(roi_dir)):
        return []
    s = str(roi_dir)
    toks = [t for t in SPLIT_RE.split(s) if t]
    hits = [t for t in toks if DATEFOLDER_RE.match(t)]
    return hits

def _yyyymmdd_to_iso(yyyymmdd: str) -> str:
    dt = pd.to_datetime(yyyymmdd, format="%Y%m%d", errors="raise").date()
    return dt.isoformat()

def _fish_label_from_roi_dir(roi_dir: str):
    rd = str(roi_dir or "")
    m = re.search(r"/(fish[^/]+)(?:/|$)", rd, flags=re.I)
    if m:
        return m.group(1)
    base = rd.rstrip("/").split("/")[-1] if rd else ""
    if base.lower().startswith("fish"):
        return base
    m2 = re.search(r"/([^/]+)/[^/]+$", rd)
    return (m2.group(1) if m2 else pd.NA)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--in-csv', default=str(IN_DB), help='Input CSV (enriched-for-db)')
    ap.add_argument('--out-csv', default=str(OUT_ROI_V9_COMPAT), help='Output compat CSV')
    args = ap.parse_args()

    in_db_path = Path(args.in_csv)
    out_compat_path = Path(args.out_csv)

    if not in_db_path.exists():
        raise SystemExit(f'missing: {in_db_path}')

    df = pd.read_csv(in_db_path, low_memory=False)
    if "roi_dir" not in df.columns:
        raise SystemExit("IN_DB missing roi_dir")

    df = df.copy()

    if "date_mount" not in df.columns:
        df["date_mount"] = pd.NA
    if "Data location" not in df.columns:
        df["Data location"] = pd.NA

    blank_loc = _is_blank_series(df["Data location"])
    blank_dat = _is_blank_series(df["date_mount"])
    both_blank = blank_loc & blank_dat

    if int(both_blank.sum()):
        toks = df.loc[both_blank, "roi_dir"].map(_extract_datefolder_tokens)
        bad = toks.index[toks.map(len).ne(1)].tolist()
        if bad:
            show = df.loc[bad, ["roi_dir"]].copy()
            show["datefolder_tokens"] = toks.loc[bad].map(lambda xs: ";".join(xs))
            print(show.head(200).to_string(index=True))
            raise SystemExit(f"[STOP] {len(bad)} rows violate deterministic datefolder rule")

        datefolder = toks.map(lambda xs: xs[0])
        yyyymmdd = datefolder.map(lambda s: s[:8])
        iso = yyyymmdd.map(_yyyymmdd_to_iso)
        df.loc[both_blank, "date_mount"] = iso

    if "date_key" in df.columns:
        yyyymmdd = df["date_key"].apply(_date_yyyymmdd_from_any)
    else:
        yyyymmdd = df["roi_dir"].astype(str).str.extract(r"/(20\d{6})[_-]")[0]

    yyyymmdd_fallback = df["roi_dir"].astype(str).str.extract(r"/(20\d{6})[_-]")[0]
    yyyymmdd = yyyymmdd.fillna(yyyymmdd_fallback)

    df["plate_date_yyyymmdd"] = yyyymmdd
    df["plate_date"] = pd.to_numeric(df["plate_date_yyyymmdd"], errors="coerce").astype("Int64")
    df["plate_date_iso"] = df["plate_date_yyyymmdd"].map(_plate_date_iso)

    if "roi_experiment_folder" in df.columns:
        exp = df["roi_experiment_folder"].astype(str)
    else:
        exp = df["roi_dir"].astype(str).str.extract(r"/(Aang_Foundation|Korra_Foundation)/([^/]+)")[1].fillna("")
    df["experiment_folder"] = exp

    if "dataset_slug_norm" in df.columns:
        slug = df["dataset_slug_norm"].astype(str)
    else:
        slug = df["experiment_folder"].astype(str)
    df["dataset_slug_norm"] = slug

    if "dataset" in df.columns:
        dataset = df["dataset"].astype(str).str.lower().str.strip()
        dataset = dataset.replace({"nan": pd.NA, "none": pd.NA, "": pd.NA})
    else:
        dataset = pd.Series([pd.NA] * len(df))
    df["dataset"] = dataset

    fish_label = df["fish"].astype(str).str.strip() if "fish" in df.columns else pd.Series([pd.NA] * len(df))
    fish_label = fish_label.replace({"nan": pd.NA, "none": pd.NA, "": pd.NA})
    fish_label = fish_label.where(~_is_blank_series(fish_label), df["roi_dir"].astype(str).apply(_fish_label_from_roi_dir))
    df["fish_label"] = fish_label

    df["plate_group_key"] = df["dataset"].astype(str).str.strip().str.lower() + "|" + df["dataset_slug_norm"].astype(str).str.strip()

    df["plate_id_filled"] = (
        df.groupby("plate_date_yyyymmdd", dropna=False)["plate_group_key"]
        .transform(lambda s: pd.factorize(s)[0] + 1)
    )

    def slot_key(row):
        fl = row.get("fish_label")
        if _nonempty(fl):
            return str(fl).strip().lower()
        rd = str(row.get("roi_dir") or "")
        m = re.search(r"/(fish[^/]+)(?:/|$)", rd, flags=re.I)
        return (m.group(1).lower() if m else "fish_unknown")

    df["slot_key"] = df.apply(slot_key, axis=1)

    df["slot_id_filled"] = (
        df.groupby(["plate_date_yyyymmdd","plate_id_filled"])["slot_key"]
          .transform(lambda s: pd.factorize(s)[0] + 1)
    )

    def roi_index(row):
        rn = str(row.get("roi_name") or "")
        rr = str(row.get("roi_rel") or "")
        rd = str(row.get("roi_dir") or "")
        x = rn if _nonempty(rn) else (rr if _nonempty(rr) else rd)
        i2 = _extract_int(r"roi(\d+)", x.lower())
        if i2 is not None:
            return i2
        m = re.search(r"/roi(\d+)", rd.lower())
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return None

    df["roi_index_within_slot"] = df.apply(roi_index, axis=1)
    df["roi_index_within_slot"] = (
        df.groupby(["plate_date_yyyymmdd","plate_id_filled","slot_id_filled"])["roi_index_within_slot"]
          .transform(lambda s: s.fillna(pd.Series(range(1, len(s)+1), index=s.index)))
    ).astype(int)

    def _renumber_group(g):
        g2 = g.sort_values(["roi_dir"], kind="mergesort").copy()
        g2["roi_index_within_slot"] = range(1, len(g2) + 1)
        return g2

    df = (
        df.groupby(["plate_date_yyyymmdd","plate_id_filled","slot_id_filled"], group_keys=False)
          .apply(_renumber_group)
          .reset_index(drop=True)
    )

    def bruker_roi_id(row):
        for k in ["bruker_roi_id", "roi_name", "roi_rel", "roi_dir"]:
            v = row.get(k)
            if _nonempty(v):
                return str(v).strip()
        return None

    df["bruker_roi_id"] = df.apply(bruker_roi_id, axis=1)

    # -----------------------------------------------------------------
    # v9_build_legacy_clutches_from_v9.py expects clutch-level fields to
    # already exist on the ROI CSV. Derive them deterministically here.
    # -----------------------------------------------------------------

    def _first_token(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        s = str(v).strip()
        if not s or s.lower() in ("nan", "none", "na", "n/a", "<na>"):
            return None
        for part in re.split(r"[|,;]+", s):
            part = part.strip()
            if part and part.lower() not in ("nan", "none", "na", "n/a", "<na>"):
                return part
        return None

    def _date_iso_any(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        s = str(v).strip()
        if not s or s.lower() in ("nan", "none", "na", "n/a", "<na>"):
            return None
        dt = pd.to_datetime(v, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.date().isoformat()

    # Parent genotype text (raw sheet values)
    if "parent_female_genotype_text" not in df.columns:
        df["parent_female_genotype_text"] = df.get("ZF female genotype", pd.NA)
    if "parent_male_genotype_text" not in df.columns:
        df["parent_male_genotype_text"] = df.get("ZF male genotype", pd.NA)

    # date_born (ISO)
    if "date_born" not in df.columns:
        df["date_born"] = df.get("Date born", pd.NA)
    df["date_born"] = df["date_born"].apply(_date_iso_any)

    # Treatment basecode “single” columns expected by v9 clutch builder
    if "treatment_rna_rna_base_code" not in df.columns:
        df["treatment_rna_rna_base_code"] = df.get("treatment_rna_base_codes", pd.NA).apply(_first_token)
    if "treatment_plasmid_plasmid_base_code" not in df.columns:
        df["treatment_plasmid_plasmid_base_code"] = df.get("treatment_plasmid_base_codes", pd.NA).apply(_first_token)

    # legacy_clutch_key: stable clutch key per (plate_code, slot_index)
    if "plate_code" not in df.columns:
        if "plate_date_yyyymmdd" in df.columns:
            plate_date_yyyymmdd = (
                df["plate_date_yyyymmdd"]
                  .astype(str)
                  .str.replace(".0", "", regex=False)
                  .str.extract(r"(20\d{6})", expand=False)
            )
        else:
            plate_date_yyyymmdd = (
                pd.to_datetime(df["plate_date"], errors="coerce")
                  .dt.strftime("%Y%m%d")
            )
        plate_id = pd.to_numeric(df["plate_id_filled"], errors="coerce").astype("Int64")
        df["plate_code"] = plate_date_yyyymmdd.astype("string") + "-plate" + plate_id.astype("string")
    if "legacy_clutch_key" not in df.columns:
        df["legacy_clutch_key"] = df["plate_code"].astype(str) + "|slot" + df["slot_id_filled"].astype(int).astype(str)
    out_compat_path = Path(out_compat_path)
    out_compat_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_compat_path, index=False)
    print('WROTE', out_compat_path, 'ROWS', len(df))

if __name__ == "__main__":
    main()
