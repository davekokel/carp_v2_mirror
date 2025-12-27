from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

_RX_PDQM = re.compile(r"\bpdqm\s*[-_ ]?\s*0*([0-9]+)\b", re.I)
_RX_MGCO = re.compile(r"\bmgco\s*[-_ ]?\s*0*([0-9]+)\b", re.I)
_RX_ALLELE = re.compile(r"\ballele\s*([0-9]+(?:\.[0-9]+)?)\b", re.I)

def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s

def _legacy_clutch_key(foundation_guess: str, date_mount: str, mount_id: str) -> str:
    f = _s(foundation_guess).lower()
    d = _s(date_mount)
    m = _s(mount_id)
    if not (f and d and m):
        return ""
    return f"{f}|{d}|{m}"


def _norm_pipe_blob(blob: object) -> str:
    s = _s(blob).lower()
    if not s:
        return ""
    toks = [t.strip() for t in re.split(r"[|,;]+", s) if t.strip()]
    out = []
    seen = set()
    for t in toks:
        t = re.sub(r"[^a-z0-9\-]+", "", t)
        m = re.match(r"^([a-z]+)-?0*([0-9]+)$", t)
        if m:
            t = f"{m.group(1)}-{int(m.group(2))}"
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return "|".join(out)

def _norm_alleles_pipe(blob: object) -> str:
    s = _s(blob)
    if not s:
        return ""
    parts = [p.strip() for p in s.replace(",", "|").replace(";", "|").split("|") if p.strip()]
    out = []
    for p in parts:
        try:
            f = float(p)
            out.append(str(int(f)) if f.is_integer() else str(p).strip())
        except Exception:
            out.append(str(p).strip())
    return "|".join(out)

def _extract_pairs_from_text(txt: str) -> list[tuple[str, str]]:
    t = _s(txt)
    if not t:
        return []
    bases: list[str] = []
    for m in _RX_PDQM.finditer(t):
        bases.append(f"pdqm-{int(m.group(1))}")
    for m in _RX_MGCO.finditer(t):
        bases.append(f"mgco-{int(m.group(1))}")
    alleles: list[str] = []
    for m in _RX_ALLELE.finditer(t):
        try:
            f = float(m.group(1))
            alleles.append(str(int(f)) if f.is_integer() else m.group(1))
        except Exception:
            alleles.append(m.group(1))
    if not bases or not alleles:
        return []
    n = min(len(bases), len(alleles))
    return list(zip(bases[:n], alleles[:n]))

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-tsv", default="seed_kits/legacy_wrangling_v4/working/ideal_roi_universe_v4.tsv")
    ap.add_argument("--sheet-tsv", default="seed_kits/legacy_wrangling_v4/working/imaging_sheet_normalized.tsv")
    ap.add_argument("--overrides-tsv", default="seed_kits/legacy_wrangling_v4/working/experiment_genotype_overrides_v4.tsv")
    ap.add_argument("--out", default="seed_kits/legacy_wrangling_v4/working/ideal_with_genotypes_v4.tsv")
    ap.add_argument("--parent-mapper-tsv", default="seed_kits/legacy_wrangling_v4/working/parent_name_mapper_v4.tsv")
    args = ap.parse_args()

    inp = Path(args.in_tsv)
    sheet_tsv = Path(args.sheet_tsv)
    out = Path(args.out)
    overrides_tsv = Path(args.overrides_tsv)
    parent_mapper_tsv = Path(args.parent_mapper_tsv)

    if not inp.exists():
        raise SystemExit(f"[STOP] missing in-tsv: {inp}")
    if not sheet_tsv.exists():
        raise SystemExit(f"[STOP] missing sheet-tsv: {sheet_tsv}")

    base = pd.read_csv(inp, sep="\t", dtype=str, keep_default_na=False, na_filter=False)
    base.columns = [str(c).strip() for c in base.columns]
    if "roi_path" not in base.columns:
        raise SystemExit("[STOP] in-tsv missing roi_path")

    sheet = pd.read_csv(sheet_tsv, sep="\t", dtype=str, keep_default_na=False, na_filter=False)
    sheet.columns = [str(c).strip() for c in sheet.columns]
    for c in ["data_location_cluster", "data_location", "foundation_guess", "date_mount", "mount_id", "zf_female_genotype", "zf_male_genotype"]:
        if c not in sheet.columns:
            sheet[c] = ""

    sheet["data_location_cluster"] = sheet["data_location_cluster"].map(_s).str.replace("\\", "/", regex=False).str.rstrip("/")
    sheet["data_location"] = sheet["data_location"].map(_s).str.replace("\\", "/", regex=False).str.rstrip("/")

    rows = sheet.to_dict(orient="records")

    if not parent_mapper_tsv.exists():
        raise SystemExit(f"[STOP] missing parent mapper TSV: {parent_mapper_tsv}")
    pm = pd.read_csv(parent_mapper_tsv, sep="\t", dtype=str, keep_default_na=False, na_filter=False).fillna("")
    pm.columns = [str(c).strip() for c in pm.columns]
    need_pm = ["parent_fish_name_norm","genotype_base_codes","genotype_allele_codes"]
    miss_pm = [c for c in need_pm if c not in pm.columns]
    if miss_pm:
        raise SystemExit(f"[STOP] parent mapper missing columns: {miss_pm}")
    pm["parent_fish_name_norm"] = pm["parent_fish_name_norm"].map(_s)
    pm = pm[pm["parent_fish_name_norm"].ne("")].copy()
    dup = pm.groupby("parent_fish_name_norm").size()
    if int((dup > 1).sum()):
        sample = dup[dup > 1].head(25).to_string()
        raise SystemExit("[STOP] parent mapper has duplicate parent_fish_name_norm keys:\n" + sample)
    parent_map = dict(zip(pm["parent_fish_name_norm"], zip(pm["genotype_base_codes"], pm["genotype_allele_codes"])))

    overrides: dict[str, tuple[str, str]] = {}
    if overrides_tsv.exists():
        ov = pd.read_csv(overrides_tsv, sep="\t", dtype=str, keep_default_na=False, na_filter=False)
        ov.columns = [str(c).strip() for c in ov.columns]
        need = ["dataset_slug_norm", "genotype_base_codes", "genotype_allele_codes"]
        if all(c in ov.columns for c in need):
            for r in ov.to_dict(orient="records"):
                k = _s(r.get("dataset_slug_norm")).lower()
                bc = _norm_pipe_blob(r.get("genotype_base_codes"))
                al = _norm_alleles_pipe(r.get("genotype_allele_codes"))
                if k and bc and al:
                    overrides[k] = (bc, al)

    def best_match(roi_path: str) -> dict[str, str]:
        rp = _s(roi_path).replace("\\", "/").rstrip("/")
        if not rp:
            return {}
        fnd = "aang" if "/Aang_Foundation/" in rp else "korra" if "/Korra_Foundation/" in rp else ""
        best = None
        for r in rows:
            pref = _s(r.get("data_location_cluster") or r.get("data_location") or "").replace("\\", "/").rstrip("/")
            if not pref:
                continue
            if not (rp == pref or rp.startswith(pref + "/")):
                continue
            pref_len = len(pref)
            fnd_hit = 1 if (fnd and _s(r.get("foundation_guess")).lower() == fnd) else 0
            if best is None or (pref_len, fnd_hit) > (best[0], best[1]):
                best = (pref_len, fnd_hit, r)
        return best[2] if best else {}

    out_rows = []
    for rp in base["roi_path"].astype(str).map(_s).tolist():
        m = best_match(rp)

        mm = re.search(r"/(Aang_Foundation|Korra_Foundation)/([^/]+)/", rp)
        dataset_slug = mm.group(2).strip() if mm else ""
        dataset_key = dataset_slug.lower().replace("-", "_")

        mom_raw = _s(m.get("zf_female_genotype"))
        dad_raw = _s(m.get("zf_male_genotype"))

        bc_parts = []
        al_parts = []
        src = ""

        for who in (mom_raw, dad_raw):
            if not who:
                continue
            hit = parent_map.get(who)
            if not hit:
                continue
            h_bc, h_al = hit
            h_bc = _norm_pipe_blob(h_bc)
            h_al = _norm_alleles_pipe(h_al)
            if h_bc and h_al:
                bc_parts.append(h_bc)
                al_parts.append(h_al)

        bc = "|".join([x for x in bc_parts if x])
        al = "|".join([x for x in al_parts if x])

        if bc and al:
            src = "parent_name_mapper_v4"
        elif dataset_key in overrides:
            bc, al = overrides[dataset_key]
            src = "exp_overrides"

        out_rows.append(
            {
                "roi_path": rp,
                "foundation_guess": _s(m.get("foundation_guess", "")),
                "date_mount": _s(m.get("date_mount", "")),
                "mount_id": _s(m.get("mount_id", "")),
                "legacy_clutch_key": _legacy_clutch_key(_s(m.get("foundation_guess", "")), _s(m.get("date_mount", "")), _s(m.get("mount_id", ""))),
                "genotype_base_codes": _norm_pipe_blob(bc),
                "genotype_allele_codes": _norm_alleles_pipe(al),
                "locked_genotype": "",
                "source_of_genotype": src,
            }
        )
    out_df = pd.DataFrame(out_rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out, sep="\t", index=False)
    print(str(out))
    print("[QC] rows", len(out_df))

if __name__ == "__main__":
    main()
