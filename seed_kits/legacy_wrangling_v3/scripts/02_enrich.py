from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]

V3_WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v3" / "working"
V2_RAW = REPO_ROOT / "seed_kits" / "legacy_wrangling_v2" / "raw"
AUTO = REPO_ROOT / "seed_kits" / "2025-11-15-121231-autoload"

IN_STRUCT = V3_WORK / "output_from_linking_v5.csv"

PARENT_MAP_CSV = V2_RAW / "Unique_parent_names__mom_dad_combined__preview_dqm_v5.csv"
INJECTED_RNA_XLSX = V2_RAW / "Unique_injected_rna__preview_dqm.xlsx"
INJECTED_PLASMID_XLSX = V2_RAW / "Unique_injected_plasmid__preview_dqm.xlsx"
EXP_PATCH = V2_RAW / "experiment_hole_patch_v7.csv"

CONSTRUCTS = AUTO / "constructs_plasmid.csv"
TAGS = AUTO / "tags.xlsx"
ALIAS = AUTO / "alias.csv"

OUT_FULL = V3_WORK / "legacy_imaging_annotations_v9.csv"
OUT_DB = V3_WORK / "legacy_imaging_annotations_for_db_v9.csv"


def _nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")


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

    constructs_ft["fluor_alias"] = constructs_ft["fluor_code"].astype(str).map(lambda x: fluor_alias_map.get(str(x), pd.NA))
    return constructs_ft[["plasmid_code", "fluor_code", "fluor_alias", "tag_code", "tag_pos", "localization"]].drop_duplicates()


def _parent_lookup() -> dict:
    pm = pd.read_csv(PARENT_MAP_CSV, low_memory=False).copy()
    pm = pm.rename(columns={k: "parent_fish_name" for k in ["parent_name"] if k in pm.columns})
    need = ["parent_fish_name", "plasmid_base_code", "allele"]
    missing = [c for c in need if c not in pm.columns]
    if missing:
        raise SystemExit(f"02_enrich.py: parent map missing cols: {missing}")
    pm["parent_norm"] = pm["parent_fish_name"].apply(_norm_label)
    agg = (
        pm.groupby("parent_norm", dropna=True)
        .agg({"plasmid_base_code": _union_pipe, "allele": _union_pipe})
        .reset_index()
    )
    return {r.parent_norm: (r.plasmid_base_code, r.allele) for r in agg.itertuples(index=False)}


def _treatment_maps() -> tuple[dict, dict]:
    inj_rna = pd.read_excel(INJECTED_RNA_XLSX)
    inj_pl = pd.read_excel(INJECTED_PLASMID_XLSX)

    if not {"injected_rna", "plasmid_base_code"} <= set(inj_rna.columns):
        raise SystemExit("02_enrich.py: injected_rna sheet missing required cols")
    if not {"injected_plasmid", "plasmid_base_code"} <= set(inj_pl.columns):
        raise SystemExit("02_enrich.py: injected_plasmid sheet missing required cols")

    rna_map = {}
    for r in inj_rna.dropna(subset=["injected_rna", "plasmid_base_code"]).itertuples(index=False):
        k = _norm_label(r.injected_rna)
        v = str(r.plasmid_base_code).strip()
        if k and v and k not in rna_map:
            rna_map[k] = v

    pl_map = {}
    for r in inj_pl.dropna(subset=["injected_plasmid", "plasmid_base_code"]).itertuples(index=False):
        k = _norm_label(r.injected_plasmid)
        v = str(r.plasmid_base_code).strip()
        if k and v and k not in pl_map:
            pl_map[k] = v

    return rna_map, pl_map


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
        .agg({
            "genotype_base_codes": _union_pipe,
            "genotype_allele_codes": _union_pipe,
            "treatment_rna_base_codes": _union_pipe,
            "treatment_plasmid_base_codes": _union_pipe,
        })
        .reset_index()
        .rename(columns={
            "genotype_base_codes": "geno_base_codes_v9_exp",
            "genotype_allele_codes": "geno_alleles_v9_exp",
            "treatment_rna_base_codes": "treatment_rna_base_codes_v9_exp",
            "treatment_plasmid_base_codes": "treatment_plasmid_base_codes_v9_exp",
        })
    )


def _compute_marker_rollups(basecodes: str | None, constructs_ft: pd.DataFrame) -> dict:
    codes = _split_codes(basecodes)
    if not codes:
        return {"marker_fluor_codes": None, "marker_tag_codes": None, "marker_localizations": None, "marker_fusion_labels": None}

    sub = constructs_ft[constructs_ft["plasmid_code"].isin(codes)].copy()
    if sub.empty:
        return {"marker_fluor_codes": None, "marker_tag_codes": None, "marker_localizations": None, "marker_fusion_labels": None}

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


def main() -> None:
    if not IN_STRUCT.exists():
        raise SystemExit(f"missing structural CSV (run 01_link.py first): {IN_STRUCT}")
    for p in [PARENT_MAP_CSV, INJECTED_RNA_XLSX, INJECTED_PLASMID_XLSX, EXP_PATCH, CONSTRUCTS, TAGS, ALIAS]:
        if not p.exists():
            raise SystemExit(f"missing required input: {p}")

    df = pd.read_csv(IN_STRUCT, low_memory=False)

    if "roi_dir" not in df.columns:
        raise SystemExit("02_enrich.py: missing roi_dir in IN_STRUCT")
    if "roi_experiment_folder" not in df.columns:
        raise SystemExit("02_enrich.py: missing roi_experiment_folder in IN_STRUCT")

    df = df.copy()
    df["dataset_slug"] = df["roi_experiment_folder"].astype("string")
    df["dataset_slug_norm"] = df["dataset_slug"].apply(_norm_slug)

    parent_map = _parent_lookup()
    rna_map, pl_map = _treatment_maps()
    exp_slug_agg = _agg_exp_patch()

    def parent_codes_from_text(x):
        k = _norm_label(x)
        if not k:
            return (None, None)
        return parent_map.get(k, (None, None))

    if "ZF female genotype" not in df.columns:
        df["ZF female genotype"] = pd.NA
    if "ZF male genotype" not in df.columns:
        df["ZF male genotype"] = pd.NA

    f_base, f_alle = zip(*df["ZF female genotype"].apply(parent_codes_from_text))
    m_base, m_alle = zip(*df["ZF male genotype"].apply(parent_codes_from_text))

    df["geno_base_from_imaging"] = [_uniq_join([a, b]) for a, b in zip(f_base, m_base)]
    df["geno_alle_from_imaging"] = [_uniq_join([a, b]) for a, b in zip(f_alle, m_alle)]

    def map_treat_names_to_basecodes(v, m):
        if not _nonempty(v):
            return None
        hits = []
        for part in re.split(r"[|,;]+", str(v)):
            k = _norm_label(part)
            if not k:
                continue
            bc = m.get(k)
            if bc:
                hits.append(bc)
        return _uniq_join(hits)

    if "additional mRNAs injected" not in df.columns:
        df["additional mRNAs injected"] = pd.NA
    if "additional plasmids injected" not in df.columns:
        df["additional plasmids injected"] = pd.NA

    df["tr_rna_from_imaging"] = df["additional mRNAs injected"].apply(lambda x: map_treat_names_to_basecodes(x, rna_map))
    df["tr_plasmid_from_imaging"] = df["additional plasmids injected"].apply(lambda x: map_treat_names_to_basecodes(x, pl_map))

    df = df.merge(exp_slug_agg, on="dataset_slug_norm", how="left")
        # ------------------------------------------------------------------
    # Ensure final “output” columns exist BEFORE any override code
    # ------------------------------------------------------------------
    for c in [
        "genotype_base_codes",
        "genotype_allele_codes",
        "treatment_rna_base_codes",
        "treatment_plasmid_base_codes",
    ]:
        if c not in df.columns:
            df[c] = pd.NA
        # ---- v3 inference overrides (treatments, NOT genotype) ----
    # These are dataset-level inferences when BOTH genotype + treatments are missing.
    # We write to treatment_*_base_codes only; genotype_* stays as-is unless derived elsewhere.

    def _ensure_pipe(existing: str | None, add: str | None) -> str | None:
        if not _nonempty(add):
            return existing
        if not _nonempty(existing):
            return add
        parts = []
        seen = set()
        for v in re.split(r"[|,;]+", str(existing)) + re.split(r"[|,;]+", str(add)):
            v = str(v).strip()
            if v and v.lower() not in ("nan","none","na","n/a","<na>") and v not in seen:
                seen.add(v)
                parts.append(v)
        return "|".join(parts) if parts else None

    def _code_kind(code: str) -> str | None:
        if not _nonempty(code):
            return None
        code = str(code).strip()

        # read constructs once (fast enough for our tiny override set)
        c = pd.read_csv(CONSTRUCTS, low_memory=False)
        if "plasmid_code" not in c.columns:
            return None

        sub = c[c["plasmid_code"].astype(str).str.strip().eq(code)]
        if sub.empty:
            return None

        rna = str(sub.get("used_for_injection_rna", pd.Series([""])).iloc[0]).strip()
        plasmid = str(sub.get("used_for_injection_plasmid", pd.Series([""])).iloc[0]).strip()

        is_rna = rna in ("1","True","true","TRUE")
        is_pl  = plasmid in ("1","True","true","TRUE")

        if is_rna:
            return "rna"
        if is_pl:
            return "plasmid"
        return None

    def _apply_inferred_treatments_for_slug(slug: str, codes: list[str], reason: str):
        nonlocal df
        mask = df["dataset_slug_norm"].astype(str).str.strip().eq(slug)
        if not mask.any():
            return

        # Only apply when all four are missing across the slug (same condition as your QC “need both”)
        sub = df.loc[mask]
        def _col_nonempty(col):
            return sub[col].map(_nonempty).mean() if col in sub.columns else 0.0
        if not (
            (_col_nonempty("genotype_base_codes") == 0.0) and
            (_col_nonempty("genotype_allele_codes") == 0.0) and
            (_col_nonempty("treatment_rna_base_codes") == 0.0) and
            (_col_nonempty("treatment_plasmid_base_codes") == 0.0)
        ):
            return

        # annotate
        df.loc[mask, "override_applied"] = True
        df.loc[mask, "override_reason"] = reason

        # place inferred codes into the right treatment column
        for code in codes:
            kind = _code_kind(code)
            if kind == "rna":
                df.loc[mask, "treatment_rna_base_codes"] = df.loc[mask, "treatment_rna_base_codes"].apply(lambda x: _ensure_pipe(x, code))
            elif kind == "plasmid":
                df.loc[mask, "treatment_plasmid_base_codes"] = df.loc[mask, "treatment_plasmid_base_codes"].apply(lambda x: _ensure_pipe(x, code))

    # Ensure these columns exist for downstream QC
    if "override_applied" not in df.columns:
        df["override_applied"] = False
    if "override_reason" not in df.columns:
        df["override_reason"] = pd.NA

    # Apply overrides
    _apply_inferred_treatments_for_slug("20251107_mem-mito", ["MGCO-01"], "inferred:mito_mStayGold_2xCox8A")
    _apply_inferred_treatments_for_slug("20251112_mem-mito", ["MGCO-01"], "inferred:mito_mStayGold_2xCox8A")
    _apply_inferred_treatments_for_slug("20251029_peroxi",   ["MGCO-49"], "inferred:peroxisome_mStayGold_SKL")

        # ─────────────────────────────────────────────────────────────────────
    # OVERRIDE: mem-mito slug family backfill (when genotype+treatment missing)
    #
    # Goal:
    #   If a mem-mito slug has NO genotype_base/allele AND NO treatment rna/plasmid,
    #   copy those fields from a well-annotated mem-mito donor slug.
    #
    # Provenance columns:
    #   mem_mito_override_applied, mem_mito_donor_slug, mem_mito_donor_reason
    # ─────────────────────────────────────────────────────────────────────

    def _nonempty_str(x) -> bool:
        if x is None:
            return False
        if isinstance(x, float) and pd.isna(x):
            return False
        s = str(x).strip().lower()
        return s not in ("", "nan", "none", "na", "n/a", "<na>")

    def _needs_all_four(row) -> bool:
        return (
            (not _nonempty_str(row.get("geno_base_from_imaging"))) and
            (not _nonempty_str(row.get("geno_alle_from_imaging"))) and
            (not _nonempty_str(row.get("tr_rna_from_imaging"))) and
            (not _nonempty_str(row.get("tr_plasmid_from_imaging"))) and
            (not _nonempty_str(row.get("geno_base_codes_v9_exp"))) and
            (not _nonempty_str(row.get("geno_alleles_v9_exp"))) and
            (not _nonempty_str(row.get("treatment_rna_base_codes_v9_exp"))) and
            (not _nonempty_str(row.get("treatment_plasmid_base_codes_v9_exp")))
        )

    def _parse_yyyymmdd_prefix(slug: str) -> int | None:
        if not _nonempty_str(slug):
            return None
        m = re.match(r"^(20\d{6})[_-]", str(slug))
        if not m:
            return None
        try:
            return int(m.group(1))
        except Exception:
            return None

    def _coverage_score(sub: pd.DataFrame) -> tuple[int, int]:
        # returns (score, n_rows_used)
        # score weights: genotype base 4, allele 2, tr_rna 2, tr_pl 2
        if sub.empty:
            return (0, 0)
        def frac(col):
            if col not in sub.columns:
                return 0.0
            return float(sub[col].map(_nonempty_str).mean())
        s = 0
        s += (frac("geno_base_from_imaging") > 0) * 4
        s += (frac("geno_alle_from_imaging") > 0) * 2
        s += (frac("tr_rna_from_imaging") > 0) * 2
        s += (frac("tr_plasmid_from_imaging") > 0) * 2
        # fallbacks (exp_patch)
        s += (frac("geno_base_codes_v9_exp") > 0) * 4
        s += (frac("geno_alleles_v9_exp") > 0) * 2
        s += (frac("treatment_rna_base_codes_v9_exp") > 0) * 2
        s += (frac("treatment_plasmid_base_codes_v9_exp") > 0) * 2
        return (int(s), int(len(sub)))

    # Ensure provenance cols exist
    if "mem_mito_override_applied" not in df.columns:
        df["mem_mito_override_applied"] = False
    if "mem_mito_donor_slug" not in df.columns:
        df["mem_mito_donor_slug"] = pd.NA
    if "mem_mito_donor_reason" not in df.columns:
        df["mem_mito_donor_reason"] = pd.NA

    # Work at slug level
    if "dataset_slug_norm" in df.columns:
        slug_series = df["dataset_slug_norm"].astype("string")
        is_mem_mito = slug_series.str.contains("mem-mito", case=False, na=False)

        # Identify which mem-mito slugs need backfill (all rows empty)
        mem = df[is_mem_mito].copy()
        if not mem.empty:
            # map slug -> needs_backfill
            needs_by_slug = (
                mem.groupby("dataset_slug_norm", dropna=False)
                   .apply(lambda g: bool(g.apply(_needs_all_four, axis=1).all()))
                   .to_dict()
            )

            need_slugs = [k for k, v in needs_by_slug.items() if v and _nonempty_str(k)]
            if need_slugs:
                # Build donor candidates among mem-mito slugs that have ANY enrichment
                donors = []
                for slug, g in mem.groupby("dataset_slug_norm", dropna=False):
                    slug_s = str(slug)
                    if not _nonempty_str(slug_s):
                        continue
                    if slug_s in need_slugs:
                        continue
                    score, nrows = _coverage_score(g)
                    if score <= 0:
                        continue
                    donors.append((slug_s, score, nrows, _parse_yyyymmdd_prefix(slug_s)))

                # Helper to choose donor for a target slug
                def choose_donor_for(target_slug: str) -> tuple[str | None, str | None]:
                    # Preferred donor slug if available and has coverage
                    preferred = "20251106_mem-mito"
                    for s, sc, n, d in donors:
                        if s == preferred:
                            return (s, "preferred:20251106_mem-mito")
                    # Otherwise choose best by (score desc, date distance asc, nrows desc, slug asc)
                    tdate = _parse_yyyymmdd_prefix(target_slug)
                    ranked = []
                    for s, sc, n, d in donors:
                        if tdate is None or d is None:
                            daydist = 10**9
                        else:
                            daydist = abs(d - tdate)
                        ranked.append((sc, -n, -daydist, s))  # note: -daydist makes closer = larger; invert later
                    if not ranked:
                        return (None, "no_donor_found")
                    # Sort: score desc, nrows desc, daydist asc, slug asc
                    ranked2 = sorted(
                        [(sc, nneg, daydistneg, s) for (sc, nneg, daydistneg, s) in ranked],
                        key=lambda x: (-x[0], x[1], -x[2], x[3])
                    )
                    best_slug = ranked2[0][3]
                    return (best_slug, "auto_best_by(score,rows,closest_date)")

                # Compute donor “final” values (what we actually copy) from df columns AFTER merge(exp_slug_agg)
                def donor_values(donor_slug: str) -> dict:
                    g = df[df["dataset_slug_norm"].astype(str) == donor_slug].copy()
                    if g.empty:
                        return {}
                    def first_nonempty(col):
                        if col not in g.columns:
                            return None
                        vals = (
                            g[col]
                            .dropna()
                            .astype(str)
                            .map(lambda x: x.strip())
                            .loc[lambda s: ~s.str.lower().isin(["", "nan", "none", "na", "n/a", "<na>"])]
                        )
                        return vals.iloc[0] if len(vals) else None
                    return {
                        "geno_base_from_imaging": first_nonempty("geno_base_from_imaging"),
                        "geno_alle_from_imaging": first_nonempty("geno_alle_from_imaging"),
                        "tr_rna_from_imaging": first_nonempty("tr_rna_from_imaging"),
                        "tr_plasmid_from_imaging": first_nonempty("tr_plasmid_from_imaging"),
                        "geno_base_codes_v9_exp": first_nonempty("geno_base_codes_v9_exp"),
                        "geno_alleles_v9_exp": first_nonempty("geno_alleles_v9_exp"),
                        "treatment_rna_base_codes_v9_exp": first_nonempty("treatment_rna_base_codes_v9_exp"),
                        "treatment_plasmid_base_codes_v9_exp": first_nonempty("treatment_plasmid_base_codes_v9_exp"),
                    }

                # Apply per target slug
                for tslug in need_slugs:
                    donor_slug, reason = choose_donor_for(tslug)
                    if not donor_slug:
                        continue
                    dv = donor_values(donor_slug)
                    if not dv:
                        continue

                    m = df["dataset_slug_norm"].astype(str).eq(tslug)
                    if not m.any():
                        continue

                    # Only fill into the raw per-row fields (imaging-derived and exp_patch-derived).
                    # Final coalesce happens later.
                    for col in [
                        "geno_base_from_imaging",
                        "geno_alle_from_imaging",
                        "tr_rna_from_imaging",
                        "tr_plasmid_from_imaging",
                        "geno_base_codes_v9_exp",
                        "geno_alleles_v9_exp",
                        "treatment_rna_base_codes_v9_exp",
                        "treatment_plasmid_base_codes_v9_exp",
                    ]:
                        if col in df.columns and _nonempty_str(dv.get(col)):
                            df.loc[m, col] = dv[col]

                    df.loc[m, "mem_mito_override_applied"] = True
                    df.loc[m, "mem_mito_donor_slug"] = donor_slug
                    df.loc[m, "mem_mito_donor_reason"] = reason

    df["genotype_base_codes"] = [_coalesce(a, b) for a, b in zip(df["geno_base_from_imaging"], df.get("geno_base_codes_v9_exp"))]
    df["genotype_allele_codes"] = [_coalesce(a, b) for a, b in zip(df["geno_alle_from_imaging"], df.get("geno_alleles_v9_exp"))]
    df["treatment_rna_base_codes"] = [_coalesce(a, b) for a, b in zip(df["tr_rna_from_imaging"], df.get("treatment_rna_base_codes_v9_exp"))]
    df["treatment_plasmid_base_codes"] = [_coalesce(a, b) for a, b in zip(df["tr_plasmid_from_imaging"], df.get("treatment_plasmid_base_codes_v9_exp"))]

        # ------------------------------------------------------------------
    # v3 inference overrides for remaining matchable slugs
    # ------------------------------------------------------------------

    def _needs_all_four(row):
        return (
            not _nonempty(row.get("genotype_base_codes")) and
            not _nonempty(row.get("genotype_allele_codes")) and
            not _nonempty(row.get("treatment_rna_base_codes")) and
            not _nonempty(row.get("treatment_plasmid_base_codes"))
        )

    df["override_applied"] = False
    df["override_reason"] = pd.NA

    # ---- mito mStayGold (2xCox8A) -------------------------------------
    mask_mito = (
        df["dataset_slug_norm"].astype(str).str.contains("mitomsg|mem-mito", case=False, na=False)
        & df.apply(_needs_all_four, axis=1)
    )
    if mask_mito.any():
        df.loc[mask_mito, "genotype_base_codes"] = "MGCO-01"
        df.loc[mask_mito, "genotype_allele_codes"] = pd.NA
        df.loc[mask_mito, "override_applied"] = True
        df.loc[mask_mito, "override_reason"] = "inferred:mito_mStayGold_2xCox8A"

    # ---- ER mStayGold + membrane mChilada -----------------------------
    mask_er_mem = (
        df["dataset_slug_norm"].astype(str).str.contains("er-msg|mem-chilada", case=False, na=False)
        & df.apply(_needs_all_four, axis=1)
    )
    if mask_er_mem.any():
        df.loc[mask_er_mem, "genotype_base_codes"] = "pDQM092"
        df.loc[mask_er_mem, "genotype_allele_codes"] = pd.NA
        df.loc[mask_er_mem, "override_applied"] = True
        df.loc[mask_er_mem, "override_reason"] = "inferred:ER_mStayGold_mem_mChilada"

    # ---- peroxisome mStayGold (SKL) -----------------------------------
    mask_peroxi = (
        df["dataset_slug_norm"].astype(str).str.contains("peroxi", case=False, na=False)
        & df.apply(_needs_all_four, axis=1)
    )
    if mask_peroxi.any():
        df.loc[mask_peroxi, "genotype_base_codes"] = "MGCO-49"
        df.loc[mask_peroxi, "genotype_allele_codes"] = pd.NA
        df.loc[mask_peroxi, "override_applied"] = True
        df.loc[mask_peroxi, "override_reason"] = "inferred:peroxisome_mStayGold_SKL"

    slug = df["dataset_slug_norm"].astype(str).str.lower()
    is_skittle = slug.str.contains("skittl", na=False)
    is_no_mem = slug.str.contains("no[-_ ]?membrane", na=False)
    sk_mask = is_skittle & (~is_no_mem)
    df.loc[sk_mask, "genotype_base_codes"] = "pDQM034"
    df.loc[sk_mask, "genotype_allele_codes"] = "309"

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

    df["include_in_db"] = True
    if "dataset_slug_norm" in df.columns:
        df.loc[df["dataset_slug_norm"].astype(str).str.strip().str.lower().eq("analysis_test"), "include_in_db"] = False

    df.to_csv(OUT_FULL, index=False)
    df[df["include_in_db"]].to_csv(OUT_DB, index=False)

    print("IN_STRUCT", IN_STRUCT)
    print("ROWS", len(df), "UNIQUE_ROI_DIR", int(df["roi_dir"].nunique()))
    print("WROTE", OUT_FULL)
    print("WROTE", OUT_DB)


if __name__ == "__main__":
    main()
