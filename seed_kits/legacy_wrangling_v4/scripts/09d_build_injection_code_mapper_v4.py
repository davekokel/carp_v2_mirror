from __future__ import annotations

import re
from pathlib import Path
import pandas as pd

IN_PLASMID = Path("seed_kits/legacy_wrangling_v2/raw/Unique_injected_plasmid__preview_dqm.xlsx")
IN_RNA = Path("seed_kits/legacy_wrangling_v2/raw/Unique_injected_rna__preview_dqm.xlsx")

OUT_TSV = Path("seed_kits/legacy_wrangling_v4/working/injection_code_mapper_v4.tsv")
QC_DUP = Path("seed_kits/legacy_wrangling_v4/qc/injection_code_mapper_v4__dupes.tsv")
QC_EMPTY = Path("seed_kits/legacy_wrangling_v4/qc/injection_code_mapper_v4__missing.tsv")

def s(x: object) -> str:
    if x is None:
        return ""
    t = str(x).strip()
    if t.lower() in ("nan","none","na","n/a","<na>"):
        return ""
    return t

def norm_token(x: object) -> str:
    t = s(x)
    if not t:
        return ""
    t2 = t
    t2 = t2.replace("pDQM","pdqm").replace("PDQM","pdqm").replace("pSWIN","pswin").replace("PSWIN","pswin").replace("MGCO","mgco").replace("MGcO","mgco")
    t2 = t2.lower()
    t2 = re.sub(r"[^a-z0-9\-]+", "", t2)
    m = re.match(r"^([a-z]+)-?0*([0-9]+)$", t2)
    if m:
        t2 = f"{m.group(1)}-{int(m.group(2))}"
    return t2

def read_any_xlsx(p: Path) -> pd.DataFrame:
    if not p.exists():
        raise SystemExit(f"[STOP] missing file: {p}")
    xl = pd.ExcelFile(p)
    dfs = []
    for sh in xl.sheet_names:
        d = xl.parse(sh, dtype=str).fillna("")
        d.columns = [str(c).strip() for c in d.columns]
        dfs.append(d)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def pick_token_col(df: pd.DataFrame) -> str:
    cols = [c.strip() for c in df.columns]
    for c in cols:
        lc = c.lower().replace(" ", "_")
        if lc in ("injected_plasmid","injected_rna","plasmid","rna","token","name","base_code","construct"):
            return c
    for c in cols:
        if "inject" in c.lower():
            return c
    if cols:
        return cols[0]
    raise SystemExit("[STOP] no columns found in mapper xlsx")

def main() -> None:
    plas = read_any_xlsx(IN_PLASMID)
    rna = read_any_xlsx(IN_RNA)

    plas_col = pick_token_col(plas)
    rna_col = pick_token_col(rna)

    rows = []
    for v in plas[plas_col].astype(str).tolist():
        raw = s(v)
        tok = norm_token(raw)
        rows.append({"delivery_form":"plasmid", "token_raw": raw, "token_norm": tok, "base_code": tok})

    for v in rna[rna_col].astype(str).tolist():
        raw = s(v)
        tok = norm_token(raw)
        rows.append({"delivery_form":"rna", "token_raw": raw, "token_norm": tok, "base_code": tok})

    out_all = pd.DataFrame(rows).drop_duplicates()

    # QC: tokens we could not normalize at all
    missing = out_all[(out_all["token_raw"].map(s).ne("")) & (out_all["token_norm"].map(s).eq(""))][["delivery_form","token_raw"]].drop_duplicates().copy()
    # QC: multiple raw spellings collapsing to the same normalized key
    dup = (
        out_all[out_all["token_norm"].map(s).ne("")]
        .groupby(["delivery_form","token_norm"], as_index=False)
        .agg(
            n_raw=("token_raw", "size"),
            token_raws=("token_raw", lambda x: "; ".join(sorted({s(v) for v in x if s(v)}))),
            base_code=("base_code", "first"),
        )
    )
    dup = dup[dup["n_raw"].astype(int) > 1].copy()

    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    QC_DUP.parent.mkdir(parents=True, exist_ok=True)
    QC_EMPTY.parent.mkdir(parents=True, exist_ok=True)

    # Final mapping: one canonical row per (delivery_form, token_norm)
    out = (
        out_all[out_all["token_norm"].map(s).ne("")]
        .sort_values(["delivery_form","token_norm","token_raw"])
        .drop_duplicates(subset=["delivery_form","token_norm"], keep="first")
        .copy()
    )
    out.to_csv(OUT_TSV, sep="\t", index=False)

    dup.to_csv(QC_DUP, sep="\t", index=False)
    missing.to_csv(QC_EMPTY, sep="\t", index=False)

    print(str(OUT_TSV))
    print("[QC] rows", len(out))
    print("[QC] dup_keys", len(dup), str(QC_DUP))
    print("[QC] missing_norm", len(missing), str(QC_EMPTY))

if __name__ == "__main__":
    main()
