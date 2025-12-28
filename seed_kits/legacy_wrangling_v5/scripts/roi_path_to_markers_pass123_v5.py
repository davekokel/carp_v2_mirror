from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
RAW = ROOT / "raw"
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_PASS12 = WORKING / "roi_path_to_markers_pass12_v5.csv"
IN_XLSX = RAW / "2025-12-22-161955-Cell Observatory - Zebrafish Development.xlsx"
SHEET = "Master Imaging list"

IN_PLASMID_MAP = RAW / "Unique_injected_plasmid__preview_dqm.xlsx"
IN_RNA_MAP = RAW / "Unique_injected_rna__preview_dqm.xlsx"

OUT_CSV = WORKING / "roi_path_to_markers_pass123_v5.csv"
QC_MAIN = QC / "roi_path_to_markers_pass123_v5.qc.tsv"
QC_AMBIG = QC / "roi_path_to_markers_pass123_v5.qc_ambiguous_date_matches.tsv"
QC_PROV = QC / "roi_path_to_markers_pass123_v5.provenance.tsv"

RE_DATE8 = re.compile(r"^(\d{8})")
RE_MGCO_NUM = re.compile(r"(?i)\bmgco[- ]?(\d{1,3})\b")
RE_SPLIT = re.compile(r"[;,|+]+|\s+|[()\[\]{}]+|:+|/+")

def _norm_pathish(s: str) -> str:
    return str(s).strip().replace("\\", "/")

def parse_foundation_and_experiment_from_roi_path(roi_path: str) -> tuple[str | None, str | None]:
    s = str(roi_path).strip().strip("/")
    parts = [p for p in s.split("/") if p]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None, None

def parse_foundation_and_experiment_from_data_location(v: str) -> tuple[str | None, str | None]:
    s = _norm_pathish(v)
    for root in ("Aang_Foundation", "Korra_Foundation"):
        i = s.find(root + "/")
        if i >= 0:
            tail = s[i:]
            parts = [p for p in tail.split("/") if p]
            if len(parts) >= 2:
                return parts[0], parts[1]
    return None, None

def date_to_yyyymmdd(v) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        ts = pd.to_datetime(v, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.strftime("%Y%m%d")
    except Exception:
        return None

def experiment_folder_date(experiment_folder: str) -> str | None:
    if not experiment_folder:
        return None
    m = RE_DATE8.match(str(experiment_folder))
    return m.group(1) if m else None

def split_tokens(s: str) -> list[str]:
    if s is None:
        return []
    t = str(s).strip()
    if not t or t.lower() in ("nan", "none"):
        return []
    t = t.replace(",", " ")
    toks = [x.strip().strip(".") for x in RE_SPLIT.split(t) if x and x.strip()]
    return [x for x in toks if x]

def load_map_plasmid() -> dict[str, str]:
    x = pd.read_excel(IN_PLASMID_MAP)
    need = {"injected_plasmid", "plasmid_base_code"}
    if not need.issubset(set(x.columns)):
        raise SystemExit(f"[STOP] {IN_PLASMID_MAP.name} missing columns: {sorted(need - set(x.columns))}")
    m: dict[str, str] = {}
    for a, b in zip(x["injected_plasmid"], x["plasmid_base_code"]):
        if pd.isna(a) or pd.isna(b):
            continue
        k = str(a).strip()
        v = str(b).strip()
        if k and v:
            m[k] = v
    return m

def load_map_rna() -> dict[str, str]:
    x = pd.read_excel(IN_RNA_MAP)
    need = {"injected_rna", "plasmid_base_code"}
    if not need.issubset(set(x.columns)):
        raise SystemExit(f"[STOP] {IN_RNA_MAP.name} missing columns: {sorted(need - set(x.columns))}")
    m: dict[str, str] = {}
    for a, b in zip(x["injected_rna"], x["plasmid_base_code"]):
        if pd.isna(a) or pd.isna(b):
            continue
        k = str(a).strip()
        v = str(b).strip()
        if k and v:
            m[k] = v
    return m

def mgco_key_variants(tok: str) -> set[str]:
    out: set[str] = set()
    t = str(tok).strip()
    if not t:
        return out
    m = RE_MGCO_NUM.search(t)
    if not m:
        return out
    n = int(m.group(1))
    out.add(f"MGCO-{n}")
    out.add(f"MGCO{n}")
    if n < 10:
        out.add(f"MGCO-0{n}")
        out.add(f"MGCO0{n}")
    return out

def normalize_mapping_keys(mapping: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in mapping.items():
        out[k] = v
        for kk in mgco_key_variants(k):
            out.setdefault(kk, v)
    return out

def inj_to_codes(v: str, mapping: dict[str, str]) -> list[str]:
    toks = split_tokens(v)
    codes: set[str] = set()
    for tok in toks:
        if tok in mapping:
            codes.add(mapping[tok])
        else:
            for kk in mgco_key_variants(tok):
                if kk in mapping:
                    codes.add(mapping[kk])
                    break
    return sorted(codes)

def main() -> None:
    for p in (IN_PASS12, IN_XLSX, IN_PLASMID_MAP, IN_RNA_MAP):
        if not p.exists():
            raise SystemExit(f"[STOP] missing input: {p}")

    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    base = pd.read_csv(IN_PASS12)
    if "roi_path" not in base.columns:
        raise SystemExit("[STOP] pass12 csv missing roi_path")

    base = base.copy()
    base["foundation_root"], base["experiment_folder"] = zip(*base["roi_path"].map(parse_foundation_and_experiment_from_roi_path))
    base["exp_date"] = base["experiment_folder"].map(experiment_folder_date)

    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)
    need_cols = {
        "Data location",
        "date_mount",
        "Date imaged",
        "ZF female genotype",
        "ZF male genotype",
        "additional plasmids injected",
        "additional mRNAs injected",
        "additonal dye and chemicals",
    }
    missing = sorted(c for c in need_cols if c not in x.columns)
    if missing:
        raise SystemExit(f"[STOP] {IN_XLSX.name}:{SHEET} missing columns: {missing}")

    x = x.copy()
    x["foundation_root"], x["experiment_folder"] = zip(*x["Data location"].map(parse_foundation_and_experiment_from_data_location))
    x["date_mount_yyyymmdd"] = x["date_mount"].map(date_to_yyyymmdd)
    x["date_imaged_yyyymmdd"] = x["Date imaged"].map(date_to_yyyymmdd)

    # identify rows still missing pass1/2 link: we proxy by missing BOTH treatment fields and genotype fields
    # (pass12 writes empty strings when missing)
    def _is_empty_col(s: pd.Series) -> pd.Series:
        return s.fillna("").astype(str).str.strip().eq("")

    missing_mask = (
        _is_empty_col(base["genotype_base_codes"])
        & _is_empty_col(base["genotype_allele_codes"])
        & _is_empty_col(base["treatment_plasmid_base_codes"])
        & _is_empty_col(base["treatment_rna_base_codes"])
    )

    need = base[missing_mask].copy()

    # provenance: default unfilled, then mark pass12 for any non-empty fields
    base["source_genotype"] = "unfilled"
    base["source_treatment_plasmid"] = "unfilled"
    base["source_treatment_rna"] = "unfilled"
    has_geno = (~_is_empty_col(base["genotype_base_codes"])) | (~_is_empty_col(base["genotype_allele_codes"]))
    has_pl = ~_is_empty_col(base["treatment_plasmid_base_codes"])
    has_rna = ~_is_empty_col(base["treatment_rna_base_codes"])
    base.loc[has_geno, "source_genotype"] = "pass12_datalocation"
    base.loc[has_pl, "source_treatment_plasmid"] = "pass12_datalocation"
    base.loc[has_rna, "source_treatment_rna"] = "pass12_datalocation"

    map_pl = normalize_mapping_keys(load_map_plasmid())
    map_rna = normalize_mapping_keys(load_map_rna())

    ambiguous_rows = []
    filled_method = {}

    filled = 0
    for idx, r in need.iterrows():
        fr = r.get("foundation_root")
        d = r.get("exp_date")
        if not fr or not d:
            continue

        cand = x[(x["foundation_root"] == fr) & (x["date_mount_yyyymmdd"] == d)]
        used = "date_mount"
        if len(cand) == 0:
            cand = x[(x["foundation_root"] == fr) & (x["date_imaged_yyyymmdd"] == d)]
            used = "date_imaged"

        if len(cand) == 1:
            row = cand.iloc[0]

            # genotype extraction: keep the already-produced representation from pass12 logic:
            # minimal token extraction is already baked into pass12; here we simply reuse the raw strings
            # by reusing pass12 empty slots is acceptable; but we can also leave genotype empty if you prefer.
            # For now we fill by re-running the same minimal extractor inline (bases/alleles).
            gf = str(row.get("ZF female genotype") or "")
            gm = str(row.get("ZF male genotype") or "")
            bases = sorted(set(re.findall(r"(?i)\b([a-z]{2,8}-?\d{1,4})\b", gf) + re.findall(r"(?i)\b([a-z]{2,8}-?\d{1,4})\b", gm)))
            alles = sorted(set(re.findall(r"(?i)\b(\d{2,4})\b", gf) + re.findall(r"(?i)\b(\d{2,4})\b", gm)))

            pl_codes = inj_to_codes(row.get("additional plasmids injected"), map_pl)
            rna_codes = inj_to_codes(row.get("additional mRNAs injected"), map_rna)

            base.at[idx, "genotype_base_codes"] = ";".join(sorted(set([b.lower() for b in bases])))
            base.at[idx, "genotype_allele_codes"] = ";".join(sorted(set(alles)))
            base.at[idx, "treatment_plasmid_base_codes"] = ";".join(pl_codes)
            base.at[idx, "treatment_rna_base_codes"] = ";".join(rna_codes)

            filled_method[int(idx)] = used
            filled += 1

        elif len(cand) > 1:
            ambiguous_rows.append({
                "roi_path": r.get("roi_path"),
                "foundation_root": fr,
                "experiment_folder": r.get("experiment_folder"),
                "exp_date": d,
                "match_field": used,
                "candidate_excel_rows": int(len(cand)),
            })

    # write canonical output (schema only)
    base[["roi_path", "genotype_base_codes", "genotype_allele_codes", "treatment_rna_base_codes", "treatment_plasmid_base_codes"]].to_csv(OUT_CSV, index=False)

    # apply pass3 provenance for filled rows
    for i, used in filled_method.items():
        tag = f"pass3_{used}"
        base.at[i, "source_genotype"] = tag
        base.at[i, "source_treatment_plasmid"] = tag
        base.at[i, "source_treatment_rna"] = tag

    # write provenance (QC artifact)
    prov = base[["roi_path", "source_genotype", "source_treatment_plasmid", "source_treatment_rna"]].copy()
    prov.to_csv(QC_PROV, sep="\t", index=False)

    # QC summaries
    pd.DataFrame([{
        "roi_paths_total": int(len(base)),
        "roi_paths_missing_before_pass3": int(len(need)),
        "roi_paths_filled_by_pass3": int(filled),
        "roi_paths_ambiguous_by_pass3": int(len(ambiguous_rows)),
    }]).to_csv(QC_MAIN, sep="\t", index=False)

    pd.DataFrame(ambiguous_rows).to_csv(QC_AMBIG, sep="\t", index=False)

    print(f"[OK] wrote {OUT_CSV} rows={len(base)}")
    print(f"[QC] wrote {QC_MAIN}")
    print(f"[QC] wrote {QC_AMBIG}")
    print(f"[QC] wrote {QC_PROV}")

if __name__ == "__main__":
    main()
