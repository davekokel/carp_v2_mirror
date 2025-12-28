from __future__ import annotations

from pathlib import Path
import pandas as pd
import re

ROOT = Path("~/Projects/carp_v2/seed_kits/legacy_wrangling_v5").expanduser()
RAW = ROOT / "raw"
WORKING = ROOT / "working"
QC = ROOT / "qc_runs"

IN_STEP1 = WORKING / "roi_path_to_session_step14_v5.csv"
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
RE_SPLIT = re.compile(r"[;,|+]+|\\s+|[()\\[\\]{}]+")  # NOTE: ':' is NOT a delimiter

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
    t = _s(s).lower()
    t = t.replace("msg", "mstaygold")
    t = re.sub(r"[^a-z0-9:]+", "", t)  # keep ':' now that we preserve it in tokens
    return t

def load_map_excel(path: Path, key_col: str, val_col: str) -> tuple[dict[str, str], dict[str, str], list[tuple[str, str]]]:
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

    raw2 = dict(raw)
    for k, v in raw.items():
        for kk in mgco_key_variants(k):
            raw2.setdefault(kk, v)

    buckets: dict[str, set[str]] = {}
    all_keys = []
    for k, v in raw2.items():
        nk = norm_key(k)
        if nk:
            all_keys.append((nk, v))
            buckets.setdefault(nk, set()).add(v)

    norm = {}
    for nk, vs in buckets.items():
        if len(vs) == 1:
            norm[nk] = list(vs)[0]

    return raw2, norm, all_keys

def match_token(tok: str, raw_map: dict[str, str], norm_map: dict[str, str], all_keys: list[tuple[str, str]]) -> tuple[str, str]:
    t = _s(tok)
    if not t:
        return "", "none"
    if t in raw_map:
        return raw_map[t], "exact"
    for kk in mgco_key_variants(t):
        if kk in raw_map:
            return raw_map[kk], "mgco"
    nk = norm_key(t)
    if nk in norm_map:
        return norm_map[nk], "norm"
    if nk and len(nk) >= 6:
        hits = [bc for (nk_key, bc) in all_keys if nk in nk_key]
        hits = sorted(set(hits))
        if len(hits) == 1:
            return hits[0], "substring"
    return "", "none"

def build_session_id(fr: str, date_mount, mount_id) -> str:
    dm = pd.to_datetime(date_mount, errors="coerce")
    mid = _s(mount_id)
    if fr and pd.notna(dm) and mid:
        return f"{fr}__{dm.strftime('%Y-%m-%d')}__{mid}"
    return ""

def main() -> None:
    for p in (IN_STEP1, IN_XLSX, IN_PARENT_MAP, IN_PLASMID_MAP, IN_RNA_MAP):
        if not p.exists():
            raise SystemExit(f"[STOP] missing input: {p}")

    WORKING.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)

    step1 = pd.read_csv(IN_STEP1)
    if not {"roi_path", "session_id"}.issubset(set(step1.columns)):
        raise SystemExit("[STOP] step1 csv missing roi_path/session_id")

    x = pd.read_excel(IN_XLSX, sheet_name=SHEET)
    need_cols = [
        "Data location", "date_mount", "mount_id",
        "ZF female genotype", "ZF male genotype",
        "additional plasmids injected", "additional mRNAs injected",
        "additonal dye and chemicals",
    ]
    for c in need_cols:
        if c not in x.columns:
            raise SystemExit(f"[STOP] Master Imaging list missing column: {c}")

    x = x.copy()
    x["dl"] = x["Data location"].astype(str).str.replace("\\\\", "/", regex=False)
    x["foundation_root"] = x["dl"].str.extract(r"(Aang_Foundation|Korra_Foundation)")[0].fillna("")
    x["session_id"] = [build_session_id(fr, dm, mid) for fr, dm, mid in zip(x["foundation_root"], x["date_mount"], x["mount_id"])]

    sheet_by_key = x.set_index("session_id", drop=False)

    pm = pd.read_excel(IN_PARENT_MAP)
    need_pm = {"parent_fish_name", "plasmid_base_code", "allele"}
    if not need_pm.issubset(set(pm.columns)):
        raise SystemExit(f"[STOP] {IN_PARENT_MAP.name} missing columns: {sorted(need_pm - set(pm.columns))}")
    pm["parent_fish_name"] = pm["parent_fish_name"].astype(str).str.strip()
    parent_to_codes = {r["parent_fish_name"]: split_list(r.get("plasmid_base_code")) for _, r in pm.iterrows()}
    parent_to_alleles = {r["parent_fish_name"]: split_list(r.get("allele")) for _, r in pm.iterrows()}

    pl_raw, pl_norm, pl_all = load_map_excel(IN_PLASMID_MAP, "injected_plasmid", "plasmid_base_code")
    rna_raw, rna_norm, rna_all = load_map_excel(IN_RNA_MAP, "injected_rna", "plasmid_base_code")

    missing_session = []
    unmapped_parents = []
    unmapped_treatments = []

    out_rows = []

    for _, r in step1.iterrows():
        roi_path = r["roi_path"]
        sid = _s(r.get("session_id"))

        if not sid or sid not in sheet_by_key.index:
            missing_session.append({"roi_path": roi_path, "session_id": sid})
            out_rows.append({
                "roi_path": roi_path,
                "date_mount_id": sid,
                "genotype_base_codes": "",
                "genotype_allele_codes": "",
                "treatment_rna_base_codes": "",
                "treatment_plasmid_base_codes": "",
            })
            continue

        xr = sheet_by_key.loc[sid]

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
                unmapped_parents.append({"roi_path": roi_path, "session_id": sid, "parent_name": pnm})

        plasmid_codes = set()
        rna_codes = set()

        cells = [
            ("pl_cell", xr.get("additional plasmids injected")),
            ("rna_cell", xr.get("additional mRNAs injected")),
            ("dye_cell", xr.get("additonal dye and chemicals")),
        ]

        for src, cell in cells:
            for tok in split_tokens(cell):
                bc_pl, _ = match_token(tok, pl_raw, pl_norm, pl_all)
                bc_rna, _ = match_token(tok, rna_raw, rna_norm, rna_all)
                if bc_pl:
                    plasmid_codes.add(bc_pl)
                    continue
                if bc_rna:
                    rna_codes.add(bc_rna)
                    continue
                if _s(tok):
                    unmapped_treatments.append({"roi_path": roi_path, "session_id": sid, "token": tok, "source_cell": src})

        out_rows.append({
            "roi_path": roi_path,
            "date_mount_id": sid,
            "genotype_base_codes": ";".join(sorted(codes)),
            "genotype_allele_codes": ";".join(sorted(alles)),
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
        "rows_with_session_id": int((out_df["date_mount_id"].astype(str).str.len() > 0).sum()),
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
