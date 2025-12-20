#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import hashlib
from typing import Dict, List, Set, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set")
    print(f"DB_URL={url}")
    return create_engine(url)


_TOKEN_SPLIT = re.compile(r"[|,; ]+")
_TOKEN_RE = re.compile(r"^([A-Za-z]+)[-_]?(0*)(\d+)$")


def canon_one(tok: str) -> str | None:
    s = (tok or "").strip()
    if not s:
        return None
    m = _TOKEN_RE.match(s)
    if not m:
        return s.lower()
    prefix = m.group(1).lower()
    num = int(m.group(3))
    if prefix == "swin":
        prefix = "pswin"
    return f"{prefix}-{num}"


def canon_tokens(raw_codes: str) -> List[str]:
    parts = [p.strip() for p in _TOKEN_SPLIT.split(raw_codes or "") if p.strip()]
    out: List[str] = []
    for p in parts:
        c = canon_one(p)
        if c:
            out.append(c)
    out = sorted(dict.fromkeys(out))
    return out


def legacy_genotype_code(norm_basecodes_csv: str) -> str:
    h = hashlib.sha1(norm_basecodes_csv.encode("utf-8")).hexdigest()[:8]
    return f"LEGACY-{h}"


def main() -> None:
    eng = get_engine()

    with eng.begin() as cx:
        roi_df = pd.read_sql(
            text(
                """
                SELECT legacy_clutch_key, genotype_base_codes
                FROM raw.legacy_roi_enriched_v9
                WHERE COALESCE(btrim(legacy_clutch_key), '') <> ''
                """
            ),
            cx,
        )

        clutch_df = pd.read_sql(
            text(
                """
                SELECT id::uuid AS clutch_id, clutch_code, legacy_clutch_key
                FROM public.clutches
                WHERE source_system = 'legacy_imaging'
                  AND COALESCE(btrim(legacy_clutch_key), '') <> ''
                """
            ),
            cx,
        )

    if "genotype_base_codes" not in roi_df.columns:
        raise SystemExit("raw.legacy_roi_enriched_v9 is missing genotype_base_codes")

    clutch_by_key: Dict[str, Tuple[str, str]] = {}
    for r in clutch_df.itertuples(index=False):
        key = (r.legacy_clutch_key or "").strip()
        if not key:
            continue
        clutch_by_key[key] = (str(r.clutch_id), (r.clutch_code or "").strip())

    if not clutch_by_key:
        raise SystemExit("[STOP] no legacy_imaging clutches with legacy_clutch_key found in DB")

    by_key_tokens: Dict[str, Set[str]] = {}
    for r in roi_df.itertuples(index=False):
        key = (r.legacy_clutch_key or "").strip()
        if not key:
            continue
        raw_codes = (r.genotype_base_codes or "")
        raw_codes = "" if raw_codes is None else str(raw_codes).strip()
        if not raw_codes or raw_codes.lower() in ("nan", "none", "na", "n/a", "<na>"):
            continue
        toks = canon_tokens(raw_codes)
        if not toks:
            continue
        by_key_tokens.setdefault(key, set()).update(toks)

    print(f"[v11_seed_legacy_genotypes_from_enriched_roi] legacy_clutch_key with basecodes: {len(by_key_tokens)}")

    missing_keys = sorted(k for k in by_key_tokens.keys() if k not in clutch_by_key)
    if missing_keys:
        sample = "\n  - " + "\n  - ".join(missing_keys[:20])
        raise SystemExit(f"[STOP] {len(missing_keys)} ROI keys have basecodes but no matching clutches. Sample:{sample}")

    all_tokens: Set[str] = set()
    for toks in by_key_tokens.values():
        all_tokens.update(toks)
    all_tokens_list = sorted(all_tokens)

    with eng.begin() as cx:
        rows = cx.execute(
            text(
                """
                SELECT lower(base_code) AS base_code, id::uuid AS construct_id
                FROM public.constructs
                WHERE lower(base_code) = ANY(CAST(:toks AS text[]))
                """
            ),
            {"toks": all_tokens_list},
        ).fetchall()

    construct_id_by_base: Dict[str, str] = {str(bc): str(cid) for bc, cid in rows if bc and cid}
    missing_tokens = [t for t in all_tokens_list if t not in construct_id_by_base]
    if missing_tokens:
        sample = "\n  - " + "\n  - ".join(missing_tokens[:30])
        raise SystemExit(f"[STOP] {len(missing_tokens)} normalized basecodes not found in public.constructs.base_code. Sample:{sample}")

    upsert_geno = text(
        """
        INSERT INTO public.genotypes_v11 (
          genotype_code,
          genotype_basecodes,
          genotype_pretty,
          source_system,
          created_at
        )
        VALUES (
          :genotype_code,
          :genotype_basecodes,
          :genotype_pretty,
          'legacy_imaging',
          now()
        )
        ON CONFLICT (genotype_code) DO UPDATE
        SET genotype_basecodes = EXCLUDED.genotype_basecodes,
            genotype_pretty   = EXCLUDED.genotype_pretty
        RETURNING id::uuid;
        """
    )

    upsert_join = text(
        """
        INSERT INTO public.join_genotype_constructs_v11 (genotype_id, construct_id, created_at)
        VALUES (:genotype_id, :construct_id, now())
        ON CONFLICT DO NOTHING;
        """
    )

    update_clutch = text(
        """
        UPDATE public.clutches
        SET genotype_v11_id = :genotype_id
        WHERE id = :clutch_id
          AND source_system = 'legacy_imaging';
        """
    )

    touched_genotypes = 0
    clutch_updates = 0
    join_inserts = 0

    with eng.begin() as cx:
        for legacy_key in sorted(by_key_tokens.keys()):
            toks = sorted(by_key_tokens[legacy_key])
            norm_csv = ",".join(toks)
            pretty = "; ".join(toks)
            gcode = legacy_genotype_code(norm_csv)

            gid = cx.execute(
                upsert_geno,
                {
                    "genotype_code": gcode,
                    "genotype_basecodes": norm_csv,
                    "genotype_pretty": pretty,
                },
            ).scalar()

            if gid is None:
                raise SystemExit(f"[STOP] failed to upsert genotype for legacy_clutch_key={legacy_key}")

            touched_genotypes += 1

            for t in toks:
                cid = construct_id_by_base.get(t)
                if not cid:
                    raise SystemExit(f"[STOP] missing construct_id for token={t}")
                r = cx.execute(upsert_join, {"genotype_id": gid, "construct_id": cid})
                join_inserts += int(r.rowcount or 0)

            clutch_id, _clutch_code = clutch_by_key[legacy_key]
            r2 = cx.execute(update_clutch, {"genotype_id": gid, "clutch_id": clutch_id})
            clutch_updates += int(r2.rowcount or 0)

        qc = cx.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM public.clutches WHERE source_system='legacy_imaging') AS n_legacy_clutches,
                  (SELECT count(*) FROM public.clutches WHERE source_system='legacy_imaging' AND genotype_v11_id IS NOT NULL) AS n_legacy_with_genotype,
                  (SELECT count(*) FROM public.genotypes_v11 WHERE source_system='legacy_imaging') AS n_legacy_genotypes,
                  (SELECT count(*) FROM public.join_genotype_constructs_v11 j
                     JOIN public.genotypes_v11 g ON g.id=j.genotype_id
                     WHERE g.source_system='legacy_imaging') AS n_join_rows_for_legacy_genotypes,
                  (SELECT count(*) FROM public.genotypes_v11
                     WHERE source_system='legacy_imaging'
                       AND (genotype_pretty ILIKE '%||%' OR genotype_basecodes ILIKE '%||%')) AS n_bad_pipe_delims
                ;
                """
            )
        ).first()

    print(f"[OK] genotypes_touched={touched_genotypes} clutch_updates={clutch_updates} join_inserts={join_inserts}")
    if qc is not None:
        print("[QC]", dict(qc._mapping))


if __name__ == "__main__":
    main()
