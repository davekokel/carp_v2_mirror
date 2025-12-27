#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import pandas as pd

EMPTY_SIG = "plasmids=|rnas=|dyes="


def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s


def _canon_codes_blob(blob: object) -> str:
    s = _s(blob)
    if not s:
        return ""
    code_re = re.compile(r"(?i)\b(mgco|pdqm|pswin|swin|hc|is)\s*-?\s*0*(\d+)\b")
    out = []
    seen = set()
    for mm in code_re.finditer(s):
        pref = mm.group(1).lower()
        num = int(mm.group(2))
        if pref == "swin":
            pref = "pswin"
        tok = f"{pref}-{num}"
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return "|".join(out)



def _pipe_to_sorted_csv(pipe_blob: str) -> str:
    s = _s(pipe_blob)
    if not s:
        return ""
    parts = [p.strip() for p in s.split("|") if p.strip()]
    parts = sorted(dict.fromkeys(parts))
    return ",".join(parts)


def _signature_text(plasmids_blob: object, rnas_blob: object) -> str:
    plas_pipe = _canon_codes_blob(plasmids_blob)
    rnas_pipe = _canon_codes_blob(rnas_blob)
    return f"plasmids={_pipe_to_sorted_csv(plas_pipe)}|rnas={_pipe_to_sorted_csv(rnas_pipe)}|dyes="


def _treat_code_from_signature(sig: str) -> str:
    s = _s(sig)
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]
    return f"T-EXP-{h}"


def _legacy_clutch_key(foundation_guess: str, date_mount: str, mount_id: str) -> str:
    f = _s(foundation_guess).lower()
    d = _s(date_mount)
    m = _s(mount_id)
    if not (f and d and m):
        return ""
    return f"{f}|{d}|{m}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-tsv", default="seed_kits/legacy_wrangling_v4/working/ideal_roi_universe_v4.tsv")
    ap.add_argument("--sheet-tsv", default="seed_kits/legacy_wrangling_v4/working/imaging_sheet_normalized.tsv")
    ap.add_argument("--out", default="seed_kits/legacy_wrangling_v4/working/ideal_with_treatments_v4.tsv")
    args = ap.parse_args()

    inp = Path(args.in_tsv)
    sheet_tsv = Path(args.sheet_tsv)
    out = Path(args.out)

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

    for c in [
        "data_location_cluster",
        "data_location",
        "foundation_guess",
        "date_mount",
        "mount_id",
        "additional_plasmids_injected",
        "additional_mrnas_injected",
        "sheet_row_id",
    ]:
        if c not in sheet.columns:
            sheet[c] = ""

    sheet["data_location_cluster"] = sheet["data_location_cluster"].map(_s).str.replace("\\", "/", regex=False).str.rstrip("/")
    sheet["data_location"] = sheet["data_location"].map(_s).str.replace("\\", "/", regex=False).str.rstrip("/")

    rows = sheet.to_dict(orient="records")

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
        rp_norm = _s(rp).replace("\\", "/").rstrip("/")
        fnd_from_path = "aang" if "/Aang_Foundation/" in rp_norm else "korra" if "/Korra_Foundation/" in rp_norm else ""

        m = best_match(rp_norm)

        fnd_sheet = _s(m.get("foundation_guess")).lower()
        fnd_eff = fnd_sheet or fnd_from_path

        date_mount = _s(m.get("date_mount"))
        mount_id = _s(m.get("mount_id"))
        lck = _legacy_clutch_key(fnd_eff, date_mount, mount_id)

        plas = _canon_codes_blob(m.get("additional_plasmids_injected", ""))
        rnas = _canon_codes_blob(m.get("additional_mrnas_injected", ""))
        sig = _signature_text(plas, rnas)

        src = ""
        if _s(sig) and sig != EMPTY_SIG:
            src = "imaging_sheet"

        out_rows.append(
            {
                "roi_path": rp_norm,
                "foundation_guess": fnd_eff,
                "date_mount": date_mount,
                "mount_id": mount_id,
                "legacy_clutch_key": lck,
                "treatment_plasmid_base_codes": plas,
                "treatment_rna_base_codes": rnas,
                "signature_text": sig,
                "treat_code": "" if sig == EMPTY_SIG else _treat_code_from_signature(sig),
                "locked_treatment": "",
                "source_of_treatment": src,
            }
        )

    out_df = pd.DataFrame(out_rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out, sep="\t", index=False)
    print(str(out))
    print("[QC] rows", len(out_df))


if __name__ == "__main__":
    main()
