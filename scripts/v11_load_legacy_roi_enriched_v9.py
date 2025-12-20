#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tomllib


def get_engine(db_url: str | None) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set (env DB_URL or --db-url)")
    print(f"DB_URL={url}")
    return create_engine(url)


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Config not found: {path}")
    with path.open("rb") as f:
        return tomllib.load(f)


def _split_schema_table(qualified: str) -> Tuple[str, str]:
    s = qualified.strip()
    if "." not in s:
        raise SystemExit(f"Expected schema.table, got: {qualified!r}")
    schema, table = s.split(".", 1)
    schema = schema.strip()
    table = table.strip()
    if not schema or not table:
        raise SystemExit(f"Bad schema.table: {qualified!r}")
    return schema, table


def _resolve_csv(repo_root: Path, working_dir: str, rel: str) -> Path:
    p = Path(rel)
    if p.is_absolute():
        return p
    if "/" in rel or "\\" in rel:
        return (repo_root / p).resolve()
    return (repo_root / working_dir / rel).resolve()


def _nonempty(x: Any) -> bool:
    if x is None:
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Load enriched legacy ROI annotations into raw.legacy_roi_enriched_v9 (STRICT: join enriched+compat on roi_dir)."
    )
    ap.add_argument("--config", default="carp_app/pipelines/legacy_imaging_config.toml")
    ap.add_argument("--db-url", help="Override DB_URL")
    args = ap.parse_args()

    cfg_path = (REPO_ROOT / args.config).resolve()
    cfg = load_config(cfg_path)

    working_dir = cfg["paths"]["working_dir"]
    table_qualified = cfg["roi_annotations"]["table"]
    schema, table = _split_schema_table(table_qualified)

    enriched_csv = _resolve_csv(REPO_ROOT, working_dir, cfg["roi_annotations"]["csv"])
    compat_csv = _resolve_csv(REPO_ROOT, working_dir, cfg["roi_annotations"]["compat_csv"])

    if not enriched_csv.exists():
        raise SystemExit(f"CSV not found: {enriched_csv}")
    if not compat_csv.exists():
        raise SystemExit(f"CSV not found: {compat_csv}")

    df_en = pd.read_csv(enriched_csv, low_memory=False)
    df_co = pd.read_csv(compat_csv, low_memory=False)

    if "roi_dir" not in df_en.columns:
        raise SystemExit(f"{enriched_csv} missing required column roi_dir")
    if "roi_dir" not in df_co.columns:
        raise SystemExit(f"{compat_csv} missing required column roi_dir")
    if "legacy_clutch_key" not in df_co.columns:
        raise SystemExit(f"{compat_csv} missing required column legacy_clutch_key")

    df_en["roi_dir"] = df_en["roi_dir"].astype(str).str.strip()
    df_co["roi_dir"] = df_co["roi_dir"].astype(str).str.strip()

    # STRICT 1:1 keys
    dupe_en = df_en["roi_dir"].value_counts()
    dupe_en = dupe_en[dupe_en > 1]
    if len(dupe_en):
        raise SystemExit(f"[STOP] enriched CSV has duplicate roi_dir (expected unique): {len(dupe_en)}")

    dupe_co = df_co["roi_dir"].value_counts()
    dupe_co = dupe_co[dupe_co > 1]
    if len(dupe_co):
        raise SystemExit(f"[STOP] compat CSV has duplicate roi_dir (expected unique): {len(dupe_co)}")

    keep_co = [
        c for c in [
            "roi_dir",
            "legacy_clutch_key",
            "plate_date",
            "plate_id_filled",
            "slot_id_filled",
            "roi_index_within_slot",
            "bruker_roi_id",
            "treatment_rna_rna_base_code",
            "treatment_plasmid_plasmid_base_code",
        ]
        if c in df_co.columns
    ]
    df_co = df_co[keep_co].copy()

    df = df_en.merge(df_co, on="roi_dir", how="left", validate="one_to_one")

    missing_key = df["legacy_clutch_key"].isna() | (df["legacy_clutch_key"].astype(str).str.strip() == "")
    if int(missing_key.sum()) > 0:
        ex = df.loc[missing_key, ["roi_dir"]].head(20)
        raise SystemExit(f"[STOP] {int(missing_key.sum())} ROI rows missing legacy_clutch_key after join. Examples:\n{ex.to_string(index=False)}")

    eng = get_engine(args.db_url)

    with eng.begin() as cx:
        rows = cx.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name   = :table
                ORDER BY ordinal_position
            """),
            {"schema": schema, "table": table},
        ).fetchall()
    db_cols = [r[0] for r in rows]
    db_set = set(db_cols)

    out_cols = [c for c in df.columns if c in db_set]
    if not out_cols:
        raise SystemExit("[STOP] no overlapping columns between merged CSV and DB table")

    df_out = df[out_cols].copy()

    print(f"[INFO] importing {len(df_out)} rows into {schema}.{table}")
    print(f"[INFO] sources: enriched={enriched_csv.name} compat={compat_csv.name}")
    print(f"[INFO] columns ({len(out_cols)}):")
    for c in out_cols:
        print("  -", c)

    with eng.begin() as cx:
        cx.execute(text(f"TRUNCATE {schema}.{table}"))
        df_out.to_sql(
            table,
            cx,
            schema=schema,
            if_exists="append",
            index=False,
        )

    qc = {}
    qc["n_rows"] = int(len(df_out))
    qc["n_distinct_roi_dir"] = int(df_out["roi_dir"].nunique()) if "roi_dir" in df_out.columns else None
    qc["n_distinct_legacy_clutch_key"] = int(df_out["legacy_clutch_key"].nunique()) if "legacy_clutch_key" in df_out.columns else None
    if "genotype_base_codes" in df_out.columns:
        qc["n_rows_with_genotype_base_codes"] = int(df_out["genotype_base_codes"].astype(str).map(_nonempty).sum())
    elif "genotype_base_codes_v9_exp" in df_out.columns:
        qc["n_rows_with_genotype_base_codes_v9_exp"] = int(df_out["genotype_base_codes_v9_exp"].astype(str).map(_nonempty).sum())

    print("[QC]", qc)
    print(f"[OK] loaded {len(df_out)} row(s) into {schema}.{table}")


if __name__ == "__main__":
    main()
