#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tomllib

from carp_app.pipelines.construct_tokens import canonicalize_tokens, resolve_construct_ids, TokenError


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


def _resolve_csv_path(repo_root: Path, cfg: Dict[str, Any]) -> Path:
    rel = cfg["parent_definitions"]["csv"]
    p = Path(rel)
    if p.is_absolute():
        return p
    if "/" in rel or "\\" in rel:
        return (repo_root / p).resolve()
    working = Path(cfg["paths"]["working_dir"])
    return (repo_root / working / rel).resolve()


def _split_schema_table(qualified: str) -> tuple[str, str]:
    s = qualified.strip()
    if "." not in s:
        raise SystemExit(f"Expected schema.table, got: {qualified!r}")
    schema, table = s.split(".", 1)
    schema = schema.strip()
    table = table.strip()
    if not schema or not table:
        raise SystemExit(f"Bad schema.table: {qualified!r}")
    return schema, table


def _canonicalize_field(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return None
    toks = canonicalize_tokens(s)
    return "|".join(toks) if toks else None


def _all_tokens_from_row(row: Dict[str, Any]) -> List[str]:
    toks: List[str] = []
    for k in ("plasmid_base_code", "injected_rna", "injected_plasmid"):
        v = row.get(k)
        if v:
            toks.extend(canonicalize_tokens(v))
    return toks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load legacy parent definitions using carp_app/pipelines/legacy_imaging_config.toml (STRICT)."
    )
    parser.add_argument(
        "--config",
        default="carp_app/pipelines/legacy_imaging_config.toml",
        help="Path to legacy imaging pipeline config TOML",
    )
    parser.add_argument(
        "--db-url",
        help="Override DB_URL",
    )
    args = parser.parse_args()

    cfg = load_config((REPO_ROOT / args.config).resolve())

    forbidden = [str(x).strip().lower() for x in cfg.get("invariants", {}).get("forbidden_tokens", []) if str(x).strip()]
    table_qualified = cfg["parent_definitions"]["table"]
    schema, table = _split_schema_table(table_qualified)

    csv_path = _resolve_csv_path(REPO_ROOT, cfg)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path, low_memory=False)

    expected_cols = ["parent_fish_name", "plasmid_base_code", "allele", "injected_rna", "injected_plasmid"]
    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        raise SystemExit(f"{csv_path} missing expected columns {missing}; columns={list(df.columns)}")

    df_out = pd.DataFrame()
    df_out["parent_fish_name"] = df["parent_fish_name"].astype(str).str.strip().where(~df["parent_fish_name"].isna(), None)
    df_out["allele"] = df["allele"].astype(str).str.strip().where(~df["allele"].isna(), None)

    df_out["plasmid_base_code"] = df["plasmid_base_code"].apply(_canonicalize_field)
    df_out["injected_rna"] = df["injected_rna"].apply(_canonicalize_field)
    df_out["injected_plasmid"] = df["injected_plasmid"].apply(_canonicalize_field)

    all_tokens: List[str] = []
    for r in df_out.to_dict(orient="records"):
        for t in _all_tokens_from_row(r):
            all_tokens.append(t)

    bad_forbidden = sorted(set(t for t in all_tokens if t in set(forbidden)))
    if bad_forbidden:
        raise SystemExit(f"[STOP] forbidden token(s) present after canonicalization: {bad_forbidden}")

    eng = get_engine(args.db_url)

    try:
        resolve_construct_ids(eng, all_tokens)
    except TokenError as e:
        raise SystemExit(f"[STOP] unresolved construct token(s) in parent definitions CSV {csv_path}: {e}") from e

    print("[INFO] legacy_parent_definitions_v9: sample rows (canonicalized):")
    print(df_out.head(15).to_string(index=False))

    with eng.begin() as cx:
        cx.execute(text(f"TRUNCATE {schema}.{table}"))
        df_out.to_sql(
            table,
            cx,
            schema=schema,
            if_exists="append",
            index=False,
        )

    print(f"[OK] loaded {len(df_out)} row(s) into {schema}.{table} from {csv_path}")


if __name__ == "__main__":
    main()
