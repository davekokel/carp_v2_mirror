from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

CLUSTER_PREFIX = "/clusterfs/vast/abcabc/"
TIFF_LIST_DEFAULT = "seed_kits/legacy_wrangling_v4/raw/foundation_tiff_files_20251223_140835.txt"
SHEET_TSV_DEFAULT = "seed_kits/legacy_wrangling_v4/working/imaging_sheet_normalized.tsv"
OVERRIDES_TSV_DEFAULT = "seed_kits/legacy_wrangling_v4/working/experiment_genotype_overrides_v4.tsv"
OUT_DEFAULT = "seed_kits/legacy_wrangling_v4/working/ideal_imaging_import_sheet_v4.raw.tsv"

EMPTY_SIG = "plasmids=|rnas=|dyes="

_RX_ROI_SEG = re.compile(r"roi\d+", re.I)
_RX_FISH_SEG = re.compile(r"^fish\d+[_\-]", re.I)
_RX_CODE = re.compile(r"\b(?P<prefix>pdqm|mgco)\s*[-_ ]?\s*0*(?P<num>\d{1,5})\b", re.I)
_RX_TG_CODE = re.compile(r"\bTg\(\s*(?P<prefix>pDQM|MGCO)\s*0*(?P<num>\d{1,5})\s*\)\s*(?P<allele>\d+(?:\.\d+)?)\b", re.I)
_RX_ALLELE = re.compile(r"\ballele\s*(?P<allele>\d+(?:\.\d+)?)\b", re.I)

def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s

def _to_posix(p: str) -> str:
    t = _s(p)
    if not t:
        return ""
    return t.replace("\\", "/").replace("//", "/")

def _to_cluster_path_from_tiff_list(line: str) -> str:
    t = _to_posix(line).lstrip("/")
    if not t:
        return ""
    if t.startswith("Aang_Foundation/") or t.startswith("Korra_Foundation/"):
        return CLUSTER_PREFIX + t
    if t.startswith("abcabc/Aang_Foundation/") or t.startswith("abcabc/Korra_Foundation/"):
        return CLUSTER_PREFIX + t.split("abcabc/", 1)[1]
    if t.startswith(CLUSTER_PREFIX.lstrip("/")):
        return "/" + t
    if t.startswith(CLUSTER_PREFIX):
        return t
    return ""

def _foundation_from_cluster_path(p: str) -> str:
    t = _s(p)
    if "/Aang_Foundation/" in t:
        return "aang"
    if "/Korra_Foundation/" in t:
        return "korra"
    return ""

def _dataset_slug_from_cluster_path(p: str) -> str:
    t = _s(p)
    m = re.search(r"/(Aang_Foundation|Korra_Foundation)/([^/]+)/", t)
    if not m:
        return ""
    return m.group(2).strip()

def _to_windows_from_cluster(p: str) -> str:
    t = _s(p)
    if not t.startswith(CLUSTER_PREFIX):
        return ""
    rel = t[len(CLUSTER_PREFIX):].replace("/", "\\")
    return "X:\\abcabc\\" + rel

def _roi_dir_from_cluster_file_path(fp: str) -> str:
    p = _to_posix(fp)
    if not p.startswith(CLUSTER_PREFIX):
        return ""
    parts = [x for x in p.split("/") if x]
    if len(parts) < 6:
        return ""
    try:
        i_fnd = parts.index("abcabc") + 1
    except ValueError:
        return ""
    fnd = parts[i_fnd]
    if fnd not in ("Aang_Foundation", "Korra_Foundation"):
        return ""

    idx_last = len(parts) - 1
    dir_parts = parts[:-1] if "." in parts[idx_last] else parts[:]

    roi_idx = None
    for i in range(len(dir_parts) - 1, 0, -1):
        if _RX_ROI_SEG.search(dir_parts[i]):
            roi_idx = i
            break
    if roi_idx is not None:
        return "/" + "/".join(dir_parts[: roi_idx + 1])

    fish_idx = None
    for i in range(len(dir_parts) - 1, 0, -1):
        if _RX_FISH_SEG.search(dir_parts[i]) or dir_parts[i].lower().startswith("fish"):
            fish_idx = i
            break
    if fish_idx is not None:
        return "/" + "/".join(dir_parts[: fish_idx + 1])

    return "/" + "/".join(dir_parts[: i_fnd + 2])

def _best_sheet_match(roi_dir: str, sheet_rows: List[Dict[str, str]]) -> Dict[str, str]:
    rp = _s(roi_dir)
    if not rp:
        return {}
    fnd = _foundation_from_cluster_path(rp)

    best: Optional[Tuple[int, int, Dict[str, str]]] = None
    for r in sheet_rows:
        pref = _s(r.get("data_location_cluster") or r.get("data_location") or r.get("data_location_raw") or "")
        pref = _to_posix(pref).rstrip("/")
        if not pref:
            continue
        rp2 = _to_posix(rp)
        if not (rp2 == pref or rp2.startswith(pref + "/")):
            continue

        pref_len = len(pref)
        fnd_hit = 1 if (fnd and _s(r.get("foundation_guess")).lower() == fnd) else 0
        if best is None or (pref_len, fnd_hit) > (best[0], best[1]):
            best = (pref_len, fnd_hit, r)

    return best[2] if best else {}

def _canon_base_code(prefix: str, num: str) -> str:
    p = prefix.lower().strip()
    n = str(int(num))
    return f"{p}-{n}"

def _norm_pipe_blob(blob: str) -> str:
    s = _s(blob)
    if not s:
        return ""
    parts = [p.strip() for p in s.replace(",", "|").replace(";", "|").split("|") if p.strip()]
    out: List[str] = []
    seen = set()
    for p in parts:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return "|".join(out)

def _norm_alleles_pipe(blob: str) -> str:
    s = _s(blob)
    if not s:
        return ""
    parts = [p.strip() for p in s.replace(",", "|").replace(";", "|").split("|") if p.strip()]
    out: List[str] = []
    for p in parts:
        try:
            f = float(p)
            out.append(str(int(f)) if f.is_integer() else p.strip())
        except Exception:
            out.append(p.strip())
    return "|".join(out)

def _extract_pairs_from_text(txt: str) -> List[Tuple[str, str]]:
    t = _s(txt)
    if not t:
        return []
    out: List[Tuple[str, str]] = []

    for m in _RX_TG_CODE.finditer(t):
        bc = _canon_base_code(m.group("prefix"), m.group("num"))
        allele = m.group("allele")
        try:
            f = float(allele)
            allele = str(int(f)) if f.is_integer() else allele
        except Exception:
            pass
        out.append((bc, allele))

    for m in _RX_CODE.finditer(t):
        bc = _canon_base_code(m.group("prefix"), m.group("num"))
        allele = ""
        m2 = _RX_ALLELE.search(t[m.end():m.end()+80])
        if m2:
            a = m2.group("allele")
            try:
                f = float(a)
                a = str(int(f)) if f.is_integer() else a
            except Exception:
                pass
            allele = a
        out.append((bc, allele))

    uniq: List[Tuple[str, str]] = []
    seen = set()
    for bc, al in out:
        key = (bc, al)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(key)
    return uniq

def _load_overrides(path: Path) -> Dict[str, Tuple[str, str]]:
    if not path.exists():
        return {}
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, na_filter=False)
    df.columns = [str(c).strip() for c in df.columns]
    key_col = None
    for c in ("dataset_slug_norm", "dataset_slug", "experiment_name", "experiment_name_norm"):
        if c in df.columns:
            key_col = c
            break
    if key_col is None:
        return {}

    if "genotype_base_codes" not in df.columns or "genotype_allele_codes" not in df.columns:
        return {}

    out: Dict[str, Tuple[str, str]] = {}
    for r in df.to_dict(orient="records"):
        k = _s(r.get(key_col)).lower()
        if not k:
            continue
        bc = _norm_pipe_blob(_s(r.get("genotype_base_codes")))
        al = _norm_alleles_pipe(_s(r.get("genotype_allele_codes")))
        if bc and al:
            out[k] = (bc, al)
    return out

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiff-list", default=TIFF_LIST_DEFAULT)
    ap.add_argument("--sheet-tsv", default=SHEET_TSV_DEFAULT)
    ap.add_argument("--overrides-tsv", default=OVERRIDES_TSV_DEFAULT)
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args()

    tiff_list = Path(args.tiff_list)
    sheet_tsv = Path(args.sheet_tsv)
    overrides_tsv = Path(args.overrides_tsv)
    out = Path(args.out)

    if not tiff_list.exists():
        raise SystemExit(f"[STOP] missing tiff list: {tiff_list}")
    if not sheet_tsv.exists():
        raise SystemExit(f"[STOP] missing imaging_sheet_normalized.tsv: {sheet_tsv}")

    overrides = _load_overrides(overrides_tsv)

    sheet = pd.read_csv(sheet_tsv, sep="\t", dtype=str, keep_default_na=False, na_filter=False)
    sheet.columns = [str(c).strip() for c in sheet.columns]
    for c in [
        "sheet_row_id",
        "date_mount",
        "mount_id",
        "data_location_raw",
        "data_location_cluster",
        "data_location",
        "foundation_guess",
        "experiment_key_guess",
        "zf_female_genotype",
        "zf_male_genotype",
        "additional_plasmids_injected",
        "additional_mrnas_injected",
        "free_text_label",
    ]:
        if c not in sheet.columns:
            sheet[c] = ""
    sheet_rows = sheet.to_dict(orient="records")

    roi_dirs = set()
    with tiff_list.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cluster_fp = _to_cluster_path_from_tiff_list(line)
            if not cluster_fp:
                continue
            rd = _roi_dir_from_cluster_file_path(cluster_fp)
            if rd:
                roi_dirs.add(rd)

    roi_dirs = sorted(roi_dirs)

    out_rows = []
    for rd in roi_dirs:
        m = _best_sheet_match(rd, sheet_rows)
        dataset_slug = _dataset_slug_from_cluster_path(rd)
        dataset_slug_key = dataset_slug.strip().lower()
        foundation = _s(m.get("foundation_guess")) or _foundation_from_cluster_path(rd)

        gtxt = " ".join([_s(m.get("zf_female_genotype")), _s(m.get("zf_male_genotype"))]).strip()

        pairs = _extract_pairs_from_text(gtxt)
        bc = ""
        al = ""
        if pairs:
            bc = "|".join([p[0] for p in pairs if p[0]])
            al = "|".join([p[1] for p in pairs if p[1]])

        if (not bc or not al) and dataset_slug_key in overrides:
            bc2, al2 = overrides[dataset_slug_key]
            bc = bc or bc2
            al = al or al2

        out_rows.append(
            {
                "roi_path": rd,
                "windows_path": _to_windows_from_cluster(rd),
                "foundation": foundation,
                "dataset_slug": dataset_slug,
                "sheet_row_id": _s(m.get("sheet_row_id")),
                "date_mount": _s(m.get("date_mount")),
                "mount_id": _s(m.get("mount_id")),
                "data_location_cluster": _s(m.get("data_location_cluster")),
                "zf_female_genotype": _s(m.get("zf_female_genotype")),
                "zf_male_genotype": _s(m.get("zf_male_genotype")),
                "additional_plasmids_injected": _s(m.get("additional_plasmids_injected")),
                "additional_mrnas_injected": _s(m.get("additional_mrnas_injected")),
                "free_text_label": _s(m.get("free_text_label")),
                "genotype_base_codes": _norm_pipe_blob(bc),
                "genotype_allele_codes": _norm_alleles_pipe(al),
                "treatment_plasmid_base_codes": "",
                "treatment_rna_base_codes": "",
                "signature_text": EMPTY_SIG,
                "treat_code": "",
                "include_in_db": "false" if dataset_slug.lower() == "analysis_test" else "true",
                "source_of_genotype": "imaging_sheet" if (bc and al) else ("exp_overrides" if dataset_slug_key in overrides else ""),
                "source_of_treatment": "",
                "locked_genotype": "",
                "locked_treatment": "",
                "inferred_row": "false",
                "link_source": "raw_tiff_list+raw_xlsx_prefix_match",
            }
        )

    df = pd.DataFrame(out_rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, sep="\t", index=False)
    print(str(out))
    print("[QC] roi_dirs", len(df))

if __name__ == "__main__":
    main()
