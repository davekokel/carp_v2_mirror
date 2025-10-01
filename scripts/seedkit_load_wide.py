#!/usr/bin/env python3
from __future__ import annotations

import csv
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Iterable

from sqlalchemy import create_engine, text


# ---------- helpers ----------
def _normalize_dsn(url: str) -> str:
    """Prefer psycopg v3 driver for SQLAlchemy."""
    return (
        "postgresql+psycopg://" + url[len("postgresql://"):]
        if url.startswith("postgresql://") and "+psycopg" not in url
        else url
    )

def _str(x: Optional[str]) -> str:
    return (x or "").strip()

def _nz(x: Optional[str]) -> Optional[str]:
    v = (x or "").strip()
    return v or None

def _parse_date(s: Optional[str]):
    s = _str(s)
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None

def _to_numeric(s: Optional[str]):
    """Return Decimal for numeric strings; None otherwise."""
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
        try:
            r.fieldnames = [(h or "").lstrip("\ufeff").strip() for h in (r.fieldnames or [])]
        except Exception:
            pass
        for row in r:
            yield {(k or "").lstrip("\ufeff").strip(): (v or "").strip() for k, v in row.items()}

def _list_tokens(val: Optional[str]) -> list[str]:
    """Split comma/semicolon/slash separated values into clean tokens."""
    return [t.strip() for t in re.split(r"[,;/]", val or "") if t.strip()]


# ---------- SQL (alleles) ----------
SQL_UPSERT_FISH = text("""
INSERT INTO public.fish (
  name, batch_label, line_building_stage, nickname, strain, date_of_birth, description
)
VALUES (:name, :batch, :stage, :nickname, :strain, :dob, :description)
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
VALUES (:code, :allele_number, NULLIF(:desc, ''))
ON CONFLICT (transgene_base_code, allele_number) DO UPDATE SET
  description = COALESCE(NULLIF(EXCLUDED.description,''), public.transgene_alleles.description)
""")

SQL_LINK_FISH_ALLELE = text("""
INSERT INTO public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
VALUES (:fish_id, :code, :allele_number)
ON CONFLICT DO NOTHING
""")

# ---------- SQL (plasmids id-based) ----------
SQL_UPSERT_PLASMID_GET_ID = text("""
with ins as (
  insert into public.plasmids (plasmid_code, name)
  values (:code, coalesce(nullif(:name,''), :code))
  on conflict (plasmid_code) do nothing
  returning id_uuid
)
select id_uuid from ins
union all
select id_uuid from public.plasmids where plasmid_code = :code
limit 1
""")

SQL_LINK_FISH_PLASMID = text("""
insert into public.fish_plasmids (fish_id, plasmid_id)
values (:fish_id, :plasmid_id)
on conflict do nothing
""")

# ---------- RNA SQL ----------
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

SQL_CREATE_RNA_TREATMENT = text("""
insert into public.treatments (treatment_type, performed_at, operator, notes)
values ('injected_rna', now(), :operator, :note)
returning id
""")

SQL_INSERT_RNA_TREATMENT = text("""
insert into public.injected_rna_treatments (treatment_id, fish_id, rna_id, amount, units, note)
values (:treatment_id, :fish_id, :rna_id, :amount, :units, :note)
on conflict do nothing
""")

# ---------- PLASMID injection SQL ----------
SQL_CREATE_PLASMID_TREATMENT = text("""
insert into public.treatments (treatment_type, performed_at, operator, notes)
values ('injected_plasmid', now(), :operator, :note)
returning id
""")

SQL_INSERT_PLASMID_TREATMENT = text("""
insert into public.injected_plasmid_treatments (treatment_id, fish_id, plasmid_id, amount, units, note)
values (:treatment_id, :fish_id, :plasmid_id, :amount, :units, :note)
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
        "dob": _parse_date(row.get("birth_date") or row.get("date_of_birth") or row.get("dob")),
        "description": _nz(row.get("description") or row.get("notes")),
    }


# ---------- allele allocator / resolver ----------
def _alloc_or_get_alleles(cx, code: str, legacy_label: str | None):
    """
    Resolve canonical allele_number(s) via DB allocator.
    - CSV never supplies allele_number.
    - If a legacy label is provided, bind it the first time and always reuse.
    - If no legacy label is provided, allocate/return the next number for this base_code.
    Returns a list of string allele_numbers (usually length 1).
    """
    nums: list[str] = []
    code = (code or "").strip()
    if not code:
        return nums

    # Support multi-legacy input like "304; 305" if it ever appears
    tokens = []
    if legacy_label:
        tokens = [x.strip() for x in re.split(r"[;,]", legacy_label) if x.strip()]

    if not tokens:
        n = cx.execute(text("select public.allocate_allele_number(:base_code, :legacy_label)"),
                       {"base_code": code, "legacy_label": None}).scalar()
        nums.append(str(n))
        return nums

    for lab in tokens:
        n = cx.execute(text("select public.allocate_allele_number(:base_code, :legacy_label)"),
                       {"base_code": code, "legacy_label": lab}).scalar()
        nums.append(str(n))

    return nums
# >>> ALLELE_ALLOCATOR_PATCH:END

# ---------- main ----------
def main():
    import argparse

    ap = argparse.ArgumentParser(description="Load WIDE seedkit CSV into core tables.")
    ap.add_argument("--db", required=True, help="DB URL, e.g. postgresql://user:pw@host:port/db?sslmode=require")
    ap.add_argument("--csv", required=True, help="Path to wide CSV")
    ap.add_argument("--require-existing-fish", action="store_true", help="Do not create missing fish; error if fish name not found or ambiguous.")
    ap.add_argument("--dry-run", action="store_true", help="Run without writing to DB")
    ap.add_argument("--operator", default="seedkit_loader",
                    help="Operator to record on created treatments (default: seedkit_loader)")
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
    attempted = 0  # allele links attempted

    with eng.connect() as cx:
        trans = cx.begin()
        try:
            for row in rows:
                p = _row_params(row)
                if not p["name"]:
                    continue  # require fish name

                # Resolve / upsert fish
                fish_ids = cx.execute(
                    text("select id from public.fish where name = :name"),
                    {"name": p["name"]},
                ).scalars().all()

                if args.require_existing_fish:
                    if not fish_ids:
                        raise RuntimeError(f"Fish '{p['name']}' not found (rerun without --require-existing-fish to create).")
                    if len(fish_ids) > 1:
                        raise RuntimeError(f"Fish '{p['name']}' is ambiguous: {len(fish_ids)} rows in public.fish.")
                    fish_id = fish_ids[0]
                else:
                    if len(fish_ids) == 1:
                        fish_id = fish_ids[0]
                    elif len(fish_ids) > 1:
                        raise RuntimeError(
                            f"Fish '{p['name']}' is ambiguous: {len(fish_ids)} rows in public.fish "
                            f"(use --require-existing-fish and disambiguate)."
                        )
                    else:
                        fish_id = cx.execute(SQL_UPSERT_FISH, p).scalar()

                # ----- Alleles -----
                code   = _str(row.get("transgene_base_code"))
                legacy = _str(row.get("legacy_allele_number") or row.get("allele_label_legacy"))
                if code:
                    cx.execute(SQL_UPSERT_TRANSGENE, {"code": code, "name": code})

                    # Reuse existing link for this fish+base_code if present (prevents new numbers)
                    existing_nums = cx.execute(
                        text("""
                            select allele_number
                            from public.fish_transgene_alleles
                            where fish_id = :fish_id and transgene_base_code = :code
                            order by allele_number
                        """),
                        {"fish_id": fish_id, "code": code},
                    ).scalars().all()

                    nums = [str(existing_nums[0])] if existing_nums else _alloc_or_get_alleles(cx, code, legacy)

                    for num in nums:
                        # ensure allele row exists/described
                        cx.execute(SQL_UPSERT_ALLELE, {"code": code, "allele_number": num, "desc": ""})
                        attempted += 1
                        res = cx.execute(
                            SQL_LINK_FISH_ALLELE,
                            {"fish_id": fish_id, "code": code, "allele_number": num},
                        )
                        if getattr(res, "rowcount", 0) > 0:
                            linked += 1

                # ----- Plasmids (id-based linking only; not injections) -----
                plasmid_tokens = _list_tokens(
                    row.get("plasmids") or row.get("plasmid_codes") or row.get("plasmid_code")
                )
                for plc in plasmid_tokens:
                    pid = cx.execute(SQL_UPSERT_PLASMID_GET_ID, {"code": plc, "name": plc}).scalar()
                    if pid:
                        cx.execute(SQL_LINK_FISH_PLASMID, {"fish_id": fish_id, "plasmid_id": pid})

                # ----- Injected RNAs (one treatment per RNA token) -----
                rna_tokens = _list_tokens(row.get("rnas") or row.get("rna_codes") or row.get("rna_code"))
                print(f"[loader] fish={p['name']!r} rna_tokens={rna_tokens}")

                rna_amount = _to_numeric(row.get("rna_amount"))
                rna_units  = _nz(row.get("rna_units"))
                rna_note   = _nz(row.get("rna_note"))

                if rna_tokens:
                    for rcode in rna_tokens:
                        rid = cx.execute(SQL_UPSERT_RNA_GET_ID, {"code": rcode, "name": rcode}).scalar()
                        if not rid:
                            continue
                        treatment_id = cx.execute(
                            SQL_CREATE_RNA_TREATMENT,
                            {"operator": args.operator, "note": rna_note},
                        ).scalar()
                        print(f"[loader] created RNA treatment_id={treatment_id} for RNA={rcode!r} note={rna_note!r}")

                        cx.execute(
                            SQL_INSERT_RNA_TREATMENT,
                            {
                                "treatment_id": treatment_id,
                                "fish_id": fish_id,
                                "rna_id": rid,
                                "amount": rna_amount,
                                "units": rna_units,
                                "note": rna_note,
                            },
                        )
                        print(
                            f"[loader] RNA detail: fish_id={fish_id} rna_id={rid} "
                            f"amount={rna_amount} units={rna_units!r} note={rna_note!r}"
                        )

                # ----- Injected Plasmids (one treatment per plasmid token) -----
                plasmid_inj_tokens = _list_tokens(
                    row.get("injected_plasmids")
                    or row.get("plasmids_injected")
                    or row.get("plasmid_injection_codes")
                )
                plasmid_amount = _to_numeric(row.get("plasmid_amount"))
                plasmid_units  = _nz(row.get("plasmid_units"))
                plasmid_note   = _nz(row.get("plasmid_note"))

                if plasmid_inj_tokens:
                    for plc in plasmid_inj_tokens:
                        pid = cx.execute(SQL_UPSERT_PLASMID_GET_ID, {"code": plc, "name": plc}).scalar()
                        if not pid:
                            continue
                        ptid = cx.execute(
                            SQL_CREATE_PLASMID_TREATMENT,
                            {"operator": args.operator, "note": plasmid_note},
                        ).scalar()
                        print(f"[loader] created PLASMID treatment_id={ptid} for plasmid={plc!r} note={plasmid_note!r}")

                        cx.execute(
                            SQL_INSERT_PLASMID_TREATMENT,
                            {
                                "treatment_id": ptid,
                                "fish_id": fish_id,
                                "plasmid_id": pid,
                                "amount": plasmid_amount,
                                "units": plasmid_units,
                                "note": plasmid_note,
                            },
                        )
                        print(
                            f"[loader] plasmid detail: fish_id={fish_id} plasmid_id={pid} "
                            f"amount={plasmid_amount} units={plasmid_units!r} note={plasmid_note!r}"
                        )

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
    print("RNA and plasmid injection treatments created as needed (see DB for details).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[loader] ERROR: {e}", file=sys.stderr, flush=True)
        raise