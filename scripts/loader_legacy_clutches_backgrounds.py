#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional, Set, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(db_url: Optional[str]) -> Engine:
    url = db_url or os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set (or pass --db-url)")
    print(f"DB_URL={url}")
    return create_engine(url)


_NULLS = {"", "nan", "none", "na", "n/a", "<na>"}


def norm(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in _NULLS:
        return ""
    return s


def infer_bg_from_parents(parent_female: str, parent_male: str) -> str:
    s = f"{parent_female} {parent_male}".casefold()
    if "casper" in s or "rnf" in s:
        return "casper"
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--db-url")
    ap.add_argument("--force-bg", default="")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"[STOP] missing CSV: {csv_path}")

    df = pd.read_csv(csv_path, low_memory=False)
    if "clutch_code" not in df.columns:
        raise SystemExit(f"[STOP] CSV missing clutch_code: {csv_path}")

    df = df.copy()
    df["clutch_code"] = df["clutch_code"].astype(str).str.strip()
    df = df[df["clutch_code"].str.strip().ne("")].copy()

    force_bg = norm(args.force_bg)

    if force_bg:
        df["genetic_background"] = force_bg
    else:
        pf = df.get("parent_female")
        pm = df.get("parent_male")
        if pf is None or pm is None:
            df["genetic_background"] = ""
        else:
            df["genetic_background"] = [
                infer_bg_from_parents(norm(a), norm(b)) for a, b in zip(pf.tolist(), pm.tolist())
            ]

    updates = df[["clutch_code", "genetic_background"]].copy()
    updates["genetic_background"] = updates["genetic_background"].astype(str).str.strip()
    updates = updates.drop_duplicates(subset=["clutch_code"]).reset_index(drop=True)

    rows: list[tuple[str, str]] = [
        (str(r["clutch_code"]).strip(), str(r["genetic_background"]).strip())
        for _, r in updates.iterrows()
    ]

    engine = get_engine(args.db_url)

    with engine.begin() as cx:
        cx.execute(text("CREATE TEMP TABLE _bg_updates (clutch_code text PRIMARY KEY, genetic_background text);"))

        raw = cx.connection
        try:
            from psycopg2.extras import execute_values
        except Exception as e:
            raise SystemExit(f"[STOP] psycopg2.extras unavailable: {e}")

        with raw.cursor() as cur:
            execute_values(
                cur,
                "INSERT INTO _bg_updates (clutch_code, genetic_background) VALUES %s "
                "ON CONFLICT (clutch_code) DO UPDATE SET genetic_background = EXCLUDED.genetic_background",
                rows,
                page_size=1000,
            )

        cx.execute(
            text(
                """
                UPDATE public.clutches c
                SET genetic_background = u.genetic_background
                FROM _bg_updates u
                WHERE c.source_system = 'legacy_imaging'
                  AND c.import_batch_id = :batch
                  AND c.clutch_code = u.clutch_code
                """
            ),
            {"batch": args.batch},
        )

        qc = cx.execute(
            text(
                """
                SELECT
                  count(*) FILTER (WHERE c.source_system='legacy_imaging' AND c.import_batch_id=:batch) AS n_legacy_clutches_in_batch,
                  count(*) FILTER (WHERE c.source_system='legacy_imaging' AND c.import_batch_id=:batch AND coalesce(btrim(c.genetic_background),'') <> '') AS n_with_bg,
                  string_agg(DISTINCT c.genetic_background, ', ' ORDER BY c.genetic_background)
                    FILTER (WHERE c.source_system='legacy_imaging' AND c.import_batch_id=:batch AND coalesce(btrim(c.genetic_background),'') <> '') AS bg_values
                FROM public.clutches c
                """
            ),
            {"batch": args.batch},
        ).fetchone()

    print("[OK] updated clutch backgrounds rows=", len(updates))
    print("[QC]", dict(qc._mapping))


if __name__ == "__main__":
    main()
