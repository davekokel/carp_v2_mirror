from __future__ import annotations

import os
import re
import hashlib
from pathlib import Path
from typing import Dict, Tuple, Optional, List

import pandas as pd
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[3]
WORK = REPO_ROOT / "seed_kits" / "legacy_wrangling_v3" / "working"

IN_CLUTCHES = WORK / "legacy_clutches_v9.csv"

def _nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")

def _norm_label(s) -> Optional[str]:
    if not _nonempty(s):
        return None
    s = str(s).strip().lower()
    s = re.sub(r"^\d{8}[_-]", "", s)
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("\\", "/")
    s = re.sub(r"[^a-z0-9]+", "", s)
    s = s.strip()
    return s or None

def _uniq_pipe(vals: List[str]) -> Optional[str]:
    out = []
    seen = set()
    for v in vals:
        if not _nonempty(v):
            continue
        for part in re.split(r"[|,;]+", str(v)):
            part = str(part).strip()
            if not part or part.lower() in ("nan","none","na","n/a","<na>"):
                continue
            if part not in seen:
                seen.add(part)
                out.append(part)
    return "|".join(out) if out else None

def _sha10(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]

def main() -> None:
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL not set")

    if not IN_CLUTCHES.exists():
        raise SystemExit(f"missing: {IN_CLUTCHES}")

    df = pd.read_csv(IN_CLUTCHES, low_memory=False)
    need_cols = ["clutch_code", "legacy_clutch_key", "parent_female_genotype_text", "parent_male_genotype_text"]
    missing = [c for c in need_cols if c not in df.columns]
    if missing:
        raise SystemExit(f"IN_CLUTCHES missing required cols: {missing}")

    engine = create_engine(db_url)

    with engine.begin() as con:
        parents = pd.read_sql(
            text("""
                SELECT parent_fish_name, plasmid_base_code, allele
                FROM raw.legacy_parent_definitions_v9
            """),
            con,
        )

        clutches_db = pd.read_sql(
            text("""
                SELECT id::text AS clutch_id, clutch_code
                FROM public.clutches
                WHERE source_system = 'legacy_imaging'
            """),
            con,
        )

    if parents.empty:
        raise SystemExit("raw.legacy_parent_definitions_v9 is empty")

    if clutches_db.empty:
        raise SystemExit("No clutches found with source_system='legacy_imaging'")

    parents = parents.copy()
    parents["parent_norm"] = parents["parent_fish_name"].apply(_norm_label)

    parent_map: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    for key, grp in parents.groupby("parent_norm", dropna=True):
        base = _uniq_pipe(grp["plasmid_base_code"].dropna().astype(str).tolist())
        alle = _uniq_pipe(grp["allele"].dropna().astype(str).tolist())
        if _nonempty(key):
            parent_map[str(key)] = (base, alle)

    df = df.copy()
    df["female_norm"] = df["parent_female_genotype_text"].apply(_norm_label)
    df["male_norm"] = df["parent_male_genotype_text"].apply(_norm_label)

    def lookup(norm: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        if not _nonempty(norm):
            return (None, None)
        return parent_map.get(str(norm), (None, None))

    f_base, f_alle = zip(*df["female_norm"].apply(lookup))
    m_base, m_alle = zip(*df["male_norm"].apply(lookup))

    df["geno_basecodes"] = [_uniq_pipe([a, b]) for a, b in zip(f_base, m_base)]
    df["geno_alleles"] = [_uniq_pipe([a, b]) for a, b in zip(f_alle, m_alle)]

    df["legacy_label"] = (
        df["parent_female_genotype_text"].astype(str).fillna("").str.strip()
        + " x "
        + df["parent_male_genotype_text"].astype(str).fillna("").str.strip()
    )
    df.loc[~df["legacy_label"].map(_nonempty), "legacy_label"] = pd.NA

    def geno_key_row(r) -> Optional[str]:
        b = r.get("geno_basecodes")
        a = r.get("geno_alleles")
        if not _nonempty(b) and not _nonempty(a):
            return None
        return f"base={b or ''};alle={a or ''}"

    df["geno_key"] = df.apply(geno_key_row, axis=1)
    df["genotype_code"] = df["geno_key"].apply(lambda k: (f"LEG-{_sha10(k)}" if _nonempty(k) else None))
    df["genotype_pretty"] = df["legacy_label"]

    missing_parent_hits = int(((df["female_norm"].map(_nonempty) & df["female_norm"].map(lambda x: x not in parent_map)) |
                               (df["male_norm"].map(_nonempty) & df["male_norm"].map(lambda x: x not in parent_map))).sum())

    clutches_db = clutches_db.copy()
    key2id = {r.clutch_code: r.clutch_id for r in clutches_db.itertuples(index=False)}

    df["clutch_id"] = df["clutch_code"].astype(str).map(key2id)
    n_missing_clutch_id = int(df["clutch_id"].isna().sum())

    geno_rows = (
        df[["genotype_code", "genotype_pretty", "geno_basecodes", "legacy_label", "geno_key"]]
        .dropna(subset=["genotype_code", "geno_key"])
        .drop_duplicates(subset=["genotype_code"])
        .copy()
    )

    with engine.begin() as con:
        existing = pd.read_sql(
            text("""
                SELECT genotype_code
                FROM public.genotypes_v11
                WHERE source_system = 'legacy_imaging'
            """),
            con,
        )
        existing_set = set(existing["genotype_code"].astype(str).tolist()) if not existing.empty else set()

        to_insert = geno_rows[~geno_rows["genotype_code"].astype(str).isin(existing_set)].copy()

        if not to_insert.empty:
            con.execute(
                text("""
                    INSERT INTO public.genotypes_v11
                        (id, genotype_code, genotype_pretty, genotype_basecodes, legacy_label, source_system, created_at)
                    VALUES
                        (gen_random_uuid(), :genotype_code, :genotype_pretty, :genotype_basecodes, :legacy_label, 'legacy_imaging', now())
                """),
                [
                    {
                        "genotype_code": r.genotype_code,
                        "genotype_pretty": (r.genotype_pretty if _nonempty(r.genotype_pretty) else r.legacy_label),
                        "genotype_basecodes": r.geno_basecodes,
                        "legacy_label": r.legacy_label,
                    }
                    for r in to_insert.itertuples(index=False)
                ],
            )

        gmap = pd.read_sql(
            text("""
                SELECT id::text AS genotype_id, genotype_code
                FROM public.genotypes_v11
                WHERE source_system = 'legacy_imaging'
            """),
            con,
        )
        code2gid = {r.genotype_code: r.genotype_id for r in gmap.itertuples(index=False)}

        upd = df.dropna(subset=["clutch_id", "genotype_code"]).copy()
        upd["genotype_id"] = upd["genotype_code"].astype(str).map(code2gid)
        upd = upd.dropna(subset=["genotype_id"]).copy()

        con.execute(
            text("""
                UPDATE public.clutches
                SET genotype_v11_id = CAST(:gid AS uuid)
                WHERE id = CAST(:cid AS uuid)
            """),
            [{"gid": r.genotype_id, "cid": r.clutch_id} for r in upd.itertuples(index=False)],
        )

    print("IN_CLUTCHES", IN_CLUTCHES)
    print("ROWS", len(df))
    print("LEGACY_CLUTCHES_IN_DB", len(clutches_db))
    print("MISSING_CLUTCH_ID_IN_DB", n_missing_clutch_id)
    print("PARENT_TEXT_WITH_NO_PARENT_MAP_HIT", missing_parent_hits)
    print("GENOTYPE_ROWS_DISTINCT", int(geno_rows.shape[0]))
    print("GENOTYPES_INSERTED", int(to_insert.shape[0]) if 'to_insert' in locals() else 0)
    print("CLUTCHES_UPDATED", int(upd.shape[0]) if 'upd' in locals() else 0)

if __name__ == "__main__":
    main()
