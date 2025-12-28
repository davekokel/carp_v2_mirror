from __future__ import annotations

from pathlib import Path
import pandas as pd
import re

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
RAW = ROOT / "raw"
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_LINK = WORKING / "experiment_linkage_v5.tsv"
IN_CAND = WORKING / "experiment_linkage_v5_candidates.tsv"
IN_XLSX = RAW / "2025-12-22-161955-Cell Observatory - Zebrafish Development.xlsx"
SHEET = "Master Imaging list"
IN_PARENT_MAP = RAW / "Unique_parent_names__mom_dad_combined__preview_dqm.xlsx"
IN_PLASMID_MAP = RAW / "Unique_injected_plasmid__preview_dqm.xlsx"
IN_RNA_MAP = RAW / "Unique_injected_rna__preview_dqm.xlsx"
IN_ROI_SLUGS = WORKING / "roi_path_slugs_v5.csv"

OUT_EXP = WORKING / "experiment_metadata_v5.tsv"
OUT_ROI = WORKING / "roi_path_to_markers_pass1234_v5.csv"
OUT_PROV = QC / "roi_path_to_markers_pass1234_v5.provenance.tsv"
OUT_QC = QC / "roi_path_to_markers_pass1234_v5.qc.tsv"
OUT_CLASS4 = QC / "roi_path_to_markers_pass1234_v5.class4_missing_experiments.tsv"
OUT_CLASS3_AMBIG = QC / "roi_path_to_markers_pass1234_v5.class3_ambiguous_after_choice.tsv"

RE_MGCO_NUM = re.compile(r"(?i)\bmgco[- ]?(\d{1,3})\b")
RE_SPLIT = re.compile(r"[;,|+]+|\s+|[()\[\]{}]+|:+|/+")

def _s(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()

def split_list(v: str) -> list[str]:
    t = _s(v).replace(";", ",")
    return [x.strip() for x in t.split(",") if x and x.strip()]

def split_tokens(v: str) -> list[str]:
    t = _s(v)
    if not t:
        return []
    t = t.replace(",", " ")
    toks = [x.strip().strip(".") for x in RE_SPLIT.split(t) if x and x.strip()]
    return [x for x in toks if x]

def mgco_key_variants(tok: str) -> set[str]:
    out = set()
    m = RE_MGCO_NUM.search(_s(tok))
    if not m:
        return out
    n = int(m.group(1))
    out.add(f"MGCO-{n}")
    out.add(f"MGCO{n}")
    if n < 10:
        out.add(f"MGCO-0{n}")
        out.add(f"MGCO0{n}")
    return out

def load_map(path: Path, key_col: str, val_col: str) -> dict[str, str]:
    x = pd.read_excel(path)
    need = {key_col, val_col}
    if not need.issubset(set(x.columns)):
        raise SystemExit(f"[STOP] {path.name} missing columns: {sorted(need - set(x.columns))}")
    m = {}
    for a, b in zip(x[key_col], x[val_col]):
        if pd.isna(a) or pd.isna(b):
            continue
        k = _s(a)
        v = _s(b)
        if k and v:
            m[k] = v
    # expand MGCO variants deterministically
    out = dict(m)
    for k, v in m.items():
        for kk in mgco_key_variants(k):
            out.setdefault(kk, v)
    return out

def choose_candidate(cands: pd.DataFrame, exp_date: str) -> tuple[pd.Series, str]:
    """
    Deterministic chooser:
      1) mode of (mom,dad,plasmids,rna,dye) signature if unique
      2) closest in time to exp_date using date_mount else date_imaged
      3) if still tied, take first row but mark ambiguous_tie
    """
    if len(cands) == 0:
        raise ValueError("empty candidates")

    def sig_row(r) -> tuple[str,str,str,str,str]:
        return (
            _s(r.get("mom_parent_cell")),
            _s(r.get("dad_parent_cell")),
            _s(r.get("inj_plasmids_cell")),
            _s(r.get("inj_rna_cell")),
            _s(r.get("inj_dye_cell")),
        )

    c = cands.copy()
    c["sig"] = c.apply(sig_row, axis=1)
    vc = c["sig"].value_counts()
    top_n = int(vc.iloc[0])
    top_sigs = vc[vc == top_n].index.tolist()
    if len(top_sigs) == 1:
        sig = top_sigs[0]
        row = c[c["sig"] == sig].iloc[0]
        return row, "mode"

    # closest in time
    exp_dt = pd.to_datetime(exp_date, format="%Y%m%d", errors="coerce")
    if pd.notna(exp_dt):
        def delta_days(r):
            dm = pd.to_datetime(r.get("date_mount"), errors="coerce")
            di = pd.to_datetime(r.get("date_imaged"), errors="coerce")
            if pd.notna(dm):
                return abs((dm.normalize() - exp_dt.normalize()).days)
            if pd.notna(di):
                return abs((di.normalize() - exp_dt.normalize()).days)
            return 10**9
        c["delta"] = c.apply(delta_days, axis=1)
        min_d = int(c["delta"].min())
        best = c[c["delta"] == min_d]
        if len(best) == 1:
            return best.iloc[0], "closest_time"
        # still tied
        return best.iloc[0], "ambiguous_tie"

    return c.iloc[0], "ambiguous_no_date"

def main() -> None:
    for p in (IN_LINK, IN_CAND, IN_XLSX, IN_PARENT_MAP, IN_PLASMID_MAP, IN_RNA_MAP, IN_ROI_SLUGS):
        if not p.exists():
            raise SystemExit(f"[STOP] missing input: {p}")

    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    link = pd.read_csv(IN_LINK, sep="\t")
    cand = pd.read_csv(IN_CAND, sep="\t")
    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)

    parent = pd.read_excel(IN_PARENT_MAP)
    need_pm = {"parent_fish_name","plasmid_base_code","allele"}
    if not need_pm.issubset(set(parent.columns)):
        raise SystemExit(f"[STOP] {IN_PARENT_MAP.name} missing columns: {sorted(need_pm - set(parent.columns))}")
    parent["parent_fish_name"] = parent["parent_fish_name"].astype(str).str.strip()

    parent_to_codes = {r["parent_fish_name"]: split_list(r.get("plasmid_base_code")) for _, r in parent.iterrows()}
    parent_to_alleles = {r["parent_fish_name"]: split_list(r.get("allele")) for _, r in parent.iterrows()}

    map_pl = load_map(IN_PLASMID_MAP, "injected_plasmid", "plasmid_base_code")
    map_rna = load_map(IN_RNA_MAP, "injected_rna", "plasmid_base_code")

    # Build experiment -> chosen marker cells
    exp_rows = []
    class4 = link[link["link_class"] == "class4"].copy()
    if len(class4):
        class4.to_csv(OUT_CLASS4, sep="\t", index=False)

    class3_ambig = []

    for _, r in link.iterrows():
        fr = r["foundation_root"]
        ef = r["experiment_folder"]
        cls = r["link_class"]
        exp_date = _s(r.get("experiment_date"))

        chosen_method = ""
        mom = dad = pl_cell = rna_cell = dye_cell = data_loc = date_mount = date_imaged = ""
        excel_row_1based = ""

        if cls in ("class1","class2"):
            excel_row_1based = _s(r.get("chosen_excel_row_1based"))
            if excel_row_1based:
                # robust cast (handles "163.0" and "163")
                try:
                    idx0 = int(float(excel_row_1based)) - 2
                except Exception:
                    idx0 = None

                if idx0 is not None and 0 <= idx0 < len(x):
                    xr = x.iloc[idx0]
                    chosen_method = cls
                    mom = _s(xr.get("ZF female genotype"))
                    dad = _s(xr.get("ZF male genotype"))
                    pl_cell = _s(xr.get("additional plasmids injected"))
                    rna_cell = _s(xr.get("additional mRNAs injected"))
                    dye_cell = _s(xr.get("additonal dye and chemicals"))
                    data_loc = _s(xr.get("Data location"))
                    date_mount = _s(xr.get("date_mount"))
                    date_imaged = _s(xr.get("Date imaged"))
        elif cls == "class3":
            c = cand[(cand["foundation_root"] == fr) & (cand["experiment_folder"] == ef)].copy()
            if len(c) == 0:
                class3_ambig.append({"foundation_root": fr, "experiment_folder": ef, "reason": "no_candidates_rows"})
                continue
            row, chosen_method = choose_candidate(c, exp_date)
            excel_row_1based = _s(row.get("excel_row_1based"))
            mom = _s(row.get("mom_parent_cell"))
            dad = _s(row.get("dad_parent_cell"))
            pl_cell = _s(row.get("inj_plasmids_cell"))
            rna_cell = _s(row.get("inj_rna_cell"))
            dye_cell = _s(row.get("inj_dye_cell"))
            data_loc = _s(row.get("Data location"))
            date_mount = _s(row.get("date_mount"))
            date_imaged = _s(row.get("date_imaged"))
            if chosen_method.startswith("ambiguous"):
                class3_ambig.append({
                    "foundation_root": fr,
                    "experiment_folder": ef,
                    "chosen_method": chosen_method,
                    "excel_row_1based": excel_row_1based,
                    "n_candidates": int(len(c)),
                })

        # Map parents -> genotype basecodes + alleles (mapping only)
        geno_codes = set()
        geno_alleles = set()
        missing_parents = []
        for pnm in [mom, dad]:
            if not pnm:
                continue
            if pnm in parent_to_codes:
                for c_ in parent_to_codes.get(pnm, []):
                    if c_:
                        geno_codes.add(c_)
                for a_ in parent_to_alleles.get(pnm, []):
                    if a_:
                        geno_alleles.add(a_)
            else:
                missing_parents.append(pnm)

        # Map injections -> treatment basecodes (mapping only)
        def map_inj(cell: str, m: dict[str,str]) -> list[str]:
            toks = split_tokens(cell)
            codes = set()
            for tok in toks:
                if tok in m:
                    codes.add(m[tok])
                else:
                    for kk in mgco_key_variants(tok):
                        if kk in m:
                            codes.add(m[kk])
                            break
            return sorted(codes)

        pl_codes = map_inj(pl_cell, map_pl)
        rna_codes = map_inj(rna_cell, map_rna)

        exp_rows.append({
            "foundation_root": fr,
            "experiment_folder": ef,
            "link_class": cls,
            "chosen_method": chosen_method,
            "excel_row_1based": excel_row_1based,
            "date_mount": date_mount,
            "date_imaged": date_imaged,
            "Data location": data_loc,
            "mom_parent_cell": mom,
            "dad_parent_cell": dad,
            "missing_parent_names": " || ".join(missing_parents),
            "genotype_base_codes": ";".join(sorted(geno_codes)),
            "genotype_allele_codes": ";".join(sorted(geno_alleles)),
            "treatment_plasmid_base_codes": ";".join(pl_codes),
            "treatment_rna_base_codes": ";".join(rna_codes),
            "treatment_dye_text": dye_cell,
        })

    exp_df = pd.DataFrame(exp_rows)
    exp_df.to_csv(OUT_EXP, sep="\t", index=False)

    if class3_ambig:
        pd.DataFrame(class3_ambig).to_csv(OUT_CLASS3_AMBIG, sep="\t", index=False)
    else:
        pd.DataFrame([{}]).head(0).to_csv(OUT_CLASS3_AMBIG, sep="\t", index=False)

    # Apply experiment metadata to ROIs
    slugs = pd.read_csv(IN_ROI_SLUGS)
    roi = slugs[["roi_path","foundation_root","experiment_folder"]].copy()
    out = roi.merge(exp_df, on=["foundation_root","experiment_folder"], how="left")

    # canonical output
    final = out[["roi_path","genotype_base_codes","genotype_allele_codes","treatment_rna_base_codes","treatment_plasmid_base_codes"]].copy()
    final.to_csv(OUT_ROI, index=False)

    # provenance per field: link_class/chooser for experiments that produced non-empty values
    prov = out[["roi_path","link_class","chosen_method"]].copy()
    tag = (prov["link_class"].fillna("") + ":" + prov["chosen_method"].fillna("")).str.strip(":")

    geno_filled = out["genotype_base_codes"].fillna("").astype(str).str.len() > 0
    pl_filled = out["treatment_plasmid_base_codes"].fillna("").astype(str).str.len() > 0
    rna_filled = out["treatment_rna_base_codes"].fillna("").astype(str).str.len() > 0

    prov["source_genotype"] = "unfilled"
    prov.loc[geno_filled, "source_genotype"] = tag[geno_filled]

    prov["source_treatment_plasmid"] = "unfilled"
    prov.loc[pl_filled, "source_treatment_plasmid"] = tag[pl_filled]

    prov["source_treatment_rna"] = "unfilled"
    prov.loc[rna_filled, "source_treatment_rna"] = tag[rna_filled]

    prov[["roi_path","source_genotype","source_treatment_plasmid","source_treatment_rna"]].to_csv(OUT_PROV, sep="	", index=False)

    # QC summary
    qc = {
        "roi_paths_total": int(len(final)),
        "experiments_total": int(len(link)),
        "class1": int((link["link_class"]=="class1").sum()),
        "class2": int((link["link_class"]=="class2").sum()),
        "class3": int((link["link_class"]=="class3").sum()),
        "class4": int((link["link_class"]=="class4").sum()),
        "roi_with_genotype": int((final["genotype_base_codes"].astype(str).str.len()>0).sum()),
        "roi_with_plasmid_treatment": int((final["treatment_plasmid_base_codes"].astype(str).str.len()>0).sum()),
        "roi_with_rna_treatment": int((final["treatment_rna_base_codes"].astype(str).str.len()>0).sum()),
    }
    pd.DataFrame([qc]).to_csv(OUT_QC, sep="\t", index=False)

    print(f"[OK] wrote {OUT_EXP}")
    print(f"[OK] wrote {OUT_ROI}")
    print(f"[OK] wrote {OUT_PROV}")
    print(f"[OK] wrote {OUT_QC}")
    print(f"[QC] wrote {OUT_CLASS4}")
    print(f"[QC] wrote {OUT_CLASS3_AMBIG}")

if __name__ == "__main__":
    main()
