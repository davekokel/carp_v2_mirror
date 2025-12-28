from __future__ import annotations

from pathlib import Path
import pandas as pd
import re

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
RAW = ROOT / "raw"
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_STEP1 = WORKING / "roi_path_to_date_mount_id_step1_v5.csv"
IN_XLSX = WORKING / "master_imaging_list_mountid_filled_v5.xlsx"
SHEET = "Master Imaging list"

IN_PARENT_MAP = RAW / "Unique_parent_names__mom_dad_combined__preview_dqm.xlsx"
IN_PLASMID_MAP = RAW / "Unique_injected_plasmid__preview_dqm.xlsx"
IN_RNA_MAP = RAW / "Unique_injected_rna__preview_dqm.xlsx"

OUT = WORKING / "roi_path_to_session_markers_v5.csv"

OUT_QC = QC / "roi_path_to_session_markers_v5.qc.tsv"
OUT_MISSING_SESSION = QC / "roi_path_to_session_markers_v5.qc_missing_session.tsv"
OUT_UNMAPPED_PARENTS = QC / "roi_path_to_session_markers_v5.qc_unmapped_parents.tsv"
OUT_UNMAPPED_TREATMENTS = QC / "roi_path_to_session_markers_v5.qc_unmapped_treatments.tsv"

RE_MGCO_NUM = re.compile(r"(?i)\bmgco[- ]?(\d{1,3})\b")
RE_SPLIT = re.compile(r"[;,|+]+|\s+|[()\[\]{}]+")

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

def norm_key(s: str) -> str:
    """
    Normalization for mapping keys (treatment labels):
    - lowercase
    - drop non-alnum
    - apply a tiny synonym: msg -> mstaygold
    """
    t = _s(s).lower()
    t = t.replace("msg", "mstaygold")
    t = re.sub(r"[^a-z0-9]+", "", t)
    return t

def load_map_excel(path: Path, key_col: str, val_col: str) -> tuple[dict[str, str], dict[str, str]]:
    """
    Returns:
      raw_map: exact key -> basecode
      norm_map: normalized_key -> basecode (only when normalization is unique)
    """
    x = pd.read_excel(path)
    need = {key_col, val_col}
    if not need.issubset(set(x.columns)):
        raise SystemExit(f"[STOP] {path.name} missing columns: {sorted(need - set(x.columns))}")

    raw = {}
    for a, b in zip(x[key_col], x[val_col]):
        if pd.isna(a) or pd.isna(b):
            continue
        k = _s(a)
        v = _s(b)
        if k and v:
            raw[k] = v

    # Add MGCO variants deterministically
    raw2 = dict(raw)
    for k, v in raw.items():
        for kk in mgco_key_variants(k):
            raw2.setdefault(kk, v)

    # Build normalized map, but only keep unique normalized keys
    buckets: dict[str, set[str]] = {}
    for k, v in raw2.items():
        nk = norm_key(k)
        if not nk:
            continue
        buckets.setdefault(nk, set()).add(v)

    norm = {}
    for nk, vs in buckets.items():
        if len(vs) == 1:
            norm[nk] = list(vs)[0]

    return raw2, norm

def match_token_to_basecode(tok: str, raw_map: dict[str, str], norm_map: dict[str, str], all_keys_lc: list[tuple[str, str]]) -> tuple[str, str]:
    """
    Returns (basecode, how)
    how ∈ {exact, mgco, norm, substring, none}
    """
    t = _s(tok)
    if not t:
        return "", "none"

    if t in raw_map:
        return raw_map[t], "exact"

    # MGCO variants may have been added to raw_map; if token normalizes to a known MGCO variant, try those
    for kk in mgco_key_variants(t):
        if kk in raw_map:
            return raw_map[kk], "mgco"

    nk = norm_key(t)
    if nk in norm_map:
        return norm_map[nk], "norm"

    # Unique substring match on normalized form (only accept if unique)
    # all_keys_lc is list of (normalized_key, basecode) for raw keys (not just unique ones)
    # We match if token normalized is a substring of exactly one normalized key.
    if nk:
        hits = [bc for (nk_key, bc) in all_keys_lc if nk in nk_key]
        hits = sorted(set(hits))
        if len(hits) == 1:
            return hits[0], "substring"

    return "", "none"

def build_all_keys_lc(raw_map: dict[str, str]) -> list[tuple[str, str]]:
    out = []
    for k, v in raw_map.items():
        nk = norm_key(k)
        if nk:
            out.append((nk, v))
    return out

def main() -> None:
    for p in (IN_STEP1, IN_XLSX, IN_PARENT_MAP, IN_PLASMID_MAP, IN_RNA_MAP):
        if not p.exists():
            raise SystemExit(f"[STOP] missing input: {p}")

    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    step1 = pd.read_csv(IN_STEP1)
    if not {"roi_path", "date_mount_id"}.issubset(set(step1.columns)):
        raise SystemExit("[STOP] step1 csv missing required columns roi_path/date_mount_id")

    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)
    need_cols = [
        "date_mount", "mount_id",
        "ZF female genotype", "ZF male genotype",
        "additional plasmids injected", "additional mRNAs injected",
        "additonal dye and chemicals",
    ]
    for c in need_cols:
        if c not in x.columns:
            raise SystemExit(f"[STOP] Master Imaging list missing column: {c}")

    # Build session key on sheet rows
    dm = pd.to_datetime(x["date_mount"], errors="coerce")
    mid = x["mount_id"].astype(str).str.strip()
    x = x.copy()
    x["date_mount_id"] = dm.dt.strftime("%Y-%m-%d") + "__" + mid
    x["date_mount_id"] = x["date_mount_id"].where(dm.notna() & mid.ne("") & mid.ne("nan"), "")

    sheet_by_key = x.set_index("date_mount_id", drop=False)

    # Parent mapping (exact, no parsing)
    pm = pd.read_excel(IN_PARENT_MAP)
    need_pm = {"parent_fish_name", "plasmid_base_code", "allele"}
    if not need_pm.issubset(set(pm.columns)):
        raise SystemExit(f"[STOP] {IN_PARENT_MAP.name} missing columns: {sorted(need_pm - set(pm.columns))}")
    pm["parent_fish_name"] = pm["parent_fish_name"].astype(str).str.strip()
    parent_to_codes = {r["parent_fish_name"]: split_list(r.get("plasmid_base_code")) for _, r in pm.iterrows()}
    parent_to_alleles = {r["parent_fish_name"]: split_list(r.get("allele")) for _, r in pm.iterrows()}

    # Treatment mapping (robust but deterministic)
    pl_raw, pl_norm = load_map_excel(IN_PLASMID_MAP, "injected_plasmid", "plasmid_base_code")
    rna_raw, rna_norm = load_map_excel(IN_RNA_MAP, "injected_rna", "plasmid_base_code")
    pl_all_keys = build_all_keys_lc(pl_raw)
    rna_all_keys = build_all_keys_lc(rna_raw)

    missing_session = []
    unmapped_parents = []
    unmapped_treatments = []

    out_rows = []

    for _, r in step1.iterrows():
        roi_path = r["roi_path"]
        key = _s(r.get("date_mount_id"))

        if not key or key not in sheet_by_key.index:
            missing_session.append({"roi_path": roi_path, "date_mount_id": key})
            out_rows.append({
                "roi_path": roi_path,
                "date_mount_id": key,
                "genotype_base_codes": "",
                "genotype_allele_codes": "",
                "treatment_rna_base_codes": "",
                "treatment_plasmid_base_codes": "",
            })
            continue

        xr = sheet_by_key.loc[key]

        # genotype from parents via mapping only
        mom = _s(xr.get("ZF female genotype"))
        dad = _s(xr.get("ZF male genotype"))

        codes = set()
        alles = set()
        for pnm in [mom, dad]:
            if not pnm:
                continue
            if pnm in parent_to_codes:
                for c_ in parent_to_codes[pnm]:
                    if c_:
                        codes.add(c_)
                for a_ in parent_to_alleles.get(pnm, []):
                    if a_:
                        alles.add(a_)
            else:
                unmapped_parents.append({"roi_path": roi_path, "date_mount_id": key, "parent_name": pnm})

        geno_bc = ";".join(sorted(codes))
        geno_al = ";".join(sorted(alles))

        # treatment mapping from BOTH cells; classify by which map hits
        plasmid_codes = set()
        rna_codes = set()

        cells = [
            ("pl_cell", xr.get("additional plasmids injected")),
            ("rna_cell", xr.get("additional mRNAs injected")),
            ("dye_cell", xr.get("additonal dye and chemicals")),
        ]

        for src, cell in cells:
            for tok in split_tokens(cell):
                bc_pl, how_pl = match_token_to_basecode(tok, pl_raw, pl_norm, pl_all_keys)
                bc_rna, how_rna = match_token_to_basecode(tok, rna_raw, rna_norm, rna_all_keys)

                if bc_pl:
                    plasmid_codes.add(bc_pl)
                    continue
                if bc_rna:
                    rna_codes.add(bc_rna)
                    continue

                # if token looks meaningful and didn't map, log
                if _s(tok):
                    unmapped_treatments.append({"roi_path": roi_path, "date_mount_id": key, "token": tok, "source_cell": src})

        out_rows.append({
            "roi_path": roi_path,
            "date_mount_id": key,
            "genotype_base_codes": geno_bc,
            "genotype_allele_codes": geno_al,
            "treatment_rna_base_codes": ";".join(sorted(rna_codes)),
            "treatment_plasmid_base_codes": ";".join(sorted(plasmid_codes)),
        })

    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(OUT, index=False)

    pd.DataFrame(missing_session).to_csv(OUT_MISSING_SESSION, sep="\t", index=False)
    pd.DataFrame(unmapped_parents).to_csv(OUT_UNMAPPED_PARENTS, sep="\t", index=False)
    pd.DataFrame(unmapped_treatments).to_csv(OUT_UNMAPPED_TREATMENTS, sep="\t", index=False)

    qc = {
        "rows_total": int(len(out_df)),
        "rows_with_date_mount_id": int((out_df["date_mount_id"].astype(str).str.len() > 0).sum()),
        "rows_with_genotype": int((out_df["genotype_base_codes"].astype(str).str.len() > 0).sum()),
        "rows_with_rna": int((out_df["treatment_rna_base_codes"].astype(str).str.len() > 0).sum()),
        "rows_with_plasmid": int((out_df["treatment_plasmid_base_codes"].astype(str).str.len() > 0).sum()),
        "missing_session_rows": int(len(missing_session)),
        "unmapped_parent_rows": int(len(unmapped_parents)),
        "unmapped_treatment_tokens": int(len(unmapped_treatments)),
    }
    pd.DataFrame([qc]).to_csv(OUT_QC, sep="\t", index=False)

    print(f"[OK] wrote {OUT} rows={len(out_df)}")
    print(f"[QC] wrote {OUT_QC}")
    print(f"[QC] wrote {OUT_MISSING_SESSION}")
    print(f"[QC] wrote {OUT_UNMAPPED_PARENTS}")
    print(f"[QC] wrote {OUT_UNMAPPED_TREATMENTS}")

if __name__ == "__main__":
    main()
