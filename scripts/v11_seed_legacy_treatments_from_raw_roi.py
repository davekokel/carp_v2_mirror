#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import hashlib
from typing import Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

TOKEN_SPLIT = re.compile(r"[|,; ]+")
TOKEN_RE = re.compile(r"^([A-Za-z]+)[-_ ]*(0*)(\d+)$")


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set")
    print(f"DB_URL={url}")
    return create_engine(url)


def _canon_one(tok: str) -> Optional[str]:
    s = (tok or "").strip()
    if not s:
        return None
    s_l = s.lower()
    if s_l in ("nan", "none", "na", "n/a", "<na>"):
        return None
    m = TOKEN_RE.match(s)
    if not m:
        return s_l
    prefix = m.group(1).lower()
    num = int(m.group(3))
    if prefix == "swin":
        prefix = "pswin"
    return f"{prefix}-{num}"


def canon_tokens(raw: Optional[str]) -> List[str]:
    if raw is None:
        return []
    parts = [p.strip() for p in TOKEN_SPLIT.split(str(raw)) if p.strip()]
    out: List[str] = []
    for p in parts:
        c = _canon_one(p)
        if c:
            out.append(c)
    return sorted(dict.fromkeys(out))


def treat_code_for(rna: List[str], plasmid: List[str]) -> str:
    sig = f"rna={';'.join(rna)}|plasmid={';'.join(plasmid)}"
    h = hashlib.sha1(sig.encode("utf-8")).hexdigest()[:10]
    return f"LEGTR-{h}"


def treat_text_for(rna: List[str], plasmid: List[str]) -> str:
    parts: List[str] = []
    if rna:
        parts.append("rna(" + ", ".join(rna) + ")")
    if plasmid:
        parts.append("plasmid(" + ", ".join(plasmid) + ")")
    return "; ".join(parts) if parts else ""


def main() -> None:
    eng = get_engine()

    # -----------------------------
    # Scope: only keys that exist in public.clutches (legacy_imaging)
    # This keeps "raw universe" and "loaded universe" aligned.
    # -----------------------------
    with eng.begin() as cx:
        clutch_rows = cx.execute(
            text(
                """
                SELECT clutch_code, id::uuid AS clutch_id, legacy_clutch_key
                FROM public.clutches
                WHERE source_system='legacy_imaging'
                  AND COALESCE(btrim(legacy_clutch_key),'') <> '';
                """
            )
        ).fetchall()

    clutch_by_key: Dict[str, Tuple[str, str]] = {}
    for clutch_code, clutch_id, lk in clutch_rows:
        clutch_by_key[str(lk).strip()] = (str(clutch_id), str(clutch_code).strip())

    if not clutch_by_key:
        raise SystemExit("[STOP] no legacy_imaging clutches with legacy_clutch_key found in DB")

    # -----------------------------
    # Pull raw treatment signatures, but ONLY for keys present in clutches
    # -----------------------------
    with eng.begin() as cx:
        rows = cx.execute(
            text(
                """
                SELECT
                  r.legacy_clutch_key,
                  NULLIF(btrim(COALESCE(r.treatment_rna_rna_base_code_from_enrich, r.treatment_rna_rna_base_code)), '') AS rna_raw,
                  NULLIF(btrim(COALESCE(r.treatment_plasmid_plasmid_base_code_from_enrich, r.treatment_plasmid_plasmid_base_code)), '') AS plasmid_raw
                FROM raw.legacy_roi_enriched_v9 r
                JOIN public.clutches c
                  ON c.source_system='legacy_imaging'
                 AND c.legacy_clutch_key = r.legacy_clutch_key
                WHERE COALESCE(btrim(r.legacy_clutch_key), '') <> '';
                """
            )
        ).fetchall()

    # Build signatures per legacy_clutch_key.
    # Rule:
    # - blank rows are allowed IF there is exactly one nonempty signature for that key
    # - but multiple distinct NONEMPTY signatures is a hard stop
    by_key_sigs: Dict[str, Dict[Tuple[str, str], int]] = {}
    for lk, rna_raw, pl_raw in rows:
        key = (lk or "").strip()
        if not key:
            continue
        rna = canon_tokens(rna_raw)
        plasmid = canon_tokens(pl_raw)
        sig = (";".join(rna), ";".join(plasmid))
        by_key_sigs.setdefault(key, {})
        by_key_sigs[key][sig] = by_key_sigs[key].get(sig, 0) + 1

    mixed_blank_nonblank = 0
    multi_nonempty = 0

    by_key_final: Dict[str, Tuple[List[str], List[str]]] = {}
    for key, sig_counts in by_key_sigs.items():
        sigs = list(sig_counts.keys())
        nonempty = [s for s in sigs if (s[0] != "" or s[1] != "")]
        if len(nonempty) == 0:
            by_key_final[key] = ([], [])
            continue
        if len(nonempty) > 1:
            multi_nonempty += 1
            sample = "\n  - " + "\n  - ".join([f"{s} (n={sig_counts[s]})" for s in nonempty[:20]])
            raise SystemExit(f"[STOP] legacy_clutch_key={key} has multiple NONEMPTY treatment signatures:{sample}")
        # Exactly one nonempty; allow blank/nonblank mixture but count it
        if len(sigs) > 1:
            mixed_blank_nonblank += 1
        rna_s, pl_s = nonempty[0]
        rna = [t for t in rna_s.split(";") if t]
        plasmid = [t for t in pl_s.split(";") if t]
        by_key_final[key] = (rna, plasmid)

    keys_with_any = [k for k, (r, p) in by_key_final.items() if r or p]
    print(f"[INFO] legacy_clutch_key (DB scope) total={len(by_key_final)} with_any_treatment={len(keys_with_any)}")
    print(f"[QC] legacy_clutch_key mixed blank/nonblank treatment rows: {mixed_blank_nonblank}")
    print(f"[QC] legacy_clutch_key with multiple NONEMPTY signatures: {multi_nonempty}")

    if not keys_with_any:
        print("[OK] No legacy treatments to create (within DB scope).")
        return

    # Validate construct tokens exist.
    all_tokens = sorted(set(t for k in keys_with_any for t in (by_key_final[k][0] + by_key_final[k][1])))
    with eng.begin() as cx:
        found = cx.execute(
            text(
                """
                SELECT lower(base_code) AS base_code, id::uuid AS construct_id
                FROM public.constructs
                WHERE lower(base_code) = ANY(CAST(:toks AS text[]));
                """
            ),
            {"toks": all_tokens},
        ).fetchall()

    construct_id_by_base: Dict[str, str] = {str(bc): str(cid) for bc, cid in found}
    if len(construct_id_by_base) != len(all_tokens):
        missing = [t for t in all_tokens if t not in construct_id_by_base]
        sample = "\n  - " + "\n  - ".join(missing[:50])
        raise SystemExit(f"[STOP] construct lookup failed for {len(missing)} token(s). Sample:{sample}")

    upsert_treatment = text(
        """
        INSERT INTO public.treatments (treat_code, kind_code, treat_text, source_system, import_batch_id, created_at)
        VALUES (:treat_code, :kind_code, :treat_text, 'legacy_imaging', :batch, now())
        ON CONFLICT (treat_code) DO UPDATE
        SET treat_text = EXCLUDED.treat_text
        RETURNING id::uuid;
        """
    )

    ensure_mix = text(
        """
        INSERT INTO public.treatment_mixes (treatment_id, mix_code, notes, created_at)
        VALUES (:treatment_id, 'mix1', NULL, now())
        ON CONFLICT (treatment_id, mix_code) DO UPDATE
        SET notes = EXCLUDED.notes
        RETURNING id::uuid;
        """
    )

    upsert_tmc = text(
        """
        INSERT INTO public.treatment_mix_constructs (mix_id, construct_id, delivery_form, created_at)
        VALUES (:mix_id, :construct_id, :delivery_form, now())
        ON CONFLICT (mix_id, construct_id, delivery_form) DO NOTHING;
        """
    )

    upsert_treated = text(
        """
        INSERT INTO public.treated_clutches_v11 (clutch_id, treated_clutch_code, treatment_id, n_embryos, notes, created_by, created_at)
        VALUES (:clutch_id, :treated_clutch_code, :treatment_id, NULL, NULL, 'legacy_imaging', now())
        ON CONFLICT (treated_clutch_code) DO UPDATE
        SET clutch_id = EXCLUDED.clutch_id,
            treatment_id = EXCLUDED.treatment_id
        RETURNING id::uuid;
        """
    )

    upd_memberships = text(
        """
        UPDATE public.imaging_clutch_memberships m
        SET treated_clutch_id = :treated_clutch_id
        WHERE m.clutch_id = :clutch_id;
        """
    )

    batch = "legacy_treatments_from_raw_roi_v9"
    n_treatments = 0
    n_tmc = 0
    n_treated = 0
    n_memberships = 0

    with eng.begin() as cx:
        for lk in sorted(keys_with_any):
            rna, plasmid = by_key_final[lk]
            treat_code = treat_code_for(rna, plasmid)
            treat_text = treat_text_for(rna, plasmid)

            tid = cx.execute(
                upsert_treatment,
                {
                    "treat_code": treat_code,
                    "kind_code": "injection_mix",
                    "treat_text": treat_text,
                    "batch": batch,
                },
            ).scalar()
            if tid is None:
                raise SystemExit(f"[STOP] failed to upsert treatment treat_code={treat_code}")

            mix_id = cx.execute(ensure_mix, {"treatment_id": tid}).scalar()
            if mix_id is None:
                raise SystemExit(f"[STOP] failed to ensure treatment_mixes for treat_code={treat_code}")

            for bc in rna:
                cid = construct_id_by_base[bc]
                res = cx.execute(upsert_tmc, {"mix_id": mix_id, "construct_id": cid, "delivery_form": "rna"})
                n_tmc += int(res.rowcount or 0)

            for bc in plasmid:
                cid = construct_id_by_base[bc]
                res = cx.execute(upsert_tmc, {"mix_id": mix_id, "construct_id": cid, "delivery_form": "plasmid"})
                n_tmc += int(res.rowcount or 0)

            clutch_id, clutch_code = clutch_by_key[lk]
            treated_code = clutch_code.replace("LCL-", "TCL-", 1) if clutch_code.startswith("LCL-") else f"TCL-{clutch_code}"
            tclid = cx.execute(
                upsert_treated,
                {
                    "clutch_id": clutch_id,
                    "treated_clutch_code": treated_code,
                    "treatment_id": tid,
                },
            ).scalar()
            if tclid is None:
                raise SystemExit(f"[STOP] failed to upsert treated_clutches_v11 for clutch_code={clutch_code}")

            n_memberships += int(
                cx.execute(upd_memberships, {"treated_clutch_id": tclid, "clutch_id": clutch_id}).rowcount or 0
            )

            n_treatments += 1
            n_treated += 1

        qc = cx.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM public.treatments WHERE source_system='legacy_imaging') AS n_legacy_treatments,
                  (SELECT count(*) FROM public.treatment_mixes tm JOIN public.treatments t ON t.id=tm.treatment_id WHERE t.source_system='legacy_imaging') AS n_legacy_treatment_mixes,
                  (SELECT count(*) FROM public.treatment_mix_constructs tmc
                     JOIN public.treatment_mixes tm ON tm.id=tmc.mix_id
                     JOIN public.treatments t ON t.id=tm.treatment_id
                     WHERE t.source_system='legacy_imaging') AS n_legacy_tmc,
                  (SELECT count(*) FROM public.treated_clutches_v11 tc
                     JOIN public.treatments t ON t.id=tc.treatment_id
                     WHERE t.source_system='legacy_imaging') AS n_legacy_treated_clutches,
                  (SELECT count(*) FROM public.imaging_clutch_memberships WHERE treated_clutch_id IS NOT NULL) AS n_memberships_with_treated_clutch_id
                ;
                """
            )
        ).first()

    print(
        f"[OK] legacy treatments created={n_treatments} treated_clutches={n_treated} "
        f"tmc_inserts={n_tmc} memberships_updated={n_memberships}"
    )
    if qc is not None:
        print("[QC]", dict(qc._mapping))


if __name__ == "__main__":
    main()