#!/usr/bin/env python3
from __future__ import annotations

import csv
import sys
from pathlib import Path
from datetime import datetime
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

# ---------- parsing helpers ----------
def _str(x: Optional[str]) -> str:
    return (x or "").strip()

def _nz(x: Optional[str]) -> Optional[str]:
    """Normalize blanks to None (NULL in SQL)."""
    v = (x or "").strip()
    return v or None

def _parse_date(s: Optional[str]):
    s = _str(s)
    if not s:
        return None
    # Accept common lab formats; 8/16/24, 2024-08-16, etc.
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None

def _iter_csv(path: Path) -> Iterable[dict]:
    # utf-8-sig consumes BOM; also defensively strip BOM from header names
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        try:
            r.fieldnames = [(h or "").lstrip("\ufeff").strip() for h in (r.fieldnames or [])]
        except Exception:
            pass
        for row in r:
            yield {(k or "").lstrip("\ufeff").strip(): (v or "").strip() for k, v in row.items()}

# ---------- list parsing ----------
def _split_list(s: Optional[str]) -> list[str]:
    """Split on ; or , and trim; returns [] on blank."""
    if not s:
        return []
    raw = [x.strip() for x in re.split(r"[;,]", s) if x.strip()]
    # de-dup preserving order
    seen, out = set(), []
    for x in raw:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

# ---------- SQL (all :named binds) ----------
SQL_UPSERT_FISH = text("""
INSERT INTO public.fish (
  name,
  batch_label,
  line_building_stage,
  nickname,
  strain,
  date_of_birth,
  description
)
VALUES (
  :name, :batch, :stage, :nickname, :strain, :dob, :description
)
ON CONFLICT (name) DO UPDATE SET
  batch_label         = EXCLUDED.batch_label,
  line_building_stage = EXCLUDED.line_building_stage,
  nickname            = EXCLUDED.nickname,
  strain              = EXCLUDED.strain,
  date_of_birth       = EXCLUDED.date_of_birth,
  description         = EXCLUDED.description
RETURNING id
""")

SQL_UPSERT_TRANSGENE = text("""
INSERT INTO public.transgenes (transgene_base_code, name)
VALUES (:code, COALESCE(NULLIF(:name,''), :code))
ON CONFLICT (transgene_base_code) DO UPDATE SET
  name = COALESCE(NULLIF(EXCLUDED.name,''), public.transgenes.name)
""")

SQL_UPSERT_ALLELE = text("""
INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, description)
VALUES (:code, :allele_number, NULLIF(:desc,''))
ON CONFLICT (transgene_base_code, allele_number) DO UPDATE SET
  description = COALESCE(NULLIF(EXCLUDED.description,''), public.transgene_alleles.description)
""")

SQL_LINK_FISH_ALLELE = text("""
INSERT INTO public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
VALUES (:fish_id, :code, :allele_number)
ON CONFLICT DO NOTHING
""")

# ---------- catalogs + links (minimal upserts) ----------
SQL_UPSERT_PLASMID = text("""
insert into public.plasmids(code, name)
values (:code, :code)
on conflict (code) do nothing
""")

SQL_LINK_FISH_PLASMID = text("""
insert into public.fish_plasmids(fish_id, plasmid_code)
values (:fish_id, :code)
on conflict do nothing
""")

SQL_UPSERT_RNA = text("""
insert into public.rnas(code, name)
values (:code, :code)
on conflict (code) do nothing
""")

SQL_LINK_FISH_RNA = text("""
insert into public.fish_rnas(fish_id, rna_code)
values (:fish_id, :code)
on conflict do nothing
""")

SQL_UPSERT_DYE = text("""
insert into public.dyes(name)
values (:name)
on conflict (name) do nothing
""")

SQL_LINK_FISH_DYE = text("""
insert into public.fish_dyes(fish_id, dye_name)
values (:fish_id, :name)
on conflict do nothing
""")

SQL_UPSERT_FLUOR = text("""
insert into public.fluors(name)
values (:name)
on conflict (name) do nothing
""")

SQL_LINK_FISH_FLUOR = text("""
insert into public.fish_fluors(fish_id, fluor_name)
values (:fish_id, :name)
on conflict do nothing
""")

# ---------- row shaping ----------
def _row_params(row: dict) -> dict:
    return {
        "name": _str(row.get("name") or row.get("fish_name")),
        "batch": _nz(row.get("batch") or row.get("batch_label")),
        "stage": _nz(row.get("stage") or row.get("line_building_stage")),
        "nickname": _nz(row.get("nickname")),
        "strain": _nz(row.get("strain") or row.get("background_strain")),
        # CSV may use 'birth_date'; accept that plus other variants
        "dob": _parse_date(row.get("birth_date") or row.get("date_of_birth") or row.get("dob")),
        "description": _nz(row.get("description") or row.get("notes")),
        "treatments": _split_list(row.get("treatments")),
        "plasmids": _split_list(row.get("plasmid_codes")),
        "rnas": _split_list(row.get("rna_codes")),
        "dyes": _split_list(row.get("dye_names")),
        "fluors": _split_list(row.get("fluor_names")),
    }

# ---------- allele allocator / resolver ----------
def _alloc_or_get_alleles(cx, code: str, legacy_label: str | None):
    import re
    nums: list[str] = []
    if not code:
        return nums

    tokens = []
    if legacy_label:
        tokens = [x.strip() for x in re.split(r"[;,]", legacy_label) if x.strip()]

    # If no legacy label provided: allocate a fresh allele number
    if not tokens:
        n = cx.execute(text("select public.next_allele_number(:code)"), {"code": code}).scalar()
        cx.execute(text("""
            insert into public.transgene_alleles(transgene_base_code, allele_number)
            values (:code, :n)
            on conflict do nothing
        """), {"code": code, "n": str(n)})
        nums.append(str(n))
        return nums

    # Otherwise: resolve each label to an allele number (allocate if first time)
    for lab in tokens:
        n = cx.execute(text("""
            with maybe as (
              select allele_number
              from public.transgene_allele_legacy_map
              where transgene_base_code = :code and legacy_label = :lab
            )
            select coalesce(
              (select allele_number from maybe)::text,
              public.next_allele_number(:code)::text
            )
        """), {"code": code, "lab": lab}).scalar()

        # ensure core allele row exists (FK safety) then map legacy label
        cx.execute(text("""
            insert into public.transgene_alleles(transgene_base_code, allele_number)
            values (:code, :n)
            on conflict do nothing
        """), {"code": code, "n": str(n)})

        cx.execute(text("""
            insert into public.transgene_allele_legacy_map(transgene_base_code, legacy_label, allele_number)
            values (:code, :lab, :n)
            on conflict do nothing
        """), {"code": code, "lab": lab, "n": str(n)})

        nums.append(str(n))

    return nums


# --- treatments (catalog + link) ---
for tcode in p.get("treatments") or []:
    # If you have a treatments catalog, upsert it similarly;
    # or if treatments are free-text events, you could instead
    # insert into a fish_treatments(fish_id, label, at_time) table.
    cx.execute(text("""
        insert into public.treatments(code, name)
        values (:code, :code)
        on conflict (code) do nothing
    """), {"code": tcode})
    cx.execute(text("""
        insert into public.fish_treatments(fish_id, treatment_code)
        values (:fish_id, :code)
        on conflict do nothing
    """), {"fish_id": fish_id, "code": tcode})

# --- plasmids ---
for code in p.get("plasmids") or []:
    cx.execute(SQL_UPSERT_PLASMID, {"code": code})
    cx.execute(SQL_LINK_FISH_PLASMID, {"fish_id": fish_id, "code": code})

# --- rnas ---
for code in p.get("rnas") or []:
    cx.execute(SQL_UPSERT_RNA, {"code": code})
    cx.execute(SQL_LINK_FISH_RNA, {"fish_id": fish_id, "code": code})

# --- dyes ---
for name in p.get("dyes") or []:
    cx.execute(SQL_UPSERT_DYE, {"name": name})
    cx.execute(SQL_LINK_FISH_DYE, {"fish_id": fish_id, "name": name})

# --- fluors ---
for name in p.get("fluors") or []:
    cx.execute(SQL_UPSERT_FLUOR, {"name": name})
    cx.execute(SQL_LINK_FISH_FLUOR, {"fish_id": fish_id, "name": name})


# ---------- main ----------
def main():
    import argparse

    ap = argparse.ArgumentParser(description="Load WIDE seedkit CSV into core tables.")
    ap.add_argument("--db", required=True, help="DB URL, e.g. postgresql://user:pw@host:port/db?sslmode=disable")
    ap.add_argument("--csv", required=True, help="Path to wide CSV")
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
        print("No rows found in CSV.")
        return

    upserted = 0
    linked = 0
    attempted = 0

    with eng.connect() as cx:
        trans = cx.begin()
        try:
            for row in rows:
                p = _row_params(row)
                if not p["name"]:
                    continue  # require fish name

                fish_id = cx.execute(SQL_UPSERT_FISH, p).scalar()

                code   = _str(row.get("transgene_base_code"))
                legacy = _str(row.get("legacy_allele_number") or row.get("allele_label_legacy"))
                if code:
                    cx.execute(SQL_UPSERT_TRANSGENE, {"code": code, "name": code})
                    for num in _alloc_or_get_alleles(cx, code, legacy):
                        cx.execute(SQL_UPSERT_ALLELE, {"code": code, "allele_number": num, "desc": ""})
                        attempted += 1
                        res = cx.execute(
                            SQL_LINK_FISH_ALLELE,
                            {"fish_id": fish_id, "code": code, "allele_number": num},
                        )
                        if getattr(res, "rowcount", 0) > 0:
                            linked += 1

                upserted += 1

            if args.dry_run:
                trans.rollback()
                print("DRY-RUN: rolled back all changes.")
            else:
                trans.commit()
        except Exception:
            trans.rollback()
            raise

    dupes = max(attempted - linked, 0)
    print(f"Upserted {upserted} fish; linked {linked}/{attempted} new allele rows; {dupes} already existed.")


if __name__ == "__main__":
    main()
