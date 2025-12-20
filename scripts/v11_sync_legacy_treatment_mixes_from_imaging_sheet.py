#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]

ROI_CSV_DEFAULT = ROOT / "seed_kits" / "legacy_wrangling_v3" / "working" / "legacy_imaging_annotations_for_db_v9.csv"
RNA_XLSX_DEFAULT = ROOT / "seed_kits" / "legacy_wrangling_v2" / "raw" / "Unique_injected_rna__preview_dqm.xlsx"
PLASMID_XLSX_DEFAULT = ROOT / "seed_kits" / "legacy_wrangling_v2" / "raw" / "Unique_injected_plasmid__preview_dqm.xlsx"

_NULLS = {"", "nan", "none", "na", "n/a", "<na>"}
_CANON_RE = re.compile(r"^([A-Za-z]+)[-_ ]*0*([0-9]+)$")

def _norm_cell(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in _NULLS:
        return ""
    return s

def _canon_basecode_strict(tok: str) -> str:
    t = _norm_cell(tok)
    if not t:
        raise SystemExit("[STOP] empty basecode token")
    m = _CANON_RE.match(t)
    if not m:
        raise SystemExit(f"[STOP] cannot canonicalize basecode token: {tok!r}")
    return f"{m.group(1).lower()}-{int(m.group(2))}"

def _split_basecodes_cell_strict(cell: str) -> List[str]:
    raw = _norm_cell(cell)
    if not raw:
        return []
    parts = re.split(r"[;,]+", raw)
    out: List[str] = []
    seen: Set[str] = set()
    for p in parts:
        p = _norm_cell(p)
        if not p:
            continue
        canon = _canon_basecode_strict(p)
        if canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out

def _load_crosswalk_strict(path: Path, channel: str) -> Dict[str, List[str]]:
    if not path.exists():
        raise SystemExit(f"[STOP] missing crosswalk xlsx: {path}")
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]

    if channel == "rna":
        raw_col = "injected_rna"
    elif channel == "plasmid":
        raw_col = "injected_plasmid"
    else:
        raise SystemExit(f"[STOP] invalid channel: {channel!r}")

    need = {raw_col, "plasmid_base_code"}
    missing = sorted(list(need - set(df.columns)))
    if missing:
        raise SystemExit(f"[STOP] {path} missing columns: {missing}")

    mapping: Dict[str, List[str]] = {}
    for _, r in df.iterrows():
        raw_value = _norm_cell(r.get(raw_col))
        if not raw_value:
            continue
        basecodes = _split_basecodes_cell_strict(_norm_cell(r.get("plasmid_base_code")))
        mapping[raw_value] = basecodes
    return mapping

def _resolve_dye_strict(raw: str) -> str:
    s = _norm_cell(raw)
    if not s:
        return ""
    s_norm = re.sub(r"\s+", "", s).lower()
    if s_norm in {"jf635", "jf-635"}:
        return "JF-635"
    raise SystemExit(f"[STOP] unmapped dye raw value: {raw!r}")

def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set")
    print(f"DB_URL={url}")
    return create_engine(url)

def main() -> None:
    roi_csv = Path(os.environ.get("LEGACY_ROI_CSV", str(ROI_CSV_DEFAULT)))
    rna_xlsx = Path(os.environ.get("LEGACY_RNA_XLSX", str(RNA_XLSX_DEFAULT)))
    plasmid_xlsx = Path(os.environ.get("LEGACY_PLS_XLSX", str(PLASMID_XLSX_DEFAULT)))

    if not roi_csv.exists():
        raise SystemExit(f"[STOP] missing ROI CSV: {roi_csv}")

    df = pd.read_csv(roi_csv, low_memory=False)

    need_cols = ["legacy_clutch_key", "additional plasmids injected", "additional mRNAs injected", "additonal dye and chemicals"]
    missing = [c for c in need_cols if c not in df.columns]
    if missing:
        raise SystemExit(f"[STOP] ROI CSV missing required columns: {missing}")

    rna_map = _load_crosswalk_strict(rna_xlsx, "rna")
    pls_map = _load_crosswalk_strict(plasmid_xlsx, "plasmid")

    # legacy_clutch_key -> (raw_pls, raw_rna, raw_dye) (strict: must be consistent if present)
    grouped: Dict[str, Tuple[str, str, str]] = {}
    for key, g in df.groupby(df["legacy_clutch_key"].astype(str).map(_norm_cell)):
        if not key:
            continue
        raw_pls = sorted({ _norm_cell(x) for x in g["additional plasmids injected"].tolist() if _norm_cell(x) })
        raw_rna = sorted({ _norm_cell(x) for x in g["additional mRNAs injected"].tolist() if _norm_cell(x) })
        raw_dye = sorted({ _norm_cell(x) for x in g["additonal dye and chemicals"].tolist() if _norm_cell(x) })

        def _one(vals: List[str], label: str) -> str:
            if not vals:
                return ""
            if len(vals) != 1:
                raise SystemExit(f"[STOP] legacy_clutch_key={key} has multiple distinct {label} values: {vals}")
            return vals[0]

        grouped[key] = (_one(raw_pls, "plasmid"), _one(raw_rna, "rna"), _one(raw_dye, "dye"))

    eng = get_engine(None)

    # clutch_code -> legacy_clutch_key (DB must have it populated)
    with eng.begin() as cx:
        clutch_rows = cx.execute(
            text("""
              SELECT clutch_code, legacy_clutch_key
              FROM public.clutches
              WHERE source_system='legacy_imaging'
            """)
        ).fetchall()
        clutch_to_key = { (str(cc).strip()): _norm_cell(lk) for cc, lk in clutch_rows if str(cc).strip() }

        # clutch_code -> treat_code (only clutches with treated_clutch_id)
        treat_rows = cx.execute(
            text("""
              SELECT
                c.clutch_code,
                t.treat_code
              FROM public.imaging_clutch_memberships m
              JOIN public.clutches c ON c.id = m.clutch_id
              JOIN public.treated_clutches_v11 tc ON tc.id = m.treated_clutch_id
              JOIN public.treatments t ON t.id = tc.treatment_id
              WHERE c.source_system='legacy_imaging'
                AND coalesce(t.treat_code,'') <> ''
            """)
        ).fetchall()

    # treat_code -> set(basecodes) + dyes, strict per-treat_code
    treat_payload: Dict[str, Tuple[Tuple[str,...], Tuple[str,...], Tuple[str,...]]] = {}

    for clutch_code, treat_code in treat_rows:
        clutch_code = str(clutch_code).strip()
        treat_code = str(treat_code).strip()
        lk = clutch_to_key.get(clutch_code, "")
        if not lk:
            raise SystemExit(f"[STOP] clutch_code={clutch_code} missing legacy_clutch_key in DB")
        if lk not in grouped:
            raise SystemExit(f"[STOP] legacy_clutch_key={lk} not found in ROI CSV grouping")
        raw_pls, raw_rna, raw_dye = grouped[lk]

        pls: Set[str] = set()
        rnas: Set[str] = set()
        dyes: Set[str] = set()

        if raw_pls:
            if raw_pls not in pls_map:
                raise SystemExit(f"[STOP] unmapped plasmid raw value: {raw_pls!r} (legacy_clutch_key={lk})")
            bcs = pls_map[raw_pls]
            if not bcs:
                raise SystemExit(f"[STOP] plasmid raw value mapped to empty basecodes: {raw_pls!r}")
            pls.update(bcs)

        if raw_rna:
            if raw_rna not in rna_map:
                raise SystemExit(f"[STOP] unmapped rna raw value: {raw_rna!r} (legacy_clutch_key={lk})")
            bcs = rna_map[raw_rna]
            if not bcs:
                raise SystemExit(f"[STOP] rna raw value mapped to empty basecodes: {raw_rna!r}")
            rnas.update(bcs)

        if raw_dye:
            dn = _resolve_dye_strict(raw_dye)
            if dn:
                dyes.add(dn)

        p = (tuple(sorted(pls)), tuple(sorted(rnas)), tuple(sorted(dyes)))
        if treat_code in treat_payload and treat_payload[treat_code] != p:
            raise SystemExit(
                f"[STOP] treat_code={treat_code} has inconsistent payload across clutches: "
                f"{treat_payload[treat_code]} vs {p}"
            )
        treat_payload[treat_code] = p

    with eng.begin() as cx:
        # Ensure mixes exist and (re)seed ingredients for ONLY the treat_codes in treat_payload
        for treat_code, (pls, rnas, dyes) in sorted(treat_payload.items()):
            tid = cx.execute(
                text("SELECT id::text FROM public.treatments WHERE treat_code = :tc LIMIT 1"),
                {"tc": treat_code},
            ).scalar()
            if not tid:
                raise SystemExit(f"[STOP] treatment not found for treat_code={treat_code}")

            mix_id = cx.execute(
                text("""
                  INSERT INTO public.treatment_mixes (treatment_id, mix_code, notes, created_at)
                  VALUES (:tid::uuid, 'M1', NULL, now())
                  ON CONFLICT (treatment_id, mix_code) DO UPDATE SET notes = EXCLUDED.notes
                  RETURNING id::text
                """),
                {"tid": tid},
            ).scalar()

            cx.execute(text("DELETE FROM public.treatment_mix_constructs WHERE mix_id = :m::uuid"), {"m": mix_id})
            cx.execute(text("DELETE FROM public.treatment_mix_dyes WHERE mix_id = :m::uuid"), {"m": mix_id})

            for bc in pls:
                cid = cx.execute(
                    text("SELECT id::text FROM public.constructs WHERE lower(base_code) = :bc LIMIT 1"),
                    {"bc": bc},
                ).scalar()
                if not cid:
                    raise SystemExit(f"[STOP] construct not found for plasmid base_code={bc}")
                cx.execute(
                    text("""
                      INSERT INTO public.treatment_mix_constructs (mix_id, construct_id, delivery_form, concentration, notes, created_at)
                      VALUES (:m::uuid, :c::uuid, 'plasmid', NULL, NULL, now())
                    """),
                    {"m": mix_id, "c": cid},
                )

            for bc in rnas:
                cid = cx.execute(
                    text("SELECT id::text FROM public.constructs WHERE lower(base_code) = :bc LIMIT 1"),
                    {"bc": bc},
                ).scalar()
                if not cid:
                    raise SystemExit(f"[STOP] construct not found for rna base_code={bc}")
                cx.execute(
                    text("""
                      INSERT INTO public.treatment_mix_constructs (mix_id, construct_id, delivery_form, concentration, notes, created_at)
                      VALUES (:m::uuid, :c::uuid, 'rna', NULL, NULL, now())
                    """),
                    {"m": mix_id, "c": cid},
                )

            for dn in dyes:
                did = cx.execute(
                    text("""
                      SELECT id::text
                      FROM public.dyes
                      WHERE lower(coalesce(nickname,'')) = lower(:dn)
                         OR lower(coalesce(code,'')) = lower(:dn)
                         OR lower(coalesce(display_name,'')) = lower(:dn)
                      LIMIT 1
                    """),
                    {"dn": dn},
                ).scalar()
                if not did:
                    raise SystemExit(f"[STOP] dye not found for {dn}")
                cx.execute(
                    text("""
                      INSERT INTO public.treatment_mix_dyes (mix_id, dye_id, concentration, notes, created_at)
                      VALUES (:m::uuid, :d::uuid, NULL, NULL, now())
                    """),
                    {"m": mix_id, "d": did},
                )

        qc = cx.execute(
            text("""
              WITH roi_codes AS (
                SELECT treatment_code, count(*) AS n_rois
                FROM public.v_roi_overview_rollups
                WHERE coalesce(treated_clutch_code,'') <> ''
                  AND coalesce(treatment_code,'') <> ''
                GROUP BY treatment_code
              ),
              mix AS (
                SELECT
                  t.treat_code,
                  string_agg(DISTINCT (tmc.delivery_form || '(' || lower(c.base_code) || ')'),
                             '; ' ORDER BY (tmc.delivery_form || '(' || lower(c.base_code) || ')')) AS typed_tokens
                FROM public.treatments t
                JOIN public.treatment_mixes tm ON tm.treatment_id = t.id
                LEFT JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
                LEFT JOIN public.constructs c ON c.id = tmc.construct_id
                GROUP BY t.treat_code
              )
              SELECT
                (SELECT count(*) FROM roi_codes) AS n_treatment_codes_in_rois,
                (SELECT count(*) FROM roi_codes r LEFT JOIN mix m ON m.treat_code=r.treatment_code
                  WHERE coalesce(m.typed_tokens,'') = '') AS n_roi_treatment_codes_with_blank_typed_tokens
              ;
            """)
        ).first()
        print("[OK] sync complete")
        if qc is not None:
            print("[QC]", dict(qc._mapping))

if __name__ == "__main__":
    main()
