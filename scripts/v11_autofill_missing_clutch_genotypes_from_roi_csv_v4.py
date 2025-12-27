from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any

import pandas as pd
from sqlalchemy import create_engine, text


def _s(x: object) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s


def _canon_basecode(x: str) -> str:
    s = _s(x).lower()
    if not s:
        return ""
    if s.startswith("pdqm") and s[4:].isdigit():
        return f"pdqm-{int(s[4:])}"
    if s.startswith("mgco") and s[4:].lstrip("-").isdigit():
        return f"mgco-{int(s.replace('mgco','').replace('-',''))}"
    if s.startswith("hc") and s[2:].lstrip("-").isdigit():
        return f"hc-{int(s.replace('hc','').replace('-',''))}"
    return s


def _split_codes_keep_order(raw: str) -> List[str]:
    s = _s(raw)
    if not s:
        return []
    parts: List[str] = []
    buf = ""
    for ch in s:
        if ch in ["|", ",", ";", " "]:
            if buf.strip():
                parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())
    out: List[str] = []
    for p in parts:
        b = _canon_basecode(p)
        if b:
            out.append(b)
    return out


def _split_alleles_keep_order(raw: str) -> List[str]:
    s = _s(raw)
    if not s:
        return []
    parts: List[str] = []
    buf = ""
    for ch in s:
        if ch in ["|", ",", ";", " "]:
            if buf.strip():
                parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())

    out: List[str] = []
    for p in parts:
        x = _s(p)
        if not x:
            continue
        if x.endswith(".0") and x[:-2].isdigit():
            x = x[:-2]
        out.append(x)
    return out


def _pair_basecodes_and_alleles(basecodes: List[str], alleles: List[str]) -> Tuple[List[Tuple[str, str]], str]:
    if not basecodes and not alleles:
        return ([], "empty")
    if not basecodes or not alleles:
        return ([], "missing_one_side")
    if len(basecodes) == 1 and len(alleles) >= 1:
        return ([(basecodes[0], a) for a in alleles if _s(a)], "single_base_multi_allele")
    if len(basecodes) == len(alleles):
        return (list(zip(basecodes, alleles)), "positional")
    return ([], f"count_mismatch n_base={len(basecodes)} n_allele={len(alleles)}")


def main() -> None:
    db_url = _s(os.environ.get("DB_URL"))
    if not db_url:
        raise SystemExit("[STOP] DB_URL must be set")

    roi_csv = _s(os.environ.get("ROI_DB_CSV")) or "seed_kits/legacy_wrangling_v4/working/legacy_imaging_annotations_for_db_v9.csv"
    roi_csv_p = Path(roi_csv)
    if not roi_csv_p.exists():
        raise SystemExit(f"[STOP] ROI_DB_CSV not found: {roi_csv_p}")

    work = Path("seed_kits/legacy_wrangling_v4/working")
    qc_dir = work / "qc_runs" / f"v11_autofill_missing_clutch_genotypes__{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    qc_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(roi_csv_p, low_memory=False).fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    need_cols = ["roi_dir", "genotype_base_codes", "genotype_allele_codes"]
    miss = [c for c in need_cols if c not in df.columns]
    if miss:
        raise SystemExit(f"[STOP] ROI CSV missing required columns: {miss}")

    df["roi_dir"] = df["roi_dir"].astype(str).str.strip()
    df["genotype_base_codes"] = df["genotype_base_codes"].astype(str).str.strip()
    df["genotype_allele_codes"] = df["genotype_allele_codes"].astype(str).str.strip()

    eng = create_engine(db_url)

    # DB: roi_path -> clutch (only clutches currently missing genotype_v11_id)
    with eng.begin() as cx:
        rows = cx.execute(
            text(
                """
                select
                  c.id::uuid as clutch_id,
                  c.clutch_code,
                  ra.roi_path
                from public.clutches c
                join public.imaging_clutch_memberships m on m.clutch_id = c.id
                join public.imaging_roi_annotations ra on ra.slot_id = m.slot_id
                where c.genotype_v11_id is null
                  and coalesce(btrim(c.clutch_code),'') <> ''
                  and coalesce(btrim(ra.roi_path),'') <> ''
                """
            )
        ).fetchall()

    map_df = pd.DataFrame(rows, columns=["clutch_id", "clutch_code", "roi_path"])
    if map_df.empty:
        (qc_dir / "qc_summary.txt").write_text("no clutches missing genotype_v11_id (nothing to do)\n", encoding="utf-8")
        print("[OK] nothing to do:", qc_dir)
        return

    map_df["roi_path"] = map_df["roi_path"].astype(str).str.strip()
    merged = map_df.merge(df, left_on="roi_path", right_on="roi_dir", how="left", validate="m:1")

    # Per clutch: require consistent nonblank genotype_base_codes / genotype_allele_codes across its ROIs
    qc_rows: List[Dict[str, Any]] = []
    clutch_payloads: List[Dict[str, Any]] = []

    grp = merged.groupby(["clutch_id", "clutch_code"], dropna=False)
    for (clutch_id, clutch_code), g in grp:
        gb = sorted({ _s(x) for x in g["genotype_base_codes"].tolist() if _s(x) })
        ga = sorted({ _s(x) for x in g["genotype_allele_codes"].tolist() if _s(x) })

        if not gb or not ga:
            qc_rows.append(
                {
                    "clutch_code": clutch_code,
                    "clutch_id": str(clutch_id),
                    "reason": "missing_genotype_evidence_in_roi_csv",
                    "n_rois": int(len(g)),
                    "sample_roi_path": _s(g["roi_path"].iloc[0]) if len(g) else "",
                }
            )
            continue

        if len(gb) != 1 or len(ga) != 1:
            qc_rows.append(
                {
                    "clutch_code": clutch_code,
                    "clutch_id": str(clutch_id),
                    "reason": "inconsistent_genotype_evidence_across_rois",
                    "gb_distinct": "|".join(gb),
                    "ga_distinct": "|".join(ga),
                    "n_rois": int(len(g)),
                    "sample_roi_path": _s(g["roi_path"].iloc[0]) if len(g) else "",
                }
            )
            continue

        clutch_payloads.append(
            {
                "clutch_id": str(clutch_id),
                "clutch_code": clutch_code,
                "genotype_base_codes": gb[0],
                "genotype_allele_codes": ga[0],
                "n_rois": int(len(g)),
            }
        )

    pd.DataFrame(qc_rows).to_csv(qc_dir / "qc_skipped_clutches.csv", index=False)

    ensured_genotypes = 0
    inserted_joins = 0
    updated_clutches = 0

    with eng.begin() as cx:
        for rec in clutch_payloads:
            clutch_id = rec["clutch_id"]
            clutch_code = rec["clutch_code"]
            bases = _split_codes_keep_order(rec["genotype_base_codes"])
            alleles = _split_alleles_keep_order(rec["genotype_allele_codes"])

            pairs, mode = _pair_basecodes_and_alleles(bases, alleles)
            if not pairs:
                qc_rows.append(
                    {
                        "clutch_code": clutch_code,
                        "clutch_id": clutch_id,
                        "reason": f"pairing_failed:{mode}",
                        "genotype_base_codes": rec["genotype_base_codes"],
                        "genotype_allele_codes": rec["genotype_allele_codes"],
                    }
                )
                continue

            resolved: List[Tuple[str, int]] = []
            for base, nick in pairs:
                base = _canon_basecode(base)
                nick = _s(nick)
                if not base or not nick:
                    continue
                row = cx.execute(
                    text("select transgene_base_code, allele_number from public.ensure_transgene_allele(:b,:n)"),
                    {"b": base, "n": nick},
                ).fetchone()
                if row is None:
                    qc_rows.append(
                        {
                            "clutch_code": clutch_code,
                            "clutch_id": clutch_id,
                            "reason": "ensure_transgene_allele_returned_null",
                            "base": base,
                            "allele_nickname": nick,
                        }
                    )
                    resolved = []
                    break
                resolved.append((str(row[0]), int(row[1])))

            if not resolved:
                continue

            basecodes_str = "|".join(sorted({b for (b, _) in resolved}))

            # Genotype identity is the allele-set (genotype_basecodes), which is UNIQUE in genotypes_v11.
            # Therefore: reuse an existing genotype row when the basecodes match, otherwise create one.
            gid = cx.execute(
                text("select id::uuid from public.genotypes_v11 where genotype_basecodes = :basecodes limit 1"),
                {"basecodes": basecodes_str},
            ).scalar()

            if gid is None:
                import hashlib
                h = hashlib.md5(basecodes_str.encode("utf-8")).hexdigest()[:12]
                genotype_code = f"GT_LEGACY_GB_{h}"

                cx.execute(
                    text(
                        """
                        insert into public.genotypes_v11 (
                          id, genotype_code, genotype_basecodes, legacy_label, source_system, created_at, nickname, display_name
                        )
                        values (
                          gen_random_uuid(), :code, :basecodes, :legacy_label, 'legacy_imaging', now(), :nickname, :display_name
                        )
                        on conflict (genotype_basecodes) do nothing
                        """
                    ),
                    {
                        "code": genotype_code,
                        "basecodes": basecodes_str,
                        "legacy_label": basecodes_str,
                        "nickname": basecodes_str,
                        "display_name": basecodes_str,
                    },
                )

                gid = cx.execute(
                    text("select id::uuid from public.genotypes_v11 where genotype_basecodes = :basecodes limit 1"),
                    {"basecodes": basecodes_str},
                ).scalar()

                if gid is None:
                    raise SystemExit("[STOP] internal: failed to resolve genotype_v11_id after upsert-by-basecodes")

                ensured_genotypes += 1
            if gid is None:
                raise SystemExit("[STOP] internal: failed to resolve genotype_v11_id after upsert")

            # join rows (v11): genotypes_v11 ↔ constructs via join_genotype_constructs_v11
            # We only have (genotype_id, construct_id) available here.
            basecodes = sorted({b for (b, _) in resolved})
            if not basecodes:
                qc_reasons["no_resolved_basecodes"] += 1
                continue

            # Resolve construct_id for each basecode by probing known tables.
            # This keeps the script durable across schema variations.
            def _resolve_construct_ids(cx, bases):
                # Find construct_id by basecode using schema introspection (durable).
                # We look for a text column that plausibly holds a basecode and probe it.
                candidates = [
                    "public.constructs",
                    "public.constructs_v11",
                    "public.constructs_plasmid",
                    "public.transgenes",
                ]

                preferred_cols = [
                    "plasmid_code",
                    "plasmid_base_code",
                    "construct_code",
                    "construct_base_code",
                    "transgene_base_code",
                    "base_code",
                    "code",
                ]

                bases_lc = [b.lower() for b in bases]

                def _table_exists(t: str) -> bool:
                    return bool(cx.execute(text("select to_regclass(:t) is not null"), {"t": t}).scalar())

                def _cols_for_table(t: str) -> list[str]:
                    schema, name = t.split(".", 1)
                    rows = cx.execute(
                        text(
                            """
                            select lower(column_name)
                            from information_schema.columns
                            where table_schema = :schema
                              and table_name = :name
                              and data_type in ('text','character varying','character')
                            order by ordinal_position
                            """
                        ),
                        {"schema": schema, "name": name},
                    ).fetchall()
                    return [str(r[0]) for r in rows]

                for table in candidates:
                    if not _table_exists(table):
                        continue

                    cols = _cols_for_table(table)
                    if not cols:
                        continue

                    col = None
                    for c in preferred_cols:
                        if c in cols:
                            col = c
                            break
                    if col is None:
                        # last resort: any column containing 'code'
                        for c in cols:
                            if "code" in c:
                                col = c
                                break
                    if col is None:
                        continue

                    rows = cx.execute(
                        text(
                            f"""
                            select id::uuid as construct_id, lower(btrim({col})) as base
                            from {table}
                            where lower(btrim({col})) = any(:bases)
                            """
                        ),
                        {"bases": bases_lc},
                    ).fetchall()

                    m = {str(base).strip(): str(cid) for (cid, base) in rows if cid and base}
                    if m:
                        return m, f"{table}.{col}"

                return {}, ""
            construct_id_by_base, src = _resolve_construct_ids(cx, basecodes)

            missing_bases = [b for b in basecodes if b.lower() not in construct_id_by_base]
            if missing_bases:
                qc_rows.append(
                    {
                        "clutch_id": clutch_id,
                        "clutch_code": clutch_code,
                        "reason": "missing_construct_id_for_basecode",
                        "details": f"bases={missing_bases} (lookup_source={src or 'NONE'})",
                    }
                )
                qc_reasons["missing_construct_id_for_basecode"] += 1
                continue

            for base in basecodes:
                cid = construct_id_by_base[base.lower()]
                res = cx.execute(
                    text(
                        """
                        insert into public.join_genotype_constructs_v11 (genotype_id, construct_id, created_at)
                        select cast(:gid as uuid), cast(:cid as uuid), now()
                        where not exists (
                          select 1
                          from public.join_genotype_constructs_v11 j
                          where j.genotype_id = cast(:gid as uuid)
                            and j.construct_id = cast(:cid as uuid)
                        )
                        """
                    ),
                    {"gid": str(gid), "cid": str(cid)},
                )
                inserted_joins += int(res.rowcount or 0)

            # attach to clutch (only if still null)
            res = cx.execute(
                text(
                    """
                    update public.clutches
                    set genotype_v11_id = cast(:gid as uuid)
                    where id = cast(:cid as uuid)
                      and genotype_v11_id is null
                    """
                ),
                {"gid": str(gid), "cid": clutch_id},
            )
            updated_clutches += int(res.rowcount or 0)

    pd.DataFrame(qc_rows).to_csv(qc_dir / "qc_skipped_clutches_postpair.csv", index=False)

    summary = [
        f"roi_csv={roi_csv_p}",
        f"db_missing_genotype_clutches_seen={map_df['clutch_id'].nunique()}",
        f"candidate_clutches_with_csv_evidence={len(clutch_payloads)}",
        f"genotypes_upserted={ensured_genotypes}",
        f"join_rows_inserted={inserted_joins}",
        f"clutches_updated={updated_clutches}",
        f"qc_dir={qc_dir}",
    ]
    (qc_dir / "qc_summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("[OK] wrote", qc_dir)
    print("\n".join(summary))


if __name__ == "__main__":
    main()
