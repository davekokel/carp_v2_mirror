from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
RAW = ROOT / "raw"
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

# Inputs
IN_PASS123 = WORKING / "roi_path_to_markers_pass123_v5.csv"
IN_XLSX = RAW / "2025-12-22-161955-Cell Observatory - Zebrafish Development.xlsx"
SHEET = "Master Imaging list"
IN_PARENT_MAP = RAW / "Unique_parent_names__mom_dad_combined__preview_dqm.xlsx"

# Outputs (new; does not touch existing files)
OUT_CSV = WORKING / "roi_path_to_markers_pass123_mapped_genotype_v5.csv"
OUT_PROV = QC / "roi_path_to_markers_pass123_mapped_genotype_v5.provenance.tsv"
OUT_QC = QC / "roi_path_to_markers_pass123_mapped_genotype_v5.qc.tsv"
OUT_UNMAPPED = QC / "roi_path_to_markers_pass123_mapped_genotype_v5.qc_unmapped_parents.tsv"


def _s(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _split_list(v: str) -> list[str]:
    """
    Deterministic split for mapping-table cells that contain multiple items.
    Accepts commas/semicolons; does not interpret meaning beyond splitting.
    """
    t = _s(v)
    if not t:
        return []
    parts = []
    for chunk in t.replace(";", ",").split(","):
        x = chunk.strip()
        if x:
            parts.append(x)
    return parts


def main() -> None:
    for p in (IN_PASS123, IN_XLSX, IN_PARENT_MAP):
        if not p.exists():
            raise SystemExit(f"[STOP] missing input: {p}")

    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    base = pd.read_csv(IN_PASS123)
    if "roi_path" not in base.columns:
        raise SystemExit("[STOP] pass123 csv missing roi_path")

    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)
    need_cols = {"Data location", "ZF female genotype", "ZF male genotype"}
    missing = sorted(c for c in need_cols if c not in x.columns)
    if missing:
        raise SystemExit(f"[STOP] {IN_XLSX.name}:{SHEET} missing columns: {missing}")

    # Build experiment key from Data location (Windows paths)
    def parse_foundation_experiment(v: str) -> tuple[str | None, str | None]:
        s = _s(v).replace("\\", "/")
        for root in ("Aang_Foundation", "Korra_Foundation"):
            i = s.find(root + "/")
            if i >= 0:
                tail = s[i:]
                parts = [p for p in tail.split("/") if p]
                if len(parts) >= 2:
                    return parts[0], parts[1]
        return None, None

    x = x.copy()
    x["foundation_root"], x["experiment_folder"] = zip(*x["Data location"].map(parse_foundation_experiment))

    # Map table: parent_fish_name -> plasmid_base_code(s), allele(s)
    pm = pd.read_excel(IN_PARENT_MAP)
    need_pm = {"parent_fish_name", "plasmid_base_code", "allele"}
    missing_pm = sorted(c for c in need_pm if c not in pm.columns)
    if missing_pm:
        raise SystemExit(f"[STOP] {IN_PARENT_MAP.name} missing columns: {missing_pm}")

    pm = pm.copy()
    pm["k"] = pm["parent_fish_name"].astype(str).str.strip()

    parent_to_codes = {}
    parent_to_alleles = {}
    for _, r in pm.iterrows():
        k = _s(r.get("parent_fish_name"))
        if not k:
            continue
        parent_to_codes[k] = _split_list(r.get("plasmid_base_code"))
        parent_to_alleles[k] = _split_list(r.get("allele"))

    # Determine experiment folder for each roi_path
    def parse_roi_exp(roi_path: str) -> tuple[str | None, str | None]:
        parts = [p for p in _s(roi_path).strip("/").split("/") if p]
        if len(parts) >= 2:
            return parts[0], parts[1]
        return None, None

    base = base.copy()
    base["foundation_root"], base["experiment_folder"] = zip(*base["roi_path"].map(parse_roi_exp))

    # For each experiment, we only use unique Excel rows (avoid guessing)
    x_good = x[x["foundation_root"].notna() & x["experiment_folder"].notna()].copy()
    grp = x_good.groupby(["foundation_root", "experiment_folder"], dropna=False)
    exp_counts = grp.size().rename("n_excel_rows").reset_index()
    unique_keys = set(map(tuple, exp_counts[exp_counts["n_excel_rows"] == 1][["foundation_root", "experiment_folder"]].values.tolist()))

    # Build experiment -> (mom_name, dad_name) from unique rows only
    exp_to_parents = {}
    for (fr, ef), sub in grp:
        if (fr, ef) not in unique_keys:
            continue
        r = sub.iloc[0]
        mom = _s(r.get("ZF female genotype"))
        dad = _s(r.get("ZF male genotype"))
        exp_to_parents[(fr, ef)] = (mom, dad)

    # Apply mapped genotype
    geno_codes = []
    geno_alleles = []
    prov_geno = []
    unmapped = []

    for _, r in base.iterrows():
        fr = r.get("foundation_root")
        ef = r.get("experiment_folder")
        key = (fr, ef)

        mom = dad = ""
        if key in exp_to_parents:
            mom, dad = exp_to_parents[key]

        codes = set()
        alles = set()
        any_parent = False
        any_mapped = False

        for parent in (mom, dad):
            if parent:
                any_parent = True
                if parent in parent_to_codes:
                    any_mapped = True
                    for c in parent_to_codes.get(parent, []):
                        codes.add(c)
                    for a in parent_to_alleles.get(parent, []):
                        alles.add(a)
                else:
                    unmapped.append({"roi_path": r["roi_path"], "foundation_root": fr, "experiment_folder": ef, "parent_name": parent})

        geno_codes.append(";".join(sorted(codes)))
        geno_alleles.append(";".join(sorted(alles)))

        if any_mapped:
            prov_geno.append("parent_map_unique_experiment")
        elif any_parent:
            prov_geno.append("parent_unmapped_or_ambiguous_experiment")
        else:
            prov_geno.append("no_parent_info")

    out = base.copy()
    out["genotype_base_codes"] = geno_codes
    out["genotype_allele_codes"] = geno_alleles

    # Keep treatment columns exactly as-is (do not change in this pass)
    final = out[["roi_path", "genotype_base_codes", "genotype_allele_codes", "treatment_rna_base_codes", "treatment_plasmid_base_codes"]].copy()
    final.to_csv(OUT_CSV, index=False)

    prov = pd.DataFrame({
        "roi_path": out["roi_path"],
        "source_genotype": prov_geno,
    })
    prov.to_csv(OUT_PROV, sep="\t", index=False)

    pd.DataFrame([{
        "roi_paths_total": int(len(out)),
        "unique_experiment_keys_in_excel": int(len(unique_keys)),
        "roi_paths_with_mapped_genotype": int((out["genotype_base_codes"].astype(str).str.len() > 0).sum()),
        "roi_paths_with_unmapped_parent_name": int(len(pd.DataFrame(unmapped)["roi_path"].unique())) if unmapped else 0,
        "unmapped_parent_rows": int(len(unmapped)),
    }]).to_csv(OUT_QC, sep="\t", index=False)

    pd.DataFrame(unmapped).to_csv(OUT_UNMAPPED, sep="\t", index=False)

    print(f"[OK] wrote {OUT_CSV} rows={len(final)}")
    print(f"[QC] wrote {OUT_QC}")
    print(f"[QC] wrote {OUT_PROV}")
    print(f"[QC] wrote {OUT_UNMAPPED}")


if __name__ == "__main__":
    main()
