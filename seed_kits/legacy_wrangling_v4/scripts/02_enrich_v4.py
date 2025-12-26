from __future__ import annotations

from pathlib import Path
import re
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]

V4_WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v4" / "working"

SLUG_RULES = V4_WORK / "slug_marker_rules_v4.csv"
V2_RAW = REPO_ROOT / "seed_kits" / "legacy_wrangling_v2" / "raw"
V2_WORKING = REPO_ROOT / "seed_kits" / "legacy_wrangling_v2" / "working"
AUTO = REPO_ROOT / "seed_kits" / "2025-11-15-121231-autoload"

IN_STRUCT = V4_WORK / "output_from_linking_v5.csv"

PARENT_MAP_XLSX = (REPO_ROOT / "seed_kits" / "legacy_wrangling_v2" / "raw" / "Unique_parent_names__mom_dad_combined__preview_dqm.xlsx")
PARENT_MAP_CSV  = (REPO_ROOT / "seed_kits" / "legacy_wrangling_v2" / "working" / "Unique_parent_names__mom_dad_combined__preview_dqm_from_raw.csv")
INJECTED_RNA_XLSX = V2_RAW / "Unique_injected_rna__preview_dqm.xlsx"
INJECTED_PLASMID_XLSX = V2_RAW / "Unique_injected_plasmid__preview_dqm.xlsx"
EXP_PATCH = V2_RAW / "experiment_hole_patch_v7.csv"

CONSTRUCTS = AUTO / "constructs_plasmid.csv"
TAGS = AUTO / "tags.xlsx"
ALIAS = AUTO / "alias.csv"

OUT_FULL = V4_WORK / "legacy_imaging_annotations_v9.csv"
OUT_DB = V4_WORK / "legacy_imaging_annotations_for_db_v9.csv"

# v4: ROI channel metadata (derived from foundation_dirs_depth6.txt)
# We pick the most recent "*-roi_channels_by_roi_root.tsv" in V4_WORK by timestamp prefix.
def _latest_work_tsv(pattern: str) -> Path | None:
    cands = sorted(V4_WORK.glob(pattern))
    return cands[-1] if cands else None

ROI_CHANNELS_TSV = _latest_work_tsv("*-roi_channels_by_roi_root.tsv")

def _norm_roi_path(s: object) -> str:
    x = "" if s is None else str(s)
    x = x.strip()
    x = x.replace("/clusterfs/vast/abcabc/", "")
    x = re.sub(r"^\./", "", x)
    return x

DATEFOLDER_RE = re.compile(r"^\d{8}_.+")
SPLIT_RE = re.compile(r"[\\/]+")
BASECODE_PAT = re.compile(r"(?i)(?:^|[^A-Z0-9])(MGCO|HC|PDQM)\s*[-_ ]?\s*(\d{1,4})(?=[^0-9]|$)")


def _extract_parent_allele_token(parent_text: object) -> str | None:
    if parent_text is None:
        return None
    s = str(parent_text).strip()
    if not s or s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return None
    m = re.search(r"(?i)\ballele\s+([A-Za-z0-9]+)\b", s)
    if not m:
        return None
    return m.group(1).strip().lower() or None

def _nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")


def _is_blank_series(s: pd.Series) -> pd.Series:
    return (
        s.isna()
        | s.astype(str).str.strip().eq("")
        | s.astype(str).str.strip().str.lower().isin(["nan", "none", "na", "n/a", "<na>"])
    )


def _norm_slug(s):
    if not _nonempty(s):
        return None
    return str(s).strip()


def _norm_label(s):
    if not _nonempty(s):
        return None
    s = str(s).strip().lower()
    s = re.sub(r"^\d{8}[_-]", "", s)
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("\\", "/")
    s = re.sub(r"[^a-z0-9]+", "", s)
    s = s.strip()
    return s or None


def _norm_injection_token(x):
    k = _norm_label(x)
    if not _nonempty(k):
        return None
    k = str(k)
    for suf in ["mrna", "rna", "plasmid", "dna", "crispr"]:
        if k.endswith(suf):
            k = k[: -len(suf)]
    return k or None


def _split_codes(v):
    if not _nonempty(v):
        return []
    s = str(v).strip()
    parts = re.split(r"[|,;]+", s)
    out = []
    for p in parts:
        p = p.strip()
        if p and p.lower() not in ("nan", "none", "na", "n/a", "<na>"):
            out.append(p)
    return out


def _uniq_join(parts):
    vals = []
    seen = set()
    for v in parts:
        if not _nonempty(v):
            continue
        for x in _split_codes(v):
            if x not in seen:
                seen.add(x)
                vals.append(x)
    return "|".join(vals) if vals else None


def _union_pipe(series: pd.Series):
    parts = []
    for v in series:
        if _nonempty(v):
            parts.append(str(v))
    return _uniq_join(parts)


def _coalesce(a, b):
    return b if _nonempty(b) else a


def _canon_basecode(prefix: str, num: str) -> str:
    p = str(prefix).upper()
    n = int(str(num))
    if p == "MGCO":
        return f"MGCO-{n}"
    if p == "HC":
        return f"HC-{n}"
    if p == "PDQM":
        return f"pDQM{n:03d}"
    return f"{p}-{n}"
def _extract_basecodes_from_raw(v) -> list[str]:
    if not _nonempty(v):
        return []
    hits = []
    s = str(v)
    for m in BASECODE_PAT.finditer(s):
        hits.append(_canon_basecode(m.group(1), m.group(2)))
    out = []
    seen = set()
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def _build_constructs_ft() -> pd.DataFrame:
    constructs = pd.read_csv(CONSTRUCTS, low_memory=False)
    tags = pd.read_excel(TAGS)
    alias = pd.read_csv(ALIAS, low_memory=False)

    tags_small = tags.copy()
    if "nickname" in tags_small.columns:
        tags_small = tags_small.rename(columns={"nickname": "tag_code"})
    if "localization" not in tags_small.columns:
        tags_small["localization"] = pd.NA
    tags_small = tags_small[["tag_code", "localization"]].drop_duplicates()

    constructs_ft = constructs.copy()
    for c in ["tag_code", "tag_pos", "fluor_code"]:
        if c not in constructs_ft.columns:
            constructs_ft[c] = pd.NA
    if "plasmid_code" not in constructs_ft.columns:
        raise SystemExit("02_enrich.py: constructs_plasmid.csv missing plasmid_code")

    constructs_ft = constructs_ft.merge(tags_small, on="tag_code", how="left")

    fluor_alias_map = {}
    if {"target_kind", "target_key", "alias"} <= set(alias.columns):
        sub = alias[alias["target_kind"].astype(str).str.lower().eq("fluor")].copy()
        for r in sub.itertuples(index=False):
            k = str(r.target_key).strip()
            a = str(r.alias).strip()
            if k and a and k not in fluor_alias_map:
                fluor_alias_map[k] = a

    constructs_ft["fluor_alias"] = constructs_ft["fluor_code"].astype(str).map(
        lambda x: fluor_alias_map.get(str(x), pd.NA)
    )
    return constructs_ft[
        ["plasmid_code", "fluor_code", "fluor_alias", "tag_code", "tag_pos", "localization"]
    ].drop_duplicates()


def _compute_marker_rollups(basecodes: str | None, constructs_ft: pd.DataFrame) -> dict:
    codes = _split_codes(basecodes)
    if not codes:
        return {
            "marker_fluor_codes": None,
            "marker_tag_codes": None,
            "marker_localizations": None,
            "marker_fusion_labels": None,
        }

    sub = constructs_ft[constructs_ft["plasmid_code"].isin(codes)].copy()
    if sub.empty:
        return {
            "marker_fluor_codes": None,
            "marker_tag_codes": None,
            "marker_localizations": None,
            "marker_fusion_labels": None,
        }

    fluor, tags, locs, fusions = [], [], [], []
    for r in sub.itertuples(index=False):
        fc = str(r.fluor_code).strip() if _nonempty(r.fluor_code) else ""
        ta = str(r.tag_code).strip() if _nonempty(r.tag_code) else ""
        tp = str(r.tag_pos).strip() if _nonempty(r.tag_pos) else ""
        lo = str(r.localization).strip() if _nonempty(r.localization) else ""

        if fc and fc not in fluor:
            fluor.append(fc)
        if ta and ta not in tags:
            tags.append(ta)
        if lo and lo not in locs:
            locs.append(lo)

        if fc and ta:
            lab = f"{fc}-{ta}({tp})" if tp else f"{fc}-{ta}"
        else:
            lab = fc or ta
        if lab and lab not in fusions:
            fusions.append(lab)

    return {
        "marker_fluor_codes": "|".join(fluor) if fluor else None,
        "marker_tag_codes": "|".join(tags) if tags else None,
        "marker_localizations": "|".join(locs) if locs else None,
        "marker_fusion_labels": "|".join(fusions) if fusions else None,
    }


def _parent_lookup() -> dict:
    pm = pd.read_excel(PARENT_MAP_XLSX, dtype=str).copy()
    pm.to_csv(PARENT_MAP_CSV, index=False)

    pm = pm.rename(columns={k: "parent_fish_name" for k in ["parent_name"] if k in pm.columns})

    need = ["parent_fish_name", "plasmid_base_code", "allele"]
    missing = [c for c in need if c not in pm.columns]
    if missing:
        raise SystemExit(f"[STOP] 02_enrich.py: parent map missing cols: {missing}")

    pm.columns = [str(c).strip() for c in pm.columns]
    pm["parent_norm"] = pm["parent_fish_name"].apply(_norm_label)

    # Build: parent_norm -> allele_token(lower) -> (base_code_pipe, allele_token)
    out: dict[str, dict[str, tuple[str | None, str | None]]] = {}

    for r in pm.itertuples(index=False):
        parent_norm = _norm_label(getattr(r, "parent_fish_name", None))
        if not parent_norm:
            continue

        bc_raw = getattr(r, "plasmid_base_code", None)
        bc = _uniq_join([bc_raw]) if _nonempty(bc_raw) else None

        allele_raw = getattr(r, "allele", None)
        if not _nonempty(allele_raw):
            continue
        a = str(allele_raw).strip()
        if a.endswith(".0") and a[:-2].isdigit():
            a = a[:-2]
        allele_tok = a.strip().lower()
        if not allele_tok:
            continue

        out.setdefault(parent_norm, {})
        prev = out[parent_norm].get(allele_tok)
        if prev is not None and prev != (bc, allele_tok):
            raise SystemExit(
                f"[STOP] parent map conflict for parent_norm={parent_norm!r} allele={allele_tok!r}: {prev} vs {(bc, allele_tok)}"
            )

        out[parent_norm][allele_tok] = (bc, allele_tok)

    return out


def _treatment_maps() -> tuple[dict, dict]:
    inj_rna = pd.read_excel(INJECTED_RNA_XLSX)
    inj_pl = pd.read_excel(INJECTED_PLASMID_XLSX)

    if "injected_rna" not in inj_rna.columns:
        raise SystemExit("02_enrich.py: injected_rna sheet missing injected_rna col")
    if "injected_plasmid" not in inj_pl.columns:
        raise SystemExit("02_enrich.py: injected_plasmid sheet missing injected_plasmid col")

    def canon_cell_to_codes(v) -> str | None:
        if not _nonempty(v):
            return None
        codes = _extract_basecodes_from_raw(v)
        return _uniq_join(codes) if codes else None

    rna_map = {}
    if "plasmid_base_code" in inj_rna.columns:
        for r in inj_rna.dropna(subset=["injected_rna"]).itertuples(index=False):
            k = _norm_injection_token(getattr(r, "injected_rna"))
            v_raw = getattr(r, "plasmid_base_code", None)
            v = canon_cell_to_codes(v_raw)
            if k and v and k not in rna_map:
                rna_map[k] = v

    pl_map = {}
    if "plasmid_base_code" in inj_pl.columns:
        for r in inj_pl.dropna(subset=["injected_plasmid"]).itertuples(index=False):
            k = _norm_injection_token(getattr(r, "injected_plasmid"))
            v_raw = getattr(r, "plasmid_base_code", None)
            v = canon_cell_to_codes(v_raw)
            if k and v and k not in pl_map:
                pl_map[k] = v

    return rna_map, pl_map
def _parse_injections_from_sheet_columns(df: pd.DataFrame, rna_map: dict, pl_map: dict) -> pd.DataFrame:
    df = df.copy()

    if "additional mRNAs injected" not in df.columns:
        df["additional mRNAs injected"] = pd.NA
    if "additional plasmids injected" not in df.columns:
        df["additional plasmids injected"] = pd.NA

    def map_any(v, maps):
        if not _nonempty(v):
            return None

        direct = _extract_basecodes_from_raw(v)
        if direct:
            return _uniq_join(direct)

        hits = []
        for part in re.split(r"[|,;]+", str(v)):
            part = part.strip()
            if not part:
                continue
            k = _norm_injection_token(part)
            if not k:
                continue
            for m in maps:
                bc = m.get(k)
                if bc:
                    hits.append(bc)
                    break
        return _uniq_join(hits) if hits else None

    df["tr_rna_from_imaging"] = df["additional mRNAs injected"].apply(lambda x: map_any(x, [rna_map, pl_map]))
    df["tr_plasmid_from_imaging"] = df["additional plasmids injected"].apply(lambda x: map_any(x, [pl_map, rna_map]))

    def _pipe_to_set(v):
        if not _nonempty(v):
            return set()
        return {x.strip() for x in re.split(r"[|,;]+", str(v)) if x.strip()}

    rna_sets = df["tr_rna_from_imaging"].apply(_pipe_to_set)
    pl_sets = df["tr_plasmid_from_imaging"].apply(_pipe_to_set)

    conflict_sets = [sorted(list(a & b)) for a, b in zip(rna_sets, pl_sets)]
    df["delivery_conflict_basecodes"] = ["|".join(xs) if xs else pd.NA for xs in conflict_sets]

    n_conflict_rows = int(df["delivery_conflict_basecodes"].map(_nonempty).sum())
    print(f"[DELIVERY_QC] n_rows_with_basecode_in_both_rna_and_plasmid_columns={n_conflict_rows}")

    return df


def _infer_treatment_rna_basecode_from_slug(slug_norm: str) -> str | None:
    s = str(slug_norm or "").strip().lower()
    if "mem-mito" in s:
        return "MGCO-1"
    if "peroxi" in s:
        return "MGCO-49"
    return None


def _apply_slug_marker_inference(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for c in [
        "dataset_slug_norm",
        "genotype_base_codes",
        "genotype_allele_codes",
        "treatment_rna_base_codes",
        "treatment_plasmid_base_codes",
    ]:
        if c not in df.columns:
            df[c] = pd.NA

    def _blank(v) -> bool:
        return not _nonempty(v)

    if not SLUG_RULES.exists():
        print(f"[SLUG_RULES] missing {SLUG_RULES} (skip)")
        return df

    rules = pd.read_csv(SLUG_RULES, low_memory=False).fillna("")
    rules.columns = [str(c).strip() for c in rules.columns]
    need_cols = [
        "dataset_slug_norm",
        "treatment_rna_base_codes",
        "treatment_plasmid_base_codes",
        "genotype_base_codes",
        "genotype_allele_codes",
        "rule_locked",
    ]
    miss = [c for c in need_cols if c not in rules.columns]
    if miss:
        raise SystemExit(f"[STOP] slug rules missing columns: {miss} in {SLUG_RULES}")

    rules["dataset_slug_norm"] = rules["dataset_slug_norm"].astype(str).str.strip().str.lower()
    rules = rules[rules["dataset_slug_norm"].astype(str).str.strip().ne("")].copy()
    rules["rule_locked"] = rules["rule_locked"].astype(str).str.strip().str.lower().isin(["1","t","true","y","yes"])

    rmap = {}
    for r in rules.itertuples(index=False):
        slug = str(getattr(r, "dataset_slug_norm")).strip().lower()
        rmap[slug] = {
            "treatment_rna_base_codes": str(getattr(r, "treatment_rna_base_codes")).strip(),
            "treatment_plasmid_base_codes": str(getattr(r, "treatment_plasmid_base_codes")).strip(),
            "genotype_base_codes": str(getattr(r, "genotype_base_codes")).strip(),
            "genotype_allele_codes": str(getattr(r, "genotype_allele_codes")).strip(),
            "rule_locked": bool(getattr(r, "rule_locked")),
        }

    # Apply rules:
    # - Only fill fields that are currently blank.
    # - Do NOT overwrite nonblank values.
    # - This is what fixes mem-mito: treatment_rna_base_codes gets filled even when genotype is present.
    slugs = df["dataset_slug_norm"].astype(str).str.strip().str.lower()

    n_fill_trna = 0
    n_fill_tpl = 0
    n_fill_gb = 0
    n_fill_ga = 0

    for slug, rule in rmap.items():
        mask = slugs.str.endswith(slug)
        if not int(mask.sum()):
            continue

        if rule["treatment_rna_base_codes"]:
            m2 = mask & df["treatment_rna_base_codes"].map(_blank)
            n = int(m2.sum())
            if n:
                df.loc[m2, "treatment_rna_base_codes"] = rule["treatment_rna_base_codes"]
                n_fill_trna += n

        if rule["treatment_plasmid_base_codes"]:
            m2 = mask & df["treatment_plasmid_base_codes"].map(_blank)
            n = int(m2.sum())
            if n:
                df.loc[m2, "treatment_plasmid_base_codes"] = rule["treatment_plasmid_base_codes"]
                n_fill_tpl += n

        if rule["genotype_base_codes"]:
            m2 = mask & df["genotype_base_codes"].map(_blank)
            n = int(m2.sum())
            if n:
                df.loc[m2, "genotype_base_codes"] = rule["genotype_base_codes"]
                n_fill_gb += n

        if rule["genotype_allele_codes"]:
            m2 = mask & df["genotype_allele_codes"].map(_blank)
            n = int(m2.sum())
            if n:
                df.loc[m2, "genotype_allele_codes"] = rule["genotype_allele_codes"]
                n_fill_ga += n

    print(f"[SLUG_RULES] filled_treatment_rna_base_codes={n_fill_trna}")
    print(f"[SLUG_RULES] filled_treatment_plasmid_base_codes={n_fill_tpl}")
    print(f"[SLUG_RULES] filled_genotype_base_codes={n_fill_gb}")
    print(f"[SLUG_RULES] filled_genotype_allele_codes={n_fill_ga}")

    return df

def _agg_exp_patch() -> pd.DataFrame:
    ep = pd.read_csv(EXP_PATCH, low_memory=False)
    required = {
        "dataset_slug",
        "genotype_base_codes",
        "genotype_allele_codes",
        "treatment_rna_base_codes",
        "treatment_plasmid_base_codes",
    }
    missing = required - set(ep.columns)
    if missing:
        raise SystemExit(f"02_enrich.py: experiment_hole_patch_v7.csv missing cols: {sorted(missing)}")

    ep["dataset_slug_norm"] = ep["dataset_slug"].apply(_norm_slug)

    return (
        ep.groupby("dataset_slug_norm", dropna=True)
        .agg(
            {
                "genotype_base_codes": _union_pipe,
                "genotype_allele_codes": _union_pipe,
                "treatment_rna_base_codes": _union_pipe,
                "treatment_plasmid_base_codes": _union_pipe,
            }
        )
        .reset_index()
        .rename(
            columns={
                "genotype_base_codes": "geno_base_codes_v9_exp",
                "genotype_allele_codes": "geno_alleles_v9_exp",
                "treatment_rna_base_codes": "treatment_rna_base_codes_v9_exp",
                "treatment_plasmid_base_codes": "treatment_plasmid_base_codes_v9_exp",
            }
        )
    )


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


def _step1a_fill_date_mount_from_roi_dir(df: pd.DataFrame) -> None:
    # Force string dtype up front so later assignments never hit float64 (pandas warning / future error).
    if "date_mount" not in df.columns:
        df["date_mount"] = pd.Series([pd.NA] * len(df), dtype="string")
    else:
        df["date_mount"] = df["date_mount"].astype("string")
    if "Data location" not in df.columns:
        df["Data location"] = pd.Series([pd.NA] * len(df), dtype="string")
    else:
        df["Data location"] = df["Data location"].astype("string")

    blank_loc = _is_blank_series(df["Data location"])
    blank_dat = _is_blank_series(df["date_mount"])
    both_blank = blank_loc & blank_dat

    n_both_blank_before = int(both_blank.sum())
    print(f"STEP1A n_both_blank_before(Data location & date_mount)={n_both_blank_before}")

    if n_both_blank_before:
        toks = df.loc[both_blank, "roi_dir"].map(_extract_datefolder_tokens)

        bad_idx = toks.index[toks.map(len).ne(1)].tolist()
        if bad_idx:
            if "dataset_slug_norm" in df.columns:
                is_analysis_test = (
                    df.loc[bad_idx, "dataset_slug_norm"]
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .eq("analysis_test")
                )
            else:
                is_analysis_test = df.loc[bad_idx, "roi_dir"].astype(str).str.contains(
                    r"/analysis_test/", case=False, na=False
                )

            allowed_idx = [i for i in bad_idx if bool(is_analysis_test.loc[i])]
            hard_idx = [i for i in bad_idx if i not in allowed_idx]

            cols = ["roi_dir"]
            if "link_source" in df.columns:
                cols.append("link_source")
            if "dataset_slug_norm" in df.columns:
                cols.append("dataset_slug_norm")

            show = df.loc[bad_idx, cols].copy()
            show["datefolder_tokens"] = toks.loc[bad_idx].map(lambda xs: ";".join(xs))
            print("STEP1A both-blank rows with non-deterministic roi_dir datefolder parsing:")
            print(show.head(200).to_string(index=True))
            print(f"STEP1A allowed_exceptions_analysis_test={len(allowed_idx)}")
            print(f"STEP1A hard_fail_rows={len(hard_idx)}")

            if hard_idx:
                raise SystemExit(
                    f"STEP1A ERROR: {len(hard_idx)} rows violate deterministic datefolder rule (expected exactly 1 token)"
                )

        fill_idx = toks.index[toks.map(len).eq(1)].tolist()
        if fill_idx:
            datefolder = toks.loc[fill_idx].map(lambda xs: xs[0])
            yyyymmdd = datefolder.map(lambda x: str(x)[:8])
            iso = yyyymmdd.map(_yyyymmdd_to_iso)
            df.loc[fill_idx, "date_mount"] = iso
            print(f"STEP1A n_date_mount_filled_from_roi_dir={len(fill_idx)}")

    blank_loc_after = _is_blank_series(df["Data location"])
    blank_dat_after = _is_blank_series(df["date_mount"])
    both_blank_after = blank_loc_after & blank_dat_after
    n_both_blank_after = int(both_blank_after.sum())
    print(f"STEP1A n_both_blank_after(Data location & date_mount)={n_both_blank_after}")

    non_test_after = both_blank_after
    if "dataset_slug_norm" in df.columns:
        non_test_after = both_blank_after & ~df["dataset_slug_norm"].astype(str).str.strip().str.lower().eq(
            "analysis_test"
        )

    if int(non_test_after.sum()) != 0:
        show_cols = [c for c in ["roi_dir", "date_mount", "Data location", "link_source", "dataset_slug_norm"] if c in df.columns]
        print(df.loc[non_test_after, show_cols].head(200).to_string(index=False))
        raise SystemExit(
            "STEP1A ERROR: refusing to continue with both Data location and date_mount blank (non-analysis_test rows)"
        )


def main() -> None:
    if not IN_STRUCT.exists():
        raise SystemExit(f"missing structural CSV (run 01_link.py first): {IN_STRUCT}")
    for p in [
        PARENT_MAP_CSV,
        INJECTED_RNA_XLSX,
        INJECTED_PLASMID_XLSX,
        EXP_PATCH,
        CONSTRUCTS,
        TAGS,
        ALIAS,
    ]:
        if not p.exists():
            raise SystemExit(f"missing required input: {p}")

    df = pd.read_csv(IN_STRUCT, low_memory=False)

    # Pass-through: allow arbitrary free-text labels from imaging sheet to flow into enriched outputs
    if "free_text_label" not in df.columns:
        df["free_text_label"] = pd.NA
    if "roi_dir" not in df.columns:
        raise SystemExit("02_enrich.py: missing roi_dir in IN_STRUCT")
    if "roi_experiment_folder" not in df.columns:
        raise SystemExit("02_enrich.py: missing roi_experiment_folder in IN_STRUCT")

    df = df.copy()

    # v4: attach ROI channel metadata (cams/channels/wavelengths/exts) derived from filesystem crawl
    df["roi_dir_norm"] = df["roi_dir"].map(_norm_roi_path)

    if ROI_CHANNELS_TSV is None or not ROI_CHANNELS_TSV.exists():
        print("[WARN] ROI_CHANNELS_TSV not found; skipping ROI channel join")
    else:
        df_ch = pd.read_csv(ROI_CHANNELS_TSV, sep="\t", low_memory=False)
        if "roi_root" not in df_ch.columns:
            raise SystemExit(f"[STOP] ROI_CHANNELS_TSV missing roi_root column: {ROI_CHANNELS_TSV}")
        df_ch = df_ch.copy()
        df_ch["roi_root_norm"] = df_ch["roi_root"].map(_norm_roi_path)

        keep = [c for c in ["roi_root_norm", "cams", "channels", "wavelengths_nm", "file_exts", "n_paths"] if c in df_ch.columns]
        df = df.merge(df_ch[keep], left_on="roi_dir_norm", right_on="roi_root_norm", how="left")

        # Normalize empty strings to NA for consistency
        for c in ["cams", "channels", "wavelengths_nm", "file_exts"]:
            if c in df.columns:
                df[c] = df[c].astype("string").replace("", pd.NA)

    df["dataset_slug"] = df["roi_experiment_folder"].astype("string")
    df["dataset_slug_norm"] = df["dataset_slug"].apply(_norm_slug)
    # v4: experiment-level genotype overrides (deterministic fallback)
    EXP_OVR = V4_WORK / "experiment_genotype_overrides_v4.tsv"
    if EXP_OVR.exists():
        ovr = pd.read_csv(EXP_OVR, sep="\t", low_memory=False)
        ovr.columns = [str(c).strip() for c in ovr.columns]
        need = ["roi_experiment_folder", "genotype_base_codes_override", "genotype_allele_codes_override"]
        miss = [c for c in need if c not in ovr.columns]
        if miss:
            raise SystemExit(f"[STOP] experiment overrides TSV missing columns {miss}: {EXP_OVR}")

        ovr = ovr[need].copy()
        for c in ["roi_experiment_folder", "genotype_base_codes_override", "genotype_allele_codes_override"]:
            ovr[c] = ovr[c].astype("string")

        df = df.merge(
            ovr.rename(
                columns={
                    "roi_experiment_folder": "dataset_slug",
                    "genotype_base_codes_override": "geno_base_codes_override_exp",
                    "genotype_allele_codes_override": "geno_alleles_override_exp",
                }
            ),
            on="dataset_slug",
            how="left",
        )

        def _blank(x) -> bool:
            if x is None:
                return True
            s = str(x).strip()
            return s == "" or s.lower() in ("nan", "none", "na", "n/a", "<na>")

        if "genotype_base_codes" not in df.columns:
            df["genotype_base_codes"] = pd.NA
        if "genotype_allele_codes" not in df.columns:
            df["genotype_allele_codes"] = pd.NA

        fill_base = df["genotype_base_codes"].map(_blank) & ~df["geno_base_codes_override_exp"].map(_blank)
        fill_alle = df["genotype_allele_codes"].map(_blank) & ~df["geno_alleles_override_exp"].map(_blank)

        n_fill_base = int(fill_base.sum())
        n_fill_alle = int(fill_alle.sum())

        if n_fill_base:
            df.loc[fill_base, "genotype_base_codes"] = df.loc[fill_base, "geno_base_codes_override_exp"]
        if n_fill_alle:
            df.loc[fill_alle, "genotype_allele_codes"] = df.loc[fill_alle, "geno_alleles_override_exp"]

        print(f"[EXP_OVERRIDES] filled genotype_base_codes={n_fill_base} genotype_allele_codes={n_fill_alle} from {EXP_OVR}")
    else:
        print(f"[WARN] EXP_OVR not found; skipping experiment genotype overrides: {EXP_OVR}")

    parent_map = _parent_lookup()
    rna_map, pl_map = _treatment_maps()
    df = _parse_injections_from_sheet_columns(df, rna_map=rna_map, pl_map=pl_map)
    exp_slug_agg = _agg_exp_patch()

    def parent_codes_from_text(x):
        k = _norm_label(x)
        if not k:
            return (None, None)

        bucket = parent_map.get(k)
        if not bucket:
            return (None, None)

        # If there's only one allele option for this normalized parent, take it.
        if len(bucket) == 1:
            (_bc, _alle) = next(iter(bucket.values()))
            return (_bc, _alle)

        # Otherwise, require disambiguation via the allele token embedded in the parent text.
        allele_tok = _extract_parent_allele_token(x)
        if allele_tok and allele_tok in bucket:
            return bucket[allele_tok]

        choices = ", ".join(sorted(bucket.keys()))
        raise SystemExit(
            f"[STOP] ambiguous parent mapping for parent_text={str(x)!r} parent_norm={k!r}. "
            f"Found {len(bucket)} allele variants in parent map: {choices}. "
            f"Could not disambiguate (missing/unknown 'allele NNN' token in text)."
        )

    if "ZF female genotype" not in df.columns:
        df["ZF female genotype"] = pd.NA
    if "ZF male genotype" not in df.columns:
        df["ZF male genotype"] = pd.NA

    f_base, f_alle = zip(*df["ZF female genotype"].apply(parent_codes_from_text))
    m_base, m_alle = zip(*df["ZF male genotype"].apply(parent_codes_from_text))
    df["geno_base_from_imaging"] = [_uniq_join([a, b]) for a, b in zip(f_base, m_base)]
    df["geno_alle_from_imaging"] = [_uniq_join([a, b]) for a, b in zip(f_alle, m_alle)]

    df = df.merge(exp_slug_agg, on="dataset_slug_norm", how="left")

    for c in [
        "genotype_base_codes",
        "genotype_allele_codes",
        "treatment_rna_base_codes",
        "treatment_plasmid_base_codes",
    ]:
        if c not in df.columns:
            df[c] = pd.NA

    df["genotype_base_codes"] = [
        _coalesce(a, b) for a, b in zip(df["geno_base_from_imaging"], df.get("geno_base_codes_v9_exp"))
    ]
    df["genotype_allele_codes"] = [
        _coalesce(a, b) for a, b in zip(df["geno_alle_from_imaging"], df.get("geno_alleles_v9_exp"))
    ]
    
    df["treatment_rna_base_codes"] = df["tr_rna_from_imaging"]
    df["treatment_plasmid_base_codes"] = df["tr_plasmid_from_imaging"]

    df = _apply_slug_marker_inference(df)

    constructs_ft = _build_constructs_ft()

    geno_roll = df["genotype_base_codes"].apply(lambda x: _compute_marker_rollups(x, constructs_ft))
    df["genotype_marker_fluor_codes"] = geno_roll.apply(lambda d: d["marker_fluor_codes"])
    df["genotype_marker_tag_codes"] = geno_roll.apply(lambda d: d["marker_tag_codes"])
    df["genotype_marker_localizations"] = geno_roll.apply(lambda d: d["marker_localizations"])
    df["genotype_marker_fusion_labels"] = geno_roll.apply(lambda d: d["marker_fusion_labels"])

    tr_roll = df["treatment_rna_base_codes"].apply(lambda x: _compute_marker_rollups(x, constructs_ft))
    df["treatment_rna_marker_fluor_codes"] = tr_roll.apply(lambda d: d["marker_fluor_codes"])
    df["treatment_rna_marker_tag_codes"] = tr_roll.apply(lambda d: d["marker_tag_codes"])
    df["treatment_rna_marker_localizations"] = tr_roll.apply(lambda d: d["marker_localizations"])
    df["treatment_rna_marker_fusion_labels"] = tr_roll.apply(lambda d: d["marker_fusion_labels"])

    tp_roll = df["treatment_plasmid_base_codes"].apply(lambda x: _compute_marker_rollups(x, constructs_ft))
    df["treatment_plasmid_marker_fluor_codes"] = tp_roll.apply(lambda d: d["marker_fluor_codes"])
    df["treatment_plasmid_marker_tag_codes"] = tp_roll.apply(lambda d: d["marker_tag_codes"])
    df["treatment_plasmid_marker_localizations"] = tp_roll.apply(lambda d: d["marker_localizations"])
    df["treatment_plasmid_marker_fusion_labels"] = tp_roll.apply(lambda d: d["marker_fusion_labels"])
    def _blank(v) -> bool:
        return not _nonempty(v)

    df["include_in_db"] = True
    if "dataset_slug_norm" in df.columns:
        df.loc[df["dataset_slug_norm"].astype(str).str.strip().str.lower().eq("analysis_test"), "include_in_db"] = False

    def _blank(v) -> bool:
        return not _nonempty(v)

    ft = df.get("free_text_label", pd.Series([pd.NA] * len(df)))
    has_free_text = ~ft.map(_blank)

    df.loc[df["genotype_base_codes"].map(_blank) & ~has_free_text, "include_in_db"] = False

    ft = df.get("free_text_label", pd.Series([pd.NA] * len(df)))
    has_free_text = ~ft.map(_blank)

    bad = df["include_in_db"].astype(bool) & df["genotype_base_codes"].map(_blank) & ~has_free_text
    n_bad = int(bad.sum())
    if n_bad:
        cols = [c for c in [
            "date_experiment",
            "roi_dir",
            "dataset_slug_norm",
            "free_text_label",
            "ZF female genotype",
            "ZF male genotype",
            "additional plasmids injected",
            "additional mRNAs injected",
            "treatment_plasmid_base_codes",
            "treatment_rna_base_codes",
            "genotype_base_codes",
            "include_in_db",
        ] if c in df.columns]
        print(df.loc[bad, cols].head(80).to_string(index=False))
        raise SystemExit(f"STOP: {n_bad} row(s) have include_in_db=True but blank genotype_base_codes AND no free_text_label")
    _step1a_fill_date_mount_from_roi_dir(df)

    # Output strategy:
    #  - OUT_FULL: all rows
    #  - OUT_DB_ALL_ROIS: all ROIs we can load (exclude analysis_test only)
    #  - OUT_DB: rows eligible for clutch/genotype/treatment workflows (must have genotype_base_codes)
    OUT_DB_ALL_ROIS = OUT_DB.parent / "legacy_imaging_annotations_for_db_v9_all_rois.csv"

    df.to_csv(OUT_FULL, index=False)

    all_rois = df.copy()
    if "dataset_slug_norm" in all_rois.columns:
        all_rois = all_rois[~all_rois["dataset_slug_norm"].astype(str).str.strip().str.lower().eq("analysis_test")].copy()
    all_rois.to_csv(OUT_DB_ALL_ROIS, index=False)

    # Ensure free_text_label is present on DB output
    try:
        _tmp = locals().get('out_db', None)
        if _tmp is not None and hasattr(_tmp, 'columns'):
            if 'free_text_label' not in _tmp.columns:
                _tmp['free_text_label'] = df.get('free_text_label', pd.NA)
    except Exception:
        pass

    df[df["include_in_db"]].to_csv(OUT_DB, index=False)

    print("IN_STRUCT", IN_STRUCT)
    print("ROWS", len(df), "UNIQUE_ROI_DIR", int(df["roi_dir"].nunique()))
    print("WROTE", OUT_FULL)
    print("WROTE", OUT_DB)


if __name__ == "__main__":
    main()
