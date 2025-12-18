from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
V3_WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v3" / "working"

IN_DB = V3_WORK / "legacy_imaging_annotations_for_db_v9.csv"

OUT_ROI_V9_COMPAT = V3_WORK / "legacy_imaging_annotations_for_db_v9_compat.csv"
OUT_CLUTCHES_V9 = V3_WORK / "legacy_clutches_v9.csv"
OUT_MEMBERSHIPS_V9 = V3_WORK / "legacy_clutch_memberships_v9.csv"

DATEFOLDER_RE = re.compile(r"^\d{8}_.+")
SPLIT_RE = re.compile(r"[\\/]+")

def _nonempty(x) -> bool:
    if x is None:
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan","none","na","n/a","<na>")

def _is_blank_series(s: pd.Series) -> pd.Series:
    return s.isna() | s.astype(str).str.strip().eq("") | s.astype(str).str.strip().str.lower().isin(["nan","none","na","n/a","<na>"])

def _split_pipe_first(x):
    if not _nonempty(x):
        return None
    parts = [p.strip() for p in re.split(r"[|,;]+", str(x)) if p.strip()]
    return parts[0] if parts else None

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

def _plate_code(plate_date: str, plate_id: int) -> str:
    return f"{plate_date.replace('-','')}-plate{plate_id}"

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

def main() -> None:
    if not IN_DB.exists():
        raise SystemExit(f"missing: {IN_DB}")

    df = pd.read_csv(IN_DB, low_memory=False)
    if "roi_dir" not in df.columns:
        raise SystemExit("IN_DB missing roi_dir")

    df = df.copy()

    # ─────────────────────────────────────────────────────────────
    # STEP 1A (CANONICAL): fill date_mount deterministically from roi_dir
    # when BOTH date_mount and Data location are blank.
    # Fail loudly if rule cannot apply deterministically.
    # ─────────────────────────────────────────────────────────────
    if "date_mount" not in df.columns:
        raise SystemExit("IN_DB missing date_mount")
    if "Data location" not in df.columns:
        raise SystemExit("IN_DB missing 'Data location'")

    blank_loc = _is_blank_series(df["Data location"])
    blank_dat = _is_blank_series(df["date_mount"])
    both_blank = blank_loc & blank_dat

    n_both_blank_before = int(both_blank.sum())
    print(f"STEP1A n_both_blank_before(Data location & date_mount)={n_both_blank_before}")

    if n_both_blank_before:
        # tokens per row; require exactly one datefolder token
        rows = df.loc[both_blank, ["roi_dir", "link_source"]].copy() if "link_source" in df.columns else df.loc[both_blank, ["roi_dir"]].copy()
        toks = rows["roi_dir"].map(_extract_datefolder_tokens)
        bad = rows.loc[toks.map(len).ne(1)].copy()
        if len(bad):
            bad["datefolder_tokens"] = toks.loc[bad.index].map(lambda xs: ";".join(xs))
            print("STEP1A ERROR: rows with both blanks but not exactly one {YYYYMMDD}_* token in roi_dir")
            print(bad.head(200).to_string(index=True))
            raise SystemExit(f"STEP1A ERROR: {len(bad)} rows violate deterministic rule")

        # Fill date_mount from the single token’s YYYYMMDD prefix
        datefolder = toks.map(lambda xs: xs[0])
        yyyymmdd = datefolder.map(lambda s: s[:8])
        iso = yyyymmdd.map(_yyyymmdd_to_iso)

        df.loc[both_blank, "date_mount"] = iso

        # Audit columns: only set if present; do not invent schema silently beyond CSV.
        if "folder_hit" in df.columns:
            df.loc[both_blank, "folder_hit"] = datefolder
        if "key_source" in df.columns:
            ks = df.loc[both_blank, "key_source"].copy()
            df.loc[both_blank, "key_source"] = ks.map(lambda v: (str(v).strip() + "|roi_dir_datefolder") if _nonempty(v) and "roi_dir_datefolder" not in str(v) else ("roi_dir_datefolder" if not _nonempty(v) else str(v).strip()))
        if "inferred_row" in df.columns:
            df.loc[both_blank, "inferred_row"] = True

        print(f"STEP1A n_date_mount_filled_from_roi_dir={n_both_blank_before}")

    # Verify no both-blank remain
    blank_loc_after = _is_blank_series(df["Data location"])
    blank_dat_after = _is_blank_series(df["date_mount"])
    both_blank_after = blank_loc_after & blank_dat_after
    n_both_blank_after = int(both_blank_after.sum())
    print(f"STEP1A n_both_blank_after(Data location & date_mount)={n_both_blank_after}")

    if n_both_blank_after:
        show = [c for c in ["roi_dir", "date_mount", "Data location", "link_source", "folder_hit", "key_source"] if c in df.columns]
        print("STEP1A ERROR: still have both-blank rows after inference")
        print(df.loc[both_blank_after, show].head(200).to_string(index=False))
        raise SystemExit("STEP1A ERROR: refusing to continue with inconsistent legacy fields")

    # ─────────────────────────────────────────────────────────────
    # Existing logic continues unchanged below
    # ─────────────────────────────────────────────────────────────

    # Prefer date_key if present, but FALL BACK to parsing ROI path (needed for Denoising/*)
    if "date_key" in df.columns:
        yyyymmdd = df["date_key"].apply(_date_yyyymmdd_from_any)
    else:
        yyyymmdd = df["roi_dir"].astype(str).str.extract(r"/(20\d{6})[_-]")[0]

    yyyymmdd_fallback = df["roi_dir"].astype(str).str.extract(r"/(20\d{6})[_-]")[0]
    yyyymmdd = yyyymmdd.fillna(yyyymmdd_fallback)

    df["plate_date_yyyymmdd"] = yyyymmdd

    df["plate_date"] = df["plate_date_yyyymmdd"].astype(str)

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

    # Derive fish_label robustly:
    #   - prefer /fish.../ segment anywhere in path
    #   - else prefer basename if it starts with fish...
    #   - else fall back to the prior heuristic
    def _fish_label_from_roi_dir(roi_dir: str):
        rd = str(roi_dir or "")
        m = re.search(r"/(fish[^/]+)(?:/|$)", rd, flags=re.I)
        if m:
            return m.group(1)
        base = rd.rstrip("/").split("/")[-1] if rd else ""
        if base.lower().startswith("fish"):
            return base
        # previous heuristic: folder before last
        m2 = re.search(r"/([^/]+)/[^/]+$", rd)
        return (m2.group(1) if m2 else pd.NA)

    if "fish" in df.columns:
        fish_label = df["fish"].astype(str).str.strip()
        fish_label = fish_label.replace({"nan": pd.NA, "none": pd.NA, "": pd.NA})
    else:
        fish_label = df["roi_dir"].astype(str).apply(_fish_label_from_roi_dir)

    df["fish_label"] = fish_label
    df["plate_group_key"] = df["dataset_slug_norm"].astype(str)

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
        i = _extract_int(r"(?:^|[^0-9])(roi)(\d+)", x.lower())
        if i is not None:
            return i
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
    # Ensure roi_index_within_slot is UNIQUE within each slot.
    # If duplicates exist (common in Denoising/*), renumber deterministically by roi_dir.
    def _renumber_group(g):
        # stable order
        g2 = g.sort_values(["roi_dir"], kind="mergesort").copy()
        g2["roi_index_within_slot"] = range(1, len(g2) + 1)
        return g2

    dup_mask = df.duplicated(subset=["plate_date_yyyymmdd","plate_id_filled","slot_id_filled","roi_index_within_slot"], keep=False)
    if dup_mask.any():
        df = (
            df.groupby(["plate_date_yyyymmdd","plate_id_filled","slot_id_filled"], dropna=False, group_keys=False)
              .apply(_renumber_group)
        )

    df["bruker_roi_id"] = (
        df["plate_date_yyyymmdd"].astype(str)
        + "-plate" + df["plate_id_filled"].astype(int).astype(str)
        + "-slot" + df["slot_id_filled"].astype(int).astype(str)
        + "-roi" + df["roi_index_within_slot"].astype(int).astype(str)
    )

    df["plate_code"] = [
        _plate_code(pd_, int(pid)) if _nonempty(pd_) else pd.NA
        for pd_, pid in zip(df["plate_date"], df["plate_id_filled"])
    ]
    df["slot_index"] = df["slot_id_filled"].astype(int)

    df["legacy_clutch_key"] = (
        df["plate_date_yyyymmdd"].astype(str)
        + "-plate" + df["plate_id_filled"].astype(int).astype(str)
        + "-slot" + df["slot_id_filled"].astype(int).astype(str)
    )

    if "Date born" in df.columns:
        df["date_born"] = pd.to_datetime(df["Date born"], errors="coerce").dt.date.astype("string")
    else:
        df["date_born"] = pd.NA

    if "ZF female genotype" in df.columns:
        df["parent_female_genotype_text"] = df["ZF female genotype"].astype("string")
    else:
        df["parent_female_genotype_text"] = pd.NA

    if "ZF male genotype" in df.columns:
        df["parent_male_genotype_text"] = df["ZF male genotype"].astype("string")
    else:
        df["parent_male_genotype_text"] = pd.NA

    df["treatment_rna_rna_base_code"] = df.get("treatment_rna_base_codes", pd.Series([pd.NA]*len(df))).apply(_split_pipe_first)
    df["treatment_plasmid_plasmid_base_code"] = df.get("treatment_plasmid_base_codes", pd.Series([pd.NA]*len(df))).apply(_split_pipe_first)

    df["mount_id_inferred"] = df.get("mount_id", pd.Series([pd.NA]*len(df)))
    df["mount_id_source"] = "from_v3"

    keep_roi_cols = [
        "plate_date",
        "mount_id",
        "mount_id_inferred",
        "plate_id_filled",
        "slot_id_filled",
        "roi_index_within_slot",
        "roi_dir",
        "bruker_roi_id",
        "plate_code",
        "slot_index",
        "legacy_clutch_key",
        "date_born",
        "parent_female_genotype_text",
        "parent_male_genotype_text",
        "treatment_rna_rna_base_code",
        "treatment_plasmid_plasmid_base_code",
    ]
    for c in keep_roi_cols:
        if c not in df.columns:
            df[c] = pd.NA

    df[keep_roi_cols].to_csv(OUT_ROI_V9_COMPAT, index=False)

    clutch_rows = (
        df.groupby("legacy_clutch_key", dropna=True)
          .agg(
              date_born=("date_born", lambda s: s.dropna().astype(str).head(1).tolist()[0] if len(s.dropna()) else pd.NA),
              parent_female_genotype_text=("parent_female_genotype_text", lambda s: s.dropna().astype(str).head(1).tolist()[0] if len(s.dropna()) else pd.NA),
              parent_male_genotype_text=("parent_male_genotype_text", lambda s: s.dropna().astype(str).head(1).tolist()[0] if len(s.dropna()) else pd.NA),
              treatment_rna_rna_base_code=("treatment_rna_rna_base_code", lambda s: s.dropna().astype(str).head(1).tolist()[0] if len(s.dropna()) else pd.NA),
              treatment_plasmid_plasmid_base_code=("treatment_plasmid_plasmid_base_code", lambda s: s.dropna().astype(str).head(1).tolist()[0] if len(s.dropna()) else pd.NA),
              plate_date=("plate_date", lambda s: s.dropna().astype(str).head(1).tolist()[0] if len(s.dropna()) else pd.NA),
              plate_id_filled=("plate_id_filled", lambda s: int(pd.to_numeric(s, errors="coerce").dropna().head(1).tolist()[0]) if len(pd.to_numeric(s, errors="coerce").dropna()) else pd.NA),
              slot_id_filled=("slot_id_filled", lambda s: int(pd.to_numeric(s, errors="coerce").dropna().head(1).tolist()[0]) if len(pd.to_numeric(s, errors="coerce").dropna()) else pd.NA),
              roi_count=("roi_dir", "size"),
              datasets=("dataset_slug_norm", lambda s: "|".join(sorted({x for x in s.dropna().astype(str) if x.strip()})) if len(s.dropna()) else pd.NA),
          )
          .reset_index()
    )

    clutch_rows["clutch_code"] = ["LCL-" + str(i+1).zfill(4) for i in range(len(clutch_rows))]
    clutch_rows.to_csv(OUT_CLUTCHES_V9, index=False)

    members = (
        df.merge(clutch_rows[["legacy_clutch_key","clutch_code"]], on="legacy_clutch_key", how="left")
          .groupby(["clutch_code","plate_code","slot_index"], dropna=True)
          .agg(roi_count=("roi_dir","size"))
          .reset_index()
    )
    members.to_csv(OUT_MEMBERSHIPS_V9, index=False)

    print("IN_DB", IN_DB)
    print("WROTE", OUT_ROI_V9_COMPAT)
    print("WROTE", OUT_CLUTCHES_V9)
    print("WROTE", OUT_MEMBERSHIPS_V9)
    print("ROI_ROWS", len(df), "UNIQUE_ROI_DIR", int(df["roi_dir"].nunique()))
    print("CLUTCH_ROWS", len(clutch_rows))
    print("MEMBERSHIP_ROWS", len(members))

if __name__ == "__main__":
    main()