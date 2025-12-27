from __future__ import annotations

import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Set

import pandas as pd
from sqlalchemy import create_engine, text


TOKEN_SPLIT = r"[|,; ]+"

def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s

def _split_list(raw: object) -> List[str]:
    s = _s(raw)
    if not s:
        return []
    parts = [p.strip() for p in pd.Series([s]).str.split(TOKEN_SPLIT, regex=True).iloc[0] if p.strip()]
    return parts

def _pairs_from_row(base_raw: object, allele_raw: object) -> Tuple[List[Tuple[str,str]], str]:
    bases = [ _s(x).lower().replace("pdqm", "pdqm-").replace("mgco", "mgco-").replace("hc", "hc-") for x in _split_list(base_raw) ]
    alleles = [ _s(x) for x in _split_list(allele_raw) ]

    bases = [b for b in bases if b]
    alleles = [a[:-2] if a.endswith(".0") and a[:-2].isdigit() else a for a in alleles]
    alleles = [a for a in alleles if a]

    if not bases or not alleles:
        return [], "blank"

    if len(bases) == 1 and len(alleles) >= 1:
        return [(bases[0], a) for a in alleles], "ok_single_base_multi_alleles"

    if len(bases) == len(alleles):
        return list(zip(bases, alleles)), "ok_positional"

    return [], f"mismatch n_basecodes={len(bases)} n_alleles={len(alleles)}"

def main() -> None:
    db_url = _s(os.environ.get("DB_URL"))
    if not db_url:
        raise SystemExit("[STOP] DB_URL must be set")

    csv_path = _s(os.environ.get("ROI_GENOTYPE_CSV")) or "seed_kits/legacy_wrangling_v4/working/legacy_imaging_annotations_for_db_v9_all_rois.csv"
    p = Path(csv_path)
    if not p.exists():
        raise SystemExit(f"[STOP] CSV not found: {p}")

    df = pd.read_csv(p, low_memory=False).fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    need = ["roi_dir", "genotype_base_codes", "genotype_allele_codes"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise SystemExit(f"[STOP] CSV missing columns: {miss}")

    df["roi_dir"] = df["roi_dir"].astype(str).str.strip()
    df["genotype_base_codes"] = df["genotype_base_codes"].astype(str).str.strip()
    df["genotype_allele_codes"] = df["genotype_allele_codes"].astype(str).str.strip()

    qc_dir = Path("seed_kits/legacy_wrangling_v4/working/qc_runs") / f"v11_apply_clutch_genotypes_from_roi_csv__{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    qc_dir.mkdir(parents=True, exist_ok=True)

    pair_rows: List[Tuple[str,str,str]] = []
    qc_reasons: Dict[str,int] = {}

    for r in df.itertuples(index=False):
        roi = _s(getattr(r, "roi_dir", ""))
        if not roi:
            continue
        pairs, reason = _pairs_from_row(getattr(r, "genotype_base_codes", ""), getattr(r, "genotype_allele_codes", ""))
        qc_reasons[reason] = qc_reasons.get(reason, 0) + 1
        for b,a in pairs:
            pair_rows.append((roi, b, a))

    if not pair_rows:
        (qc_dir / "qc_summary.txt").write_text("no usable (roi,base,allele_nickname) pairs\n", encoding="utf-8")
        print("[OK] no genotype pairs found in CSV")
        return

    pairs_df = pd.DataFrame(pair_rows, columns=["roi_path","transgene_base_code","allele_nickname"]).drop_duplicates()

    eng = create_engine(db_url)

    with eng.begin() as cx:
        db_map = cx.execute(text("""
            select
              ra.roi_path,
              m.clutch_id::uuid as clutch_id
            from public.imaging_roi_annotations ra
            join public.imaging_clutch_memberships m on m.slot_id = ra.slot_id
            where ra.roi_path = any(:paths)
        """), {"paths": pairs_df["roi_path"].tolist()}).fetchall()

        map_df = pd.DataFrame(db_map, columns=["roi_path","clutch_id"])
        map_df["roi_path"] = map_df["roi_path"].astype(str).str.strip()
        map_df["clutch_id"] = map_df["clutch_id"].astype(str).str.strip()

    merged = pairs_df.merge(map_df, left_on="roi_path", right_on="roi_path", how="inner")
    n_joined = len(merged)
    (qc_dir / "qc_pairs.csv").write_text(merged.head(5000).to_csv(index=False), encoding="utf-8")

    if n_joined == 0:
        (qc_dir / "qc_summary.txt").write_text("0 pairs joined to DB via roi_path\n", encoding="utf-8")
        raise SystemExit("[STOP] 0 genotype pairs joined to DB; roi_path mismatch")

    clutch_pairs: Dict[str, Set[Tuple[str,str]]] = {}
    for r in merged.itertuples(index=False):
        clutch_pairs.setdefault(r.clutch_id, set()).add((str(r.transgene_base_code), str(r.allele_nickname)))

    with eng.begin() as cx:
        ensured: Dict[Tuple[str,str], Tuple[int,str,str]] = {}
        for b,a in sorted({(b,a) for s in clutch_pairs.values() for (b,a) in s}):
            row = cx.execute(text("select (public.ensure_transgene_allele(:b,:a)).*"), {"b": b, "a": a}).fetchone()
            ensured[(b,a)] = (int(row[1]), str(row[2]), str(row[3]))

        upserted_genotypes = 0
        inserted_joins = 0
        updated_clutches = 0

        for clutch_id, pairs in clutch_pairs.items():
            sig_parts = []
            allele_rows = []
            for (b,a) in sorted(pairs):
                anum, aname, annick = ensured[(b,a)]
                allele_rows.append((b, anum))
                sig_parts.append(f"{b}:{anum}")

            sig = ";".join(sig_parts)
            gcode = "GT_ROI_" + hashlib.md5(sig.encode("utf-8")).hexdigest()[:12]

            gid = cx.execute(text("""
                select id::uuid from public.genotypes_v11 where genotype_code = :gcode
            """), {"gcode": gcode}).fetchone()
            if gid is None:
                cx.execute(text("""
                    insert into public.genotypes_v11 (id, genotype_code, genotype_pretty, genotype_basecodes, legacy_label, source_system, created_at)
                    values (gen_random_uuid(), :gcode, '', :basecodes, :label, 'legacy_imaging', now())
                """), {
                    "gcode": gcode,
                    "basecodes": "|".join(sorted({b for (b,_) in allele_rows})),
                    "label": sig,
                })
                upserted_genotypes += 1
                gid = cx.execute(text("select id::uuid from public.genotypes_v11 where genotype_code = :gcode"), {"gcode": gcode}).fetchone()

            genotype_id = str(gid[0])

            for (b, anum) in allele_rows:
                cx.execute(text("""
                    insert into public.join_genotype_transgene_alleles (genotype_v11_id, transgene_base_code, allele_number, zygosity, created_at)
                    values (cast(:gid as uuid), :b, :anum, '', now())
                    on conflict do nothing
                """), {"gid": genotype_id, "b": b, "anum": anum})
                inserted_joins += 1

            res = cx.execute(text("""
                update public.clutches
                set genotype_v11_id = cast(:gid as uuid)
                where id = cast(:cid as uuid)
                  and genotype_v11_id is null
            """), {"gid": genotype_id, "cid": clutch_id})
            updated_clutches += int(res.rowcount or 0)

    summary = []
    summary.append(f"csv={p}")
    summary.append(f"pairs_total={len(pairs_df)}")
    summary.append(f"pairs_joined_to_db={n_joined}")
    summary.append(f"distinct_clutches_touched={len(clutch_pairs)}")
    summary.append(f"genotypes_created={upserted_genotypes}")
    summary.append(f"join_rows_attempted={inserted_joins}")
    summary.append(f"clutches_updated={updated_clutches}")
    summary.append("reasons=" + ", ".join([f"{k}:{v}" for k,v in sorted(qc_reasons.items())]))

    (qc_dir / "qc_summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("[OK] wrote", qc_dir)

if __name__ == "__main__":
    main()
