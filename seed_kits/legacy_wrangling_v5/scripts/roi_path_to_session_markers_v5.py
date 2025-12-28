from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
RAW = ROOT / "raw"
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_ROI_SLUGS = WORKING / "roi_path_slugs_v5.csv"
IN_LINK = WORKING / "experiment_linkage_v5.tsv"
IN_CAND = WORKING / "experiment_linkage_v5_candidates.tsv"
IN_XLSX = RAW / "2025-12-22-161955-Cell Observatory - Zebrafish Development.xlsx"
SHEET = "Master Imaging list"

IN_PARENT_MAP = RAW / "Unique_parent_names__mom_dad_combined__preview_dqm.xlsx"
IN_PLASMID_MAP = RAW / "Unique_injected_plasmid__preview_dqm.xlsx"
IN_RNA_MAP = RAW / "Unique_injected_rna__preview_dqm.xlsx"

OUT = WORKING / "roi_path_to_session_markers_v5.csv"
OUT_QC = QC / "roi_path_to_session_markers_v5.qc.tsv"
OUT_CLASS4 = QC / "roi_path_to_session_markers_v5.class4_missing.tsv"
OUT_CLASS3_AMBIG = QC / "roi_path_to_session_markers_v5.class3_ambiguous.tsv"

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


def load_map_excel(path: Path, key_col: str, val_col: str) -> dict[str, str]:
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
    # deterministic MGCO variant expansion
    out = dict(m)
    for k, v in m.items():
        for kk in mgco_key_variants(k):
            out.setdefault(kk, v)
    return out


def choose_candidate(cands: pd.DataFrame, exp_date_yyyymmdd: str) -> tuple[pd.Series, str]:
    """
    Deterministic chooser for class3:
      1) unique mode of (mom,dad,plasmids,rna,dye) signature
      2) closest in time to exp_date using date_mount else date_imaged
      3) if still tied, pick first but mark ambiguous_tie
    """
    if len(cands) == 0:
        raise ValueError("empty candidates")

    def sig_row(r) -> tuple[str, str, str, str, str]:
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
        return c[c["sig"] == sig].iloc[0], "mode"

    exp_dt = pd.to_datetime(exp_date_yyyymmdd, format="%Y%m%d", errors="coerce")
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
        return best.iloc[0], "ambiguous_tie"

    return c.iloc[0], "ambiguous_no_date"


def main() -> None:
    for p in (IN_ROI_SLUGS, IN_LINK, IN_CAND, IN_XLSX, IN_PARENT_MAP, IN_PLASMID_MAP, IN_RNA_MAP):
        if not p.exists():
            raise SystemExit(f"[STOP] missing input: {p}")

    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    # ROI -> (foundation_root, experiment_folder)
    slugs = pd.read_csv(IN_ROI_SLUGS)
    roi = slugs[["roi_path", "foundation_root", "experiment_folder"]].copy()

    # Experiment linkage (class1/2/3/4)
    link = pd.read_csv(IN_LINK, sep="\t")
    cand = pd.read_csv(IN_CAND, sep="\t")

    # Excel sheet
    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)

    # Ensure required columns exist
    for c in [
        "date_mount",
        "mount_id",
        "ZF female genotype",
        "ZF male genotype",
        "additional plasmids injected",
        "additional mRNAs injected",
        "additonal dye and chemicals",
    ]:
        if c not in x.columns:
            raise SystemExit(f"[STOP] Master Imaging list missing column: {c}")

    # Parent mapping
    pm = pd.read_excel(IN_PARENT_MAP)
    need_pm = {"parent_fish_name", "plasmid_base_code", "allele"}
    if not need_pm.issubset(set(pm.columns)):
        raise SystemExit(f"[STOP] {IN_PARENT_MAP.name} missing columns: {sorted(need_pm - set(pm.columns))}")
    pm["parent_fish_name"] = pm["parent_fish_name"].astype(str).str.strip()
    parent_to_codes = {r["parent_fish_name"]: split_list(r.get("plasmid_base_code")) for _, r in pm.iterrows()}
    parent_to_alleles = {r["parent_fish_name"]: split_list(r.get("allele")) for _, r in pm.iterrows()}

    # Injection maps
    map_pl = load_map_excel(IN_PLASMID_MAP, "injected_plasmid", "plasmid_base_code")
    map_rna = load_map_excel(IN_RNA_MAP, "injected_rna", "plasmid_base_code")

    # Build experiment -> chosen Excel row index (0-based) and class/method
    exp_choice = {}
    class4_rows = []
    class3_ambig = []

    for _, r in link.iterrows():
        fr = r["foundation_root"]
        ef = r["experiment_folder"]
        cls = r["link_class"]
        exp_date = _s(r.get("experiment_date"))  # YYYYMMDD

        key = (fr, ef)

        if cls in ("class1", "class2"):
            row_1 = _s(r.get("chosen_excel_row_1based"))
            if not row_1:
                continue
            try:
                idx0 = int(float(row_1)) - 2
            except Exception:
                continue
            exp_choice[key] = {"excel_idx0": idx0, "link_class": cls, "chosen_method": cls}
            continue

        if cls == "class3":
            c = cand[(cand["foundation_root"] == fr) & (cand["experiment_folder"] == ef)].copy()
            if len(c) == 0:
                class3_ambig.append({"foundation_root": fr, "experiment_folder": ef, "reason": "no_candidate_rows"})
                continue
            row, method = choose_candidate(c, exp_date)
            row_1 = _s(row.get("excel_row_1based"))
            idx0 = None
            if row_1:
                try:
                    idx0 = int(float(row_1)) - 2
                except Exception:
                    idx0 = None
            if idx0 is None:
                class3_ambig.append({"foundation_root": fr, "experiment_folder": ef, "reason": "bad_excel_row_number", "chosen_method": method, "excel_row_1based": row_1})
                continue
            exp_choice[key] = {"excel_idx0": idx0, "link_class": cls, "chosen_method": method}
            if method.startswith("ambiguous"):
                class3_ambig.append({"foundation_root": fr, "experiment_folder": ef, "reason": method, "excel_row_1based": row_1, "n_candidates": int(len(c))})
            continue

        if cls == "class4":
            class4_rows.append({"foundation_root": fr, "experiment_folder": ef})
            continue

    # Write QC lists
    pd.DataFrame(class4_rows).to_csv(OUT_CLASS4, sep="\t", index=False)
    pd.DataFrame(class3_ambig).to_csv(OUT_CLASS3_AMBIG, sep="\t", index=False)

    # Helper: map parent names to genotype basecodes/alleles (mapping only)
    def map_parents(mom: str, dad: str) -> tuple[str, str]:
        codes = set()
        alles = set()
        for pnm in [_s(mom), _s(dad)]:
            if not pnm:
                continue
            for c_ in parent_to_codes.get(pnm, []):
                if c_:
                    codes.add(c_)
            for a_ in parent_to_alleles.get(pnm, []):
                if a_:
                    alles.add(a_)
        return ";".join(sorted(codes)), ";".join(sorted(alles))

    # Helper: map injections to basecodes (mapping only)
    def map_inj(cell: str, mapping: dict[str, str]) -> str:
        toks = split_tokens(cell)
        codes = set()
        for tok in toks:
            if tok in mapping:
                codes.add(mapping[tok])
                continue
            for kk in mgco_key_variants(tok):
                if kk in mapping:
                    codes.add(mapping[kk])
                    break
        return ";".join(sorted(codes))

    # Build ROI rows
    out_rows = []
    for _, rr in roi.iterrows():
        roi_path = rr["roi_path"]
        fr = rr["foundation_root"]
        ef = rr["experiment_folder"]
        key = (fr, ef)

        date_mount_id = ""
        geno_bc = ""
        geno_al = ""
        rna_bc = ""
        pl_bc = ""

        choice = exp_choice.get(key)
        if choice is not None:
            idx0 = int(choice["excel_idx0"])
            if 0 <= idx0 < len(x):
                xr = x.iloc[idx0]
                date_mount = pd.to_datetime(xr.get("date_mount"), errors="coerce")
                mount_id = _s(xr.get("mount_id"))
                if pd.notna(date_mount) and mount_id:
                    date_mount_id = date_mount.strftime("%Y-%m-%d") + "__" + mount_id

                mom = xr.get("ZF female genotype")
                dad = xr.get("ZF male genotype")
                geno_bc, geno_al = map_parents(mom, dad)

                pl_bc = map_inj(xr.get("additional plasmids injected"), map_pl)
                rna_bc = map_inj(xr.get("additional mRNAs injected"), map_rna)

        out_rows.append({
            "roi_path": roi_path,
            "date_mount_id": date_mount_id,
            "genotype_base_codes": geno_bc,
            "genotype_allele_codes": geno_al,
            "treatment_rna_base_codes": rna_bc,
            "treatment_plasmid_base_codes": pl_bc,
        })

    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(OUT, index=False)

    qc = {
        "roi_paths_total": int(len(out_df)),
        "roi_with_date_mount_id": int((out_df["date_mount_id"].astype(str).str.len() > 0).sum()),
        "roi_with_genotype": int((out_df["genotype_base_codes"].astype(str).str.len() > 0).sum()),
        "roi_with_plasmid_treatment": int((out_df["treatment_plasmid_base_codes"].astype(str).str.len() > 0).sum()),
        "roi_with_rna_treatment": int((out_df["treatment_rna_base_codes"].astype(str).str.len() > 0).sum()),
        "experiments_linked": int(len(exp_choice)),
        "experiments_class4": int(len(class4_rows)),
        "experiments_class3_ambig_logged": int(len(class3_ambig)),
    }
    pd.DataFrame([qc]).to_csv(OUT_QC, sep="\t", index=False)

    print(f"[OK] wrote {OUT} rows={len(out_df)}")
    print(f"[QC] wrote {OUT_QC}")
    print(f"[QC] wrote {OUT_CLASS4}")
    print(f"[QC] wrote {OUT_CLASS3_AMBIG}")

if __name__ == "__main__":
    main()
