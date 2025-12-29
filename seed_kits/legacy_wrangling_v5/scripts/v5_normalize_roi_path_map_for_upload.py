from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd

SPLIT_RX = re.compile(r"[;,]\s*|\s+")
PDQM_RX = re.compile(r"^(?:p)?pdqm[-_ ]?0*(\d+)$", re.I)
MGCO_RX = re.compile(r"^(?:p)?mgco[-_ ]?0*(\d+)$", re.I)
HC_RX = re.compile(r"^(?:p)?hc[-_ ]?0*(\d+)$", re.I)
PSWIN_RX = re.compile(r"^(?:p)?pswin[-_ ]?0*(\d+)$", re.I)

DATE_MOUNT_RX = re.compile(r"/(20\d{6})_", re.I)
ANAT_RX = re.compile(r"(?:^|/)(er|mito|peroxi|histone|actin|kinectocore|centrioles|cytosol|nuclear_envelope|microtubules)(?:[^a-z]|$)", re.I)

DEFAULT_MASTER_XLSX = Path(
    "/Users/davekokel/Projects/carp_v2/seed_kits/legacy_wrangling_v5/raw/2025-12-22-161955-Cell Observatory - Zebrafish Development.xlsx"
)


def split_blob(v: Optional[str]) -> List[str]:
    if v is None:
        return []
    s = str(v).strip()
    if not s or s.lower() in {"none", "nan"}:
        return []
    return [p.strip() for p in SPLIT_RX.split(s) if p and p.strip()]


def canon_base_code(tok: str) -> Tuple[str, str]:
    t = tok.strip()
    if not t:
        return ("", "empty")

    t_lc = t.lower().replace("_", "-").replace(" ", "-")

    m = PDQM_RX.match(t_lc)
    if m:
        return (f"pdqm-{int(m.group(1))}", "ok")

    m = MGCO_RX.match(t_lc)
    if m:
        return (f"mgco-{int(m.group(1))}", "ok")

    m = HC_RX.match(t_lc)
    if m:
        return (f"hc-{int(m.group(1))}", "ok")

    m = PSWIN_RX.match(t_lc)
    if m:
        return (f"pswin-{int(m.group(1))}", "ok")

    return (t_lc, "unknown")


def canon_blob(blob: Optional[str]) -> Tuple[str, List[Tuple[str, str, str]]]:
    toks = split_blob(blob)
    out: List[str] = []
    qc: List[Tuple[str, str, str]] = []
    seen = set()

    for tok in toks:
        canon, status = canon_base_code(tok)
        if canon and canon not in seen:
            seen.add(canon)
            out.append(canon)
        qc.append((tok, canon, status))

    return ("; ".join(out), qc)


FOUNDATION_RX = re.compile(r"\b(Aang_Foundation|Korra_Foundation)\b", re.I)
DATE_MOUNT_ID_RX = re.compile(r'^(.+?)__([0-9]{4}-[0-9]{2}-[0-9]{2})__')

def fd_key_from_date_mount_id(date_mount_id: str) -> str:
    m = DATE_MOUNT_ID_RX.match((date_mount_id or "").strip())
    if not m:
        return ""
    return f"{m.group(1)}__{m.group(2)}"

def load_master_fd_map(master_xlsx: Path) -> dict[str, dict[str, str]]:
    import pandas as pd

    df = pd.read_excel(master_xlsx, sheet_name="Master Imaging list")

    col_date_mount = "date_mount"
    col_data_loc = "Data location"
    col_bday = "Date born"
    col_orient = "Mounting Orientation"
    col_dye = "additonal dye and chemicals"

    for c in [col_date_mount, col_data_loc, col_bday, col_orient, col_dye]:
        if c not in df.columns:
            raise SystemExit(f"[STOP] missing column in Master Imaging list: {c}")

    out: dict[str, dict[str, str]] = {}

    for _, r in df.iterrows():
        dl = "" if r.get(col_data_loc) is None else str(r.get(col_data_loc)).strip()
        mfd = FOUNDATION_RX.search(dl)
        if not mfd:
            continue
        foundation = mfd.group(1)
        try:
            dt = pd.to_datetime(r.get(col_date_mount), errors="coerce")
        except Exception:
            dt = None
        if dt is None or str(dt) == "NaT":
            continue
        date_s = dt.strftime("%Y-%m-%d")
        key = f"{foundation}__{date_s}"

        bday = "" if r.get(col_bday) is None else str(r.get(col_bday)).strip()
        orient = "" if r.get(col_orient) is None else str(r.get(col_orient)).strip()
        dye_raw = "" if r.get(col_dye) is None else str(r.get(col_dye)).strip()

        rec = out.get(key, {})
        if bday and not rec.get("birthday"):
            rec["birthday"] = bday
        if orient and not rec.get("orientation"):
            rec["orientation"] = orient
        if dye_raw and not rec.get("dye_raw"):
            rec["dye_raw"] = dye_raw
        out[key] = rec

    return out

def _norm_win_path_to_prefixes(data_location: str) -> list[str]:
    """
    Convert Master 'Data location' into candidate roi_path prefixes.

    Rules:
      - Extract foundation (Aang_Foundation|Korra_Foundation)
      - Extract the first folder after foundation (usually YYYYMMDD_...)
      - Candidate 1: foundation/YYYYMMDD_folder/
      - Candidate 2 (if present): foundation/YYYYMMDD_folder/<next_segment>/
        (needed when the date-folder has multiple orientations across fish subfolders)
    """
    dl = (data_location or "").strip()
    if not dl:
        return []

    # normalize slashes
    dl2 = dl.replace("\\", "/")
    # remove drive prefix like X:/abcabc/
    dl2 = re.sub(r"^[A-Za-z]:/+", "", dl2)
    # remove leading abcabc/ if present
    dl2 = re.sub(r"^abcabc/+", "", dl2)
    dl2 = dl2.strip("/")

    # find foundation segment
    mfd = FOUNDATION_RX.search(dl2)
    if not mfd:
        return []

    foundation = mfd.group(1)
    parts = [p for p in dl2.split("/") if p]

    try:
        i = next(i for i,p in enumerate(parts) if p.lower() == foundation.lower())
    except StopIteration:
        return []

    rest = parts[i+1:]
    if not rest:
        return []

    date_folder = rest[0]
    p1 = f"{foundation}/{date_folder}/"

    out = [p1]
    if len(rest) >= 2:
        out.append(f"{foundation}/{date_folder}/{rest[1]}/")
    return out


def load_master_orientation_prefix_map(master_xlsx: Path) -> dict[str, str]:
    import pandas as pd

    if not master_xlsx.exists():
        raise SystemExit(f"[STOP] master_xlsx not found: {master_xlsx}")

    df = pd.read_excel(master_xlsx, sheet_name="Master Imaging list")

    col_loc = "Data location"
    col_or = "Mounting Orientation"
    missing = [c for c in [col_loc, col_or] if c not in df.columns]
    if missing:
        raise SystemExit(f"[STOP] missing columns in Master Imaging list for orientation mapping: {missing}")

    def _s(v: object) -> str:
        if v is None:
            return ""
        if isinstance(v, float) and pd.isna(v):
            return ""
        t = str(v).strip()
        if not t:
            return ""
        if t.lower() in {"none", "nan", "nat"}:
            return ""
        return t

    rows = []
    for i, note in df.iterrows():
        ori = _s(note.get(col_or))
        loc = _s(note.get(col_loc))
        if not ori or not loc:
            continue
        prefs = _norm_win_path_to_prefixes(loc)
        if not prefs:
            continue
        rows.append((i, ori, loc, prefs))

    if not rows:
        raise SystemExit("[STOP] no usable orientation rows in Master Imaging list (need non-empty Data location + Mounting Orientation)")

    # First pass: try mapping at date-folder level (p1). If conflicts, require fish-level (p2).
    p1_to_oris: dict[str, set[str]] = {}
    p2_to_oris: dict[str, set[str]] = {}

    for _, ori, _, prefs in rows:
        p1 = prefs[0]
        p1_to_oris.setdefault(p1, set()).add(ori)
        if len(prefs) >= 2:
            p2 = prefs[1]
            p2_to_oris.setdefault(p2, set()).add(ori)

    out: dict[str, str] = {}

    # non-conflicting p1
    for p1, oris in p1_to_oris.items():
        if len(oris) == 1:
            out[p1] = next(iter(oris))

    # conflicting p1 groups must be resolved by p2
    unresolved = []
    for p1, oris in p1_to_oris.items():
        if len(oris) <= 1:
            continue

        # collect all candidate p2s under this p1
        p2s = [p2 for p2 in p2_to_oris.keys() if p2.startswith(p1)]
        if not p2s:
            unresolved.append((p1, sorted(oris), "no p2 candidates"))
            continue

        # each p2 must be single-orientation
        bad = [(p2, sorted(p2_to_oris[p2])) for p2 in p2s if len(p2_to_oris[p2]) != 1]
        if bad:
            unresolved.append((p1, sorted(oris), f"conflicting p2s: {bad[:3]}"))
            continue

        for p2 in p2s:
            out[p2] = next(iter(p2_to_oris[p2]))

    if unresolved:
        msg = ["[STOP] unresolved orientation conflicts at date-folder level; cannot deterministically map without better keys:"]
        for p1, oris, why in unresolved[:25]:
            msg.append(f"- {p1} orientations={oris} reason={why}")
        raise SystemExit("\n".join(msg))

    return out



def derive_birthday_from_path(roi_path: str) -> str:
    m = DATE_MOUNT_RX.search(roi_path or "")
    if not m:
        return ""
    ymd = m.group(1)
    if len(ymd) != 8:
        return ""
    return f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}"


def derive_anatomical_location(roi_path: str) -> str:
    s = (roi_path or "").lower()

    parts = re.split(r"[^a-z0-9]+", s)
    toks = [t for t in parts if t and not t.isdigit()]

    stop = {
        "aang","korra","foundation",
        "fish","roi",
        "af","afcam2","dsh1","dsh1cam2","affft","dffft",
        "test","matlab","decon","gpusirecon","resample","psf","otf","archive","fortm",
        "sim","lls","chromatic","shift","analysis",
    }
    toks = [t for t in toks if t not in stop]

    syn = {
        "spinal": "spinal_cord",
        "cord": "spinal_cord",
        "yolksac": "yolk_sac",
        "yolk": "yolk_sac",
        "otic": "ear",
        "ventricles": "ventricle",
        "tailbud": "tailbud",
        "hindbrain": "hindbrain",
        "forebrain": "forebrain",
        "midbrain": "midbrain",
        "brain": "brain",
        "spine": "spine",
        "tail": "tail",
        "muscle": "muscle",
        "somite": "somite",
        "eye": "eye",
        "retina": "retina",
        "lens": "lens",
        "ear": "ear",
        "heart": "heart",
        "ventricle": "ventricle",
        "blood": "blood",
        "notocord": "notochord",
        "trunk": "trunk",
        "head": "head",
        "fin": "fin",
        "gill": "gill",
        "jaw": "jaw",
    }

    hits = []
    for t in toks:
        hits.append(syn.get(t, t))

    allowed = {
        "hindbrain","forebrain","midbrain","brain",
        "spinal_cord","spine",
        "tail","tailbud",
        "muscle","somite","notochord",
        "eye","retina","lens",
        "ear",
        "heart","ventricle","blood",
        "yolk_sac",
        "head","trunk",
        "fin","gill","jaw",
    }

    out = []
    seen = set()
    for t in hits:
        if t in allowed and t not in seen:
            seen.add(t)
            out.append(t)

    order = [
        "head","brain","forebrain","midbrain","hindbrain",
        "eye","retina","lens","ear",
        "heart","ventricle","blood",
        "trunk","spinal_cord","spine",
        "muscle","somite","notochord",
        "tailbud","tail",
        "yolk_sac",
        "fin","gill","jaw",
    ]
    out_sorted = [t for t in order if t in seen]
    return "; ".join(out_sorted)

def derive_orientation(roi_path: str) -> str:
    return ""


def _fmt_date_mount_id(prefix: str, date_mount: str, mount_id: str) -> str:
    dm = (date_mount or "").strip()
    mid = (mount_id or "").strip()
    if not dm or not mid:
        return ""
    dm2 = dm.replace("/", "-")
    return f"{prefix}__{dm2}__{mid}"


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "usage: python v5_normalize_roi_path_map_for_upload.py /path/to/roi_path_to_session_markers_v5_manual_*.csv [out_dir] [master_xlsx]"
        )

    src = Path(sys.argv[1]).expanduser().resolve()
    out_dir = Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) >= 3 else src.parent
    master_xlsx = Path(sys.argv[3]).expanduser().resolve() if len(sys.argv) >= 4 else DEFAULT_MASTER_XLSX

    wide_out = out_dir / "roi_path_to_session_markers_v5_normalized.csv"
    geno_out = out_dir / "roi_genotype_constructs_v5_normalized.csv"
    trt_out = out_dir / "roi_treatment_constructs_v5_normalized.csv"
    qc_out = out_dir / "roi_path_map_v5_normalization_qc.csv"

    out_dir.mkdir(parents=True, exist_ok=True)
    master_fd_map = load_master_fd_map(master_xlsx)
    orientation_prefix_map = load_master_orientation_prefix_map(master_xlsx)

    orientation_prefixes = sorted(orientation_prefix_map.keys(), key=len, reverse=True)

    rows: List[Dict[str, str]] = []
    geno_rows: List[Dict[str, str]] = []
    trt_rows: List[Dict[str, str]] = []
    qc_rows: List[Dict[str, str]] = []

    with src.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        header = list(r.fieldnames or [])
        need = {
            "roi_path",
            "date_mount_id",
            "genotype_base_codes",
            "genotype_allele_codes",
            "treatment_rna_base_codes",
            "treatment_plasmid_base_codes",
        }
        missing = [c for c in sorted(need) if c not in header]
        if missing:
            raise SystemExit(f"[STOP] missing columns in {src}: {missing}")

        for row in r:
            roi_path = (row.get("roi_path") or "").strip()
            if not roi_path:
                continue

            gb_norm, gb_qc = canon_blob(row.get("genotype_base_codes"))
            tr_norm, tr_qc = canon_blob(row.get("treatment_rna_base_codes"))
            tp_norm, tp_qc = canon_blob(row.get("treatment_plasmid_base_codes"))

            dm_id = (row.get("date_mount_id") or "").strip()
            fd_key = fd_key_from_date_mount_id(dm_id)
            master = master_fd_map.get(fd_key, {})
            birthday = (master.get("birthday") or "").strip() or derive_birthday_from_path(roi_path)

            # strict orientation mapping: roi_path must match exactly one master-derived prefix
            orientation = ""
            hit = None
            for pref in orientation_prefixes:
                if roi_path.startswith(pref):
                    if hit is None:
                        hit = pref
                    else:
                        raise SystemExit(f"[STOP] ambiguous roi_path->orientation mapping: roi_path={roi_path} prefixes={[hit, pref]}")
            if hit is not None:
                orientation = orientation_prefix_map[hit]

            out_row = dict(row)
            out_row["genotype_base_codes_raw"] = row.get("genotype_base_codes") or ""
            out_row["treatment_rna_base_codes_raw"] = row.get("treatment_rna_base_codes") or ""
            out_row["treatment_plasmid_base_codes_raw"] = row.get("treatment_plasmid_base_codes") or ""
            out_row["genotype_base_codes"] = gb_norm
            out_row["treatment_rna_base_codes"] = tr_norm
            out_row["treatment_plasmid_base_codes"] = tp_norm
            out_row["orientation"] = orientation
            out_row["birthday"] = birthday
            out_row["anatomical_location"] = derive_anatomical_location(roi_path)
            rows.append(out_row)

            alleles = split_blob(row.get("genotype_allele_codes"))
            bases = split_blob(gb_norm)
            if bases:
                if alleles and len(alleles) == len(bases):
                    for b, a in zip(bases, alleles):
                        if b:
                            geno_rows.append({"roi_path": roi_path, "construct_base_code": b, "allele_code": (a or "").strip()})
                else:
                    for b in bases:
                        if b:
                            geno_rows.append({"roi_path": roi_path, "construct_base_code": b, "allele_code": ""})

            for b in split_blob(tr_norm):
                if b:
                    trt_rows.append({"roi_path": roi_path, "kind": "rna", "construct_base_code": b})
            for b in split_blob(tp_norm):
                if b:
                    trt_rows.append({"roi_path": roi_path, "kind": "plasmid", "construct_base_code": b})

            for (raw, canon, status) in gb_qc:
                qc_rows.append({"roi_path": roi_path, "field": "genotype_base_codes", "raw_token": raw, "canon_token": canon, "status": status})
            for (raw, canon, status) in tr_qc:
                qc_rows.append({"roi_path": roi_path, "field": "treatment_rna_base_codes", "raw_token": raw, "canon_token": canon, "status": status})
            for (raw, canon, status) in tp_qc:
                qc_rows.append({"roi_path": roi_path, "field": "treatment_plasmid_base_codes", "raw_token": raw, "canon_token": canon, "status": status})

    def write_csv(path: Path, fieldnames: List[str], recs: List[Dict[str, str]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for rr in recs:
                w.writerow({k: (rr.get(k) if rr.get(k) is not None else "") for k in fieldnames})

    wide_fields = list(rows[0].keys()) if rows else [
        "roi_path",
        "date_mount_id",
        "genotype_base_codes",
        "genotype_allele_codes",
        "treatment_rna_base_codes",
        "treatment_plasmid_base_codes",
                "genotype_base_codes_raw",
        "treatment_rna_base_codes_raw",
        "treatment_plasmid_base_codes_raw",
                "orientation",
        "birthday",
        "anatomical_location",
    ]
    write_csv(wide_out, wide_fields, rows)
    write_csv(geno_out, ["roi_path", "construct_base_code", "allele_code"], geno_rows)
    write_csv(trt_out, ["roi_path", "kind", "construct_base_code"], trt_rows)
    write_csv(qc_out, ["roi_path", "field", "raw_token", "canon_token", "status"], qc_rows)

    n_unknown = sum(1 for r in qc_rows if r["status"] != "ok")
    print(f"[OK] input:  {src}")
    print(f"[OK] wide:   {wide_out} rows={len(rows)}")
    print(f"[OK] geno:   {geno_out} rows={len(geno_rows)}")
    print(f"[OK] trt:    {trt_out} rows={len(trt_rows)}")
    print(f"[OK] qc:     {qc_out} rows={len(qc_rows)} unknown={n_unknown}")
    print(f"[OK] master_xlsx: {master_xlsx} mapped_date_mount_ids={len(master_fd_map)}")


if __name__ == "__main__":
    main()
