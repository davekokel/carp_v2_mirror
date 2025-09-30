#!/usr/bin/env python3
from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Optional, Iterable

from sqlalchemy import create_engine, text

# ---------- DSN helper ----------
def _normalize_dsn(url: str) -> str:
    """Prefer psycopg v3 driver for SQLAlchemy."""
    return (
        "postgresql+psycopg://" + url[len("postgresql://"):]
        if url.startswith("postgresql://") and "+psycopg" not in url
        else url
    )

# ---------- tiny utils ----------
def _str(x: Optional[str]) -> str:
    return (x or "").strip()

def _to_numeric(s: Optional[str]):
    from decimal import Decimal, InvalidOperation
    s = _str(s)
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None

def _iter_csv(path: Path) -> Iterable[dict]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        if r.fieldnames:
            r.fieldnames = [(h or "").lstrip("\ufeff").strip() for h in r.fieldnames]
        for row in r:
            yield { (k or "").lstrip("\ufeff").strip(): (v or "").strip() for k, v in row.items() }

# ---------- SQL ----------
SQL_GET_FISH_ID = text("""
select id from public.fish where name = :name
""")

SQL_UPSERT_RNA_GET_ID = text("""
with ins as (
  insert into public.rnas (rna_code, name)
  values (:code, coalesce(nullif(:name,''), :code))
  on conflict (rna_code) do nothing
  returning id_uuid
)
select id_uuid from ins
union all
select id_uuid from public.rnas where rna_code = :code
limit 1
""")

SQL_INSERT_RNA_TREATMENT = text("""
insert into public.injected_rna_treatments (fish_id, rna_id, amount, units, note)
values (:fish_id, :rna_id, :amount, :units, :note)
on conflict do nothing
""")

# ---------- main ----------
def main():
    import argparse

    ap = argparse.ArgumentParser(description="Load injected RNA treatments from a narrow CSV.")
    ap.add_argument("--db", required=True, help="DB URL (e.g., postgresql://user:pw@host:port/db?sslmode=require)")
    ap.add_argument("--csv", required=True, help="CSV with columns: fish_name, rna_code, amount, units, note")
    ap.add_argument("--dry-run", action="store_true", help="Run without writing to DB")
    args = ap.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(2)

    eng = create_engine(
        _normalize_dsn(args.db),
        pool_pre_ping=True,
        future=True,
        connect_args={"prepare_threshold": None},
    )

    rows = list(_iter_csv(csv_path))
    if not rows:
        print("No rows in CSV.")
        return

    inserted = 0
    attempted = 0
    skipped_missing_fish = 0

    with eng.connect() as cx:
        trans = cx.begin()
        try:
            for row in rows:
                fish_name = _str(row.get("fish_name"))
                rna_code  = _str(row.get("rna_code"))
                if not fish_name or not rna_code:
                    continue

                fish_id = cx.execute(SQL_GET_FISH_ID, {"name": fish_name}).scalar()
                if not fish_id:
                    skipped_missing_fish += 1
                    continue

                rid = cx.execute(
                    SQL_UPSERT_RNA_GET_ID,
                    {"code": rna_code, "name": rna_code},
                ).scalar()

                if not rid:
                    # Shouldn't happen, but guard anyway
                    continue

                amount = _to_numeric(row.get("amount"))
                units  = _str(row.get("units")) or None
                note   = _str(row.get("note")) or None

                attempted += 1
                res = cx.execute(
                    SQL_INSERT_RNA_TREATMENT,
                    {"fish_id": fish_id, "rna_id": rid, "amount": amount, "units": units, "note": note},
                )
                if getattr(res, "rowcount", 0) > 0:
                    inserted += 1

            if args.dry_run:
                trans.rollback()
                print("DRY-RUN: rolled back all changes.")
            else:
                trans.commit()
        except Exception:
            trans.rollback()
            raise

    dupes = max(attempted - inserted, 0)
    print(f"Inserted {inserted}/{attempted} RNA treatment rows; {dupes} duplicates skipped; {skipped_missing_fish} rows skipped (fish not found).")

if __name__ == "__main__":
    main()