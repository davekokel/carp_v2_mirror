from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

REPO = Path(__file__).resolve().parents[3]

DB = REPO / "seed_kits" / "legacy_wrangling_v3" / "working" / "legacy_imaging_annotations_for_db_v9.csv"
CONSTRUCTS = REPO / "seed_kits" / "2025-11-15-121231-autoload" / "constructs_plasmid.csv"
TAGS = REPO / "seed_kits" / "2025-11-15-121231-autoload" / "tags.xlsx"

OUT = REPO / "seed_kits" / "legacy_wrangling_v3" / "working" / "qc_enrich_overrides_suggestions.csv"

BASECODE_RE = re.compile(r"\b(pDQM\d{3}|MGCO-\d{2}|pSWIN\d{2})\b", flags=re.I)

def nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s.lower() not in ("", "nan", "none", "<na>")

def norm_token(s: str) -> str:
    s = str(s).lower()
    s = s.replace("\\", "/")
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def extract_basecodes(text) -> list[str]:
    if not nonempty(text):
        return []
    s = str(text)
    hits = BASECODE_RE.findall(s)
    out = []
    seen = set()
    for h in hits:
        h = h.replace("mgco", "MGCO").replace("pdqm", "pDQM").replace("pswin", "pSWIN")
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out

def split_pipe(v) -> set[str]:
    if not nonempty(v):
        return set()
    parts = re.split(r"[|,;]+", str(v))
    out = set()
    for p in parts:
        p = norm_token(p)
        if p:
            out.add(p)
    return out

def score_construct(row, c) -> int:
    score = 0
    fluor = norm_token(c.get("fluor_code", ""))
    tag = norm_token(c.get("tag_code", ""))
    loc = norm_token(c.get("localization", ""))

    if row["fluor_hints"] and fluor and fluor in row["fluor_hints"]:
        score += 3
    if row["organelle_hints"]:
        for o in row["organelle_hints"]:
            if o and (o in loc or o in tag):
                score += 2
    if row["experiment_label_hints"]:
        for t in row["experiment_label_hints"]:
            if t and (t in tag or t in loc):
                score += 1
    return score

def main() -> None:
    df = pd.read_csv(DB, low_memory=False)
    con = pd.read_csv(CONSTRUCTS, low_memory=False)
    tags = pd.read_excel(TAGS)

    if "dataset_slug_norm" not in df.columns:
        raise SystemExit("Missing dataset_slug_norm in DB CSV")

    need = df.copy()
    def is_empty_col(s):
        s = s.fillna("").astype(str).str.strip().str.lower()
        return s.isin(["", "nan", "none", "<na>"])

    needs_geno = is_empty_col(need.get("genotype_base_codes", pd.Series([""]*len(need)))) & is_empty_col(need.get("genotype_allele_codes", pd.Series([""]*len(need))))
    needs_tx = is_empty_col(need.get("treatment_rna_base_codes", pd.Series([""]*len(need)))) & is_empty_col(need.get("treatment_plasmid_base_codes", pd.Series([""]*len(need))))
    need = need[needs_geno & needs_tx].copy()

    want_slugs = sorted(need["dataset_slug_norm"].astype(str).unique().tolist())

    tag_small = tags.copy()
    if "nickname" in tag_small.columns:
        tag_small = tag_small.rename(columns={"nickname": "tag_code"})
    if "localization" not in tag_small.columns:
        tag_small["localization"] = pd.NA
    tag_small = tag_small[["tag_code", "localization"]].drop_duplicates()

    con2 = con.copy()
    if "tag_code" not in con2.columns:
        con2["tag_code"] = pd.NA
    if "fluor_code" not in con2.columns:
        con2["fluor_code"] = pd.NA
    con2 = con2.merge(tag_small, on="tag_code", how="left")
    con2["localization"] = con2.get("localization", pd.Series([pd.NA]*len(con2))).astype("string")

    rows = []
    for slug in want_slugs:
        sub = need[need["dataset_slug_norm"].astype(str) == slug].copy()

        pl_texts = sub.get("additional plasmids injected", pd.Series([], dtype=object)).dropna().tolist()
        rna_texts = sub.get("additional mRNAs injected", pd.Series([], dtype=object)).dropna().tolist()

        pl_codes = []
        for t in pl_texts:
            pl_codes += extract_basecodes(t)
        rna_codes = []
        for t in rna_texts:
            rna_codes += extract_basecodes(t)

        def uniq(xs):
            out=[]
            seen=set()
            for x in xs:
                if x not in seen:
                    seen.add(x)
                    out.append(x)
            return out

        pl_codes = uniq(pl_codes)
        rna_codes = uniq(rna_codes)

        hint_row = {
            "fluor_hints": split_pipe((sub.get("fluor_hints", pd.Series([""])).dropna().head(1).tolist() or [""])[0]),
            "organelle_hints": split_pipe((sub.get("organelle_hints", pd.Series([""])).dropna().head(1).tolist() or [""])[0]),
            "experiment_label_hints": split_pipe((sub.get("experiment_label_hints", pd.Series([""])).dropna().head(1).tolist() or [""])[0]),
        }

        scored = []
        for _, c in con2.iterrows():
            if str(c.get("plasmid_code", "")).strip() == "":
                continue
            sc = score_construct(hint_row, c)
            if sc > 0:
                scored.append((sc, str(c["plasmid_code"]), str(c.get("fluor_code","")), str(c.get("tag_code","")), str(c.get("localization",""))))

        scored.sort(key=lambda t: (-t[0], t[1]))
        top = scored[:10]

        rows.append({
            "dataset_slug_norm": slug,
            "n_rows": len(sub),
            "direct_plasmid_basecodes": "|".join(pl_codes),
            "direct_rna_basecodes": "|".join(rna_codes),
            "top_construct_candidates": "|".join([f"{sc}:{code}" for sc,code,_,_,_ in top]),
            "top_construct_details": "|".join([f"{code}[{fc},{tg},{loc}]" for sc,code,fc,tg,loc in top]),
        })

    out = pd.DataFrame(rows).sort_values(["n_rows","dataset_slug_norm"], ascending=[False, True])
    out.to_csv(OUT, index=False)
    print("DB", DB)
    print("NEED_SLUGS", len(out))
    print("WROTE", OUT)

if __name__ == "__main__":
    main()
