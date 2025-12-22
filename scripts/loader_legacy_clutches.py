from __future__ import annotations

def _norm_bg(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("", "nan", "none", "na", "n/a", "<na>"):
        return ""
    return s

def _split_bg_list(s: str) -> list[str]:
    s = _norm_bg(s)
    if not s:
        return []
    parts = re.split(r"[;,/|]+", s)
    out = []
    for p in parts:
        v = _norm_bg(p)
        if v:
            out.append(v)
    return out

def _merge_parent_backgrounds(mom_bg: str, dad_bg: str) -> str:
    # Union of tokens from mom+dad, stable ordering:
    # - preserve first-seen order (mom then dad), dedupe case-insensitively
    seen = set()
    out = []
    for tok in _split_bg_list(mom_bg) + _split_bg_list(dad_bg):
        k = tok.casefold()
        if k in seen:
            continue
        seen.add(k)
        out.append(tok)
    return ", ".join(out)

def _row_get_first(row: dict, keys: list[str]) -> str:
    for k in keys:
        if k in row:
            v = _norm_bg(row.get(k))
            if v:
                return v
    return ""

import argparse
import os
import sys
import pathlib
import re
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd
from sqlalchemy import text, create_engine
from sqlalchemy.engine import Engine

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_BATCH_ID = "legacy_clutch_inference_2025-12-18"

PARENT_MAP_CSV_DEFAULT = (
    ROOT
    / "seed_kits"
    / "legacy_wrangling_v2"
    / "working"
    / "Unique_parent_names__mom_dad_combined__preview_dqm_from_raw.csv"
)

MEMBERSHIPS_CSV_DEFAULT = (
    ROOT
    / "seed_kits"
    / "legacy_wrangling_v3"
    / "working"
    / "legacy_clutch_memberships_v9.csv"
)

QC_OUT_DIR_DEFAULT = (
    ROOT
    / "seed_kits"
    / "legacy_wrangling_v3"
    / "working"
)

def _nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")

def _norm_label(s):
    if not _nonempty(s):
        return None
    s = str(s).strip().lower()
    s = re.sub(r"^\d{8}[_-]", "", s)
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("\\", "/")
    s = re.sub(r"[^a-z0-9]+", "", s)
    s = s.strip()
    return s or None

def _split_codes(v):
    if not _nonempty(v):
        return []
    s = str(v).strip()
    parts = re.split(r"[|,;]+", s)
    out = []
    for p in parts:
        p = p.strip()
        if p and p.lower() not in ("nan", "none", "na", "n/a", "<na>"):
            out.append(p)
    return out

def _uniq_join(parts):
    vals = []
    seen = set()
    for v in parts:
        if not _nonempty(v):
            continue
        for x in _split_codes(v):
            if x not in seen:
                seen.add(x)
                vals.append(x)
    return "|".join(vals) if vals else None

def _union_pipe(values: List[Optional[str]]) -> Optional[str]:
    return _uniq_join(values)

def _load_csv(path: pathlib.Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    df = pd.read_csv(path, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def _parent_lookup(parent_map_csv: pathlib.Path) -> dict:
    pm = pd.read_csv(parent_map_csv, low_memory=False).copy()
    pm.columns = [str(c).strip() for c in pm.columns]
    if "parent_name" in pm.columns and "parent_fish_name" not in pm.columns:
        pm = pm.rename(columns={"parent_name": "parent_fish_name"})
    need = {"parent_fish_name", "plasmid_base_code", "allele"}
    missing = sorted(list(need - set(pm.columns)))
    if missing:
        raise SystemExit(f"loader_legacy_clutches: parent map missing cols: {missing}")

    pm["parent_norm"] = pm["parent_fish_name"].apply(_norm_label)

    agg = (
        pm.groupby("parent_norm", dropna=True)
        .agg(
            {
                "plasmid_base_code": lambda s: _union_pipe([str(x) for x in s.tolist()]),
                "allele": lambda s: _union_pipe([str(x) for x in s.tolist()]),
            }
        )
        .reset_index()
    )
    return {r.parent_norm: (r.plasmid_base_code, r.allele) for r in agg.itertuples(index=False)}

def _prepare_payload(df: pd.DataFrame, batch: str) -> List[Dict[str, Any]]:
    required = {"clutch_code", "legacy_clutch_key", "date_born", "roi_count"}
    missing = sorted(list(required - set(df.columns)))
    if missing:
        raise ValueError(f"legacy_clutches.csv is missing required columns: {missing}")

    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        clutch_code = str(row["clutch_code"]).strip()
        if not clutch_code:
            continue

        legacy_clutch_key = row.get("legacy_clutch_key")
        legacy_clutch_key = str(legacy_clutch_key).strip() if _nonempty(legacy_clutch_key) else ""
        if not legacy_clutch_key:
            raise ValueError(f"legacy_clutches.csv has empty legacy_clutch_key for clutch_code={clutch_code!r}")

        date_born = row.get("date_born")
        clutch_date = str(date_born).strip() if _nonempty(date_born) else None

        roi_count = row.get("roi_count")
        try:
            egg_count = int(roi_count) if pd.notna(roi_count) else None
        except Exception:
            egg_count = None

        notes = f"legacy_imaging; roi_count={roi_count}"

        rows.append(
            {
                "clutch_code": clutch_code,
                "legacy_clutch_key": legacy_clutch_key,
                "clutch_date": clutch_date,
                "estimated_egg_count": egg_count,
                "notes": notes,
                "source_system": "legacy_imaging",
                "import_batch_id": batch,
            }
        )

    return rows


def _upsert_clutches(engine: Engine, rows: List[Dict[str, Any]], batch: str) -> None:
    if not rows:
        print("[WARN] loader_legacy_clutches: no rows to insert.")
        return

    insert_sql = text(
        """
        INSERT INTO public.clutches (
        clutch_code,
        legacy_clutch_key,
        clutch_date,
        estimated_egg_count,
        notes,
        source_system,
        import_batch_id,
        genetic_background
        )
        VALUES (
        :clutch_code,
        :legacy_clutch_key,
        :clutch_date,
        :estimated_egg_count,
        :notes,
        :source_system,
        :import_batch_id,
        :genetic_background
        )
        ON CONFLICT (legacy_clutch_key) WHERE (
        source_system = 'legacy_imaging'
        AND legacy_clutch_key IS NOT NULL
        AND btrim(legacy_clutch_key) <> ''
        )
        DO UPDATE SET
        clutch_code         = EXCLUDED.clutch_code,
        clutch_date         = EXCLUDED.clutch_date,
        estimated_egg_count = EXCLUDED.estimated_egg_count,
        notes               = EXCLUDED.notes,
        source_system       = EXCLUDED.source_system,
        import_batch_id     = EXCLUDED.import_batch_id,
        genetic_background  = EXCLUDED.genetic_background
        ;
        """
    )

    with engine.begin() as cx:
        for r in rows:
            mom_bg = _row_get_first(r, [
                'mom_genetic_background','mom_background','mom_bg','mom_bg_name','mom_bg_code',
                'mom_line_background','mom_fish_background','maternal_background'
            ])
            dad_bg = _row_get_first(r, [
                'dad_genetic_background','dad_background','dad_bg','dad_bg_name','dad_bg_code',
                'dad_line_background','dad_fish_background','paternal_background'
            ])
            gb = _merge_parent_backgrounds(mom_bg, dad_bg)
            r['genetic_background'] = gb if gb else None

        cx.execute(insert_sql, rows)

    print(f"[OK] Upserted {len(rows)} legacy clutch row(s) for batch='{batch}'.")



def _ensure_genotype(cx, genotype_basecodes: str, genotype_pretty: Optional[str] = None) -> str:
    bc = str(genotype_basecodes).strip()
    if not bc:
        raise ValueError("empty genotype_basecodes")

    pretty = str(genotype_pretty).strip() if _nonempty(genotype_pretty) else bc
    genotype_code = "G-" + bc.upper()

    sql_upsert = text(
        """
        INSERT INTO public.genotypes_v11 (
          genotype_code,
          genotype_basecodes,
          genotype_pretty,
          source_system,
          legacy_label,
          display_name
        )
        VALUES (
          :genotype_code,
          :genotype_basecodes,
          :genotype_pretty,
          'legacy_imaging',
          'legacy_infer',
          :display_name
        )
        ON CONFLICT (genotype_code) DO UPDATE
        SET genotype_basecodes = EXCLUDED.genotype_basecodes,
            genotype_pretty   = EXCLUDED.genotype_pretty,
            display_name      = EXCLUDED.display_name
        RETURNING id::uuid;
        """
    )

    sql_lookup_constructs = text(
        """
        SELECT id::uuid
        FROM public.constructs
        WHERE lower(base_code) = ANY(CAST(:toks AS text[]))
        ORDER BY lower(base_code);
        """
    )

    sql_join = text(
        """
        INSERT INTO public.join_genotype_constructs_v11 (genotype_id, construct_id, created_at)
        VALUES (:genotype_id, :construct_id, now())
        ON CONFLICT DO NOTHING;
        """
    )

    toks = [t.strip() for t in re.split(r"[|,; ]+", bc) if t.strip()]
    toks = [t.lower() for t in toks if t.lower() not in ("nan", "none", "na", "n/a", "<na>")]
    toks = sorted(dict.fromkeys(toks))

    gid = cx.execute(
        sql_upsert,
        {
            "genotype_code": genotype_code,
            "genotype_basecodes": bc,
            "genotype_pretty": pretty,
            "display_name": genotype_code,
        },
    ).scalar()

    if gid is None:
        raise SystemExit(f"[STOP] failed to upsert genotype_v11 for genotype_code={genotype_code}")

    if toks:
        rows = cx.execute(sql_lookup_constructs, {"toks": toks}).fetchall()
        found = [str(r[0]) for r in rows]
        if len(found) != len(toks):
            raise SystemExit(
                f"[STOP] construct lookup failed for genotype={genotype_code} basecodes={toks!r} "
                f"(found {len(found)} of {len(toks)})"
            )

        for (cid,) in rows:
            cx.execute(sql_join, {"genotype_id": gid, "construct_id": cid})

    return str(gid)

def _assign_clutch_genotypes_strict(
    engine: Engine,
    df_clutches: pd.DataFrame,
    batch: str,
    parent_map: dict,
) -> int:
    df = df_clutches.copy()

    if "genotype_basecodes" not in df.columns:
        raise SystemExit("[STOP] loader_legacy_clutches: missing required column genotype_basecodes in input CSV")

    if "genotype_alleles_display" not in df.columns:
        df["genotype_alleles_display"] = pd.NA

    df["clutch_code"] = df["clutch_code"].astype(str).str.strip()
    df["genotype_basecodes"] = df["genotype_basecodes"].astype(str).str.strip()
    df["genotype_alleles_display"] = df["genotype_alleles_display"].astype(str).str.strip()

    bad = df[df["genotype_basecodes"].apply(lambda x: not _nonempty(x))].copy()
    if len(bad):
        sample = bad[["clutch_code", "legacy_clutch_key"]].head(30).to_string(index=False)
        raise SystemExit(
            f"[STOP] loader_legacy_clutches: {len(bad)} clutch row(s) missing genotype_basecodes in input CSV.\n"
            f"Sample:\n{sample}"
        )

    sql_upd = text(
        """
        UPDATE public.clutches c
        SET genotype_v11_id = CAST(:gid AS uuid)
        WHERE c.clutch_code = :clutch_code
          AND c.source_system = 'legacy_imaging'
          AND c.import_batch_id = :batch;
        """
    )

    updated = 0

    for r in df.itertuples(index=False):
        clutch_code = str(r.clutch_code).strip()
        bc = str(r.genotype_basecodes).strip()

        pretty = None
        if hasattr(r, "genotype_alleles_display"):
            v = getattr(r, "genotype_alleles_display")
            if _nonempty(v):
                pretty = str(v).strip()

        with engine.begin() as cx:
            cx.execute(text("SET LOCAL lock_timeout = '5s';"))
            cx.execute(text("SET LOCAL statement_timeout = '60s';"))

            gid = _ensure_genotype(cx, bc, pretty)
            res = cx.execute(
                sql_upd,
                {"gid": gid, "clutch_code": clutch_code, "batch": batch},
            )
            updated += int(res.rowcount or 0)

    print(f"[OK] loader_legacy_clutches: set genotype_v11_id for {updated} clutch(es) in batch='{batch}'.")
    return updated
def _qc_report(engine: Engine, batch: str, out_dir: pathlib.Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"qc_missing_genotype_but_has_membership__{batch}.csv"

    sql = text(
        """
        WITH c AS (
          SELECT id, clutch_code, genotype_v11_id
          FROM public.clutches
          WHERE source_system='legacy_imaging'
            AND import_batch_id=:batch
        ),
        m AS (
          SELECT DISTINCT clutch_id
          FROM public.imaging_clutch_memberships
        )
        SELECT
          c.clutch_code,
          (c.genotype_v11_id IS NULL) AS missing_genotype,
          (m.clutch_id IS NOT NULL) AS has_membership
        FROM c
        LEFT JOIN m ON m.clutch_id = c.id
        ORDER BY c.clutch_code;
        """
    )

    with engine.begin() as cx:
        df = pd.read_sql(sql, cx, params={"batch": batch})

    n_clutches = int(len(df))
    n_missing = int(df["missing_genotype"].sum())
    n_missing_with_membership = int((df["missing_genotype"] & df["has_membership"]).sum())

    print(f"[QC] legacy clutches in batch={n_clutches} missing_genotype={n_missing} missing_genotype_but_has_membership={n_missing_with_membership}")

    bad = df[df["missing_genotype"] & df["has_membership"]].copy()
    if len(bad):
        bad.to_csv(out_csv, index=False)
        examples = ", ".join(bad["clutch_code"].head(30).tolist())
        print(f"[WARN] {len(bad)} legacy clutches have imaging memberships but NULL genotype_v11_id. QC report: {out_csv}")
        print(f"[WARN] examples: {examples}")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load inferred legacy clutches into public.clutches (STRICT)."
    )
    parser.add_argument("--csv", required=True, help="Path to legacy_clutches_v9_for_loader.csv")
    parser.add_argument(
        "--memberships-csv",
        default=str(MEMBERSHIPS_CSV_DEFAULT),
        help="Path to legacy_clutch_memberships_v9.csv",
    )
    parser.add_argument(
        "--qc-out-dir",
        default=str(QC_OUT_DIR_DEFAULT),
        help="Where to write QC reports",
    )
    parser.add_argument("--batch", default=DEFAULT_BATCH_ID, help="import_batch_id label")
    args = parser.parse_args()

    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL environment variable is not set.")
    print(f"DB_URL(loader_legacy_clutches)={db_url}")
    engine = create_engine(db_url)

    df_clutches = _load_csv(pathlib.Path(args.csv))
    df_members = _load_csv(pathlib.Path(args.memberships_csv))

    if "clutch_code" not in df_clutches.columns:
        raise SystemExit("[STOP] legacy clutches CSV missing clutch_code")
    if "clutch_code" not in df_members.columns:
        raise SystemExit("[STOP] legacy_clutch_memberships CSV missing clutch_code")

    clutch_codes_in_members = set(df_members["clutch_code"].astype(str).str.strip().tolist())
    df_clutches["clutch_code"] = df_clutches["clutch_code"].astype(str).str.strip()
    df_clutches = df_clutches[df_clutches["clutch_code"].isin(clutch_codes_in_members)].copy()

    if df_clutches.empty:
        raise SystemExit("[STOP] No clutches matched memberships CSV (strict).")

    rows = _prepare_payload(df_clutches, args.batch)
    _upsert_clutches(engine, rows, args.batch)

    _assign_clutch_genotypes_strict(engine, df_clutches, args.batch, parent_map={})

    _qc_report(engine, args.batch, pathlib.Path(args.qc_out_dir))

if __name__ == "__main__":
    main()
