#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.fish_v11_shared import (
    ensure_tank_for_instance,
    ensure_line_alleles_for_line,
)

FISH_XLSX_DEFAULT = "seed_kits/2025-11-15-121231-autoload/fish.xlsx"


# ───────────────────────────────────────────────────────────────────────────────
# SMALL HELPERS
# ───────────────────────────────────────────────────────────────────────────────

def norm(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip()


def norm_or_none(s: Any) -> Optional[str]:
    s2 = norm(s)
    return s2 or None


def coerce_date(v: Any) -> Optional[date]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return None


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL is not set")
    return create_engine(url)


# ───────────────────────────────────────────────────────────────────────────────
# CANONICAL CONSTRUCT NORMALIZATION
# format: lower(prefix) + '-' + int (no zero padding)
# examples:
#   "pDQM005"  -> "pdqm-5"
#   "PDQM-005" -> "pdqm-5"
#   "MGCO-035" -> "mgco-35"
# ───────────────────────────────────────────────────────────────────────────────

def normalize_construct_code(raw: Any) -> Optional[str]:
    s = norm(raw)
    if not s:
        return None

    prefix = ""
    i = 0
    while i < len(s) and s[i].isalpha():
        prefix += s[i]
        i += 1
    if not prefix:
        return None

    rest = s[i:]
    digits = ""
    for ch in rest:
        if ch.isdigit():
            digits += ch
        elif ch in "-_":
            continue
        else:
            break

    if not digits:
        return None

    return f"{prefix.lower()}-{int(digits)}"


def mint_construct_if_missing(cx, canonical_code: str) -> str:
    """
    Ensure there is a row in public.constructs with base_code = canonical_code.
    If not present, mint a minimal 'legacy' construct row.
    Returns canonical_code (unchanged).
    """
    canonical = norm(canonical_code)
    if not canonical:
        return ""

    df = pd.read_sql(
        text(
            """
            SELECT id::text, construct_code, base_code
            FROM public.constructs
            """
        ),
        cx,
    )

    def _norm_db(code: Any) -> str:
        return normalize_construct_code(code) or ""

    for _, r in df.iterrows():
        if _norm_db(r["base_code"]) == canonical or _norm_db(r["construct_code"]) == canonical:
            return canonical

    cx.execute(
        text(
            """
            INSERT INTO public.constructs (
              construct_code,
              base_code,
              construct_name,
              construct_kind,
              description
            )
            VALUES (
              :code,
              :code,
              :code,
              'legacy',
              'minted from v11_seed_fish_from_fish_xlsx'
            )
            ON CONFLICT (base_code) DO NOTHING;
            """
        ),
        {"code": canonical},
    )

    return canonical


# ───────────────────────────────────────────────────────────────────────────────
# ALLELES / GENOTYPES / GROUPS / LINES
# Model A: group = basecode, line = allele, instance = stage/birthday
# ───────────────────────────────────────────────────────────────────────────────

def ensure_allele_new_or_existing(
    cx,
    *,
    canonical_base_code: str,
    allele_nickname: Optional[str],
) -> Tuple[str, int, str]:
    """
    Ensure:
      1) The construct exists in public.constructs (via canonical base_code).
      2) The transgene exists in public.transgenes.
      3) We have an allele row in public.transgene_alleles, either reused or created.

    Returns (transgene_base_code, allele_number, human_label).
    """
    base = norm(canonical_base_code)
    if not base:
        raise ValueError("canonical_base_code is required for each allele.")

    # ALWAYS ensure the construct row exists before touching transgenes
    base = mint_construct_if_missing(cx, base)
    if not base:
        raise ValueError(f"Failed to mint construct for base_code={canonical_base_code!r}")

    nick = norm_or_none(allele_nickname)

    # Ensure transgene row exists and respects FK → constructs
    cx.execute(
        text(
            """
            INSERT INTO public.transgenes (transgene_base_code, description, transgene_name)
            VALUES (:bc, NULL, :bc)
            ON CONFLICT (transgene_base_code) DO NOTHING;
            """
        ),
        {"bc": base},
    )

    # Try to reuse an existing allele (same base_code + nickname)
    row = pd.read_sql(
        text(
            """
            SELECT
              allele_number,
              COALESCE(allele_name,'')     AS allele_name,
              COALESCE(allele_nickname,'') AS allele_nickname
            FROM public.transgene_alleles
            WHERE transgene_base_code = :bc
              AND (:nick IS NULL OR allele_nickname = :nick)
            ORDER BY allele_number
            LIMIT 1;
            """
        ),
        cx,
        params={"bc": base, "nick": nick},
    )

    if not row.empty:
        r = row.iloc[0]
        label = f"{base} #{int(r['allele_number'])}"
        if r["allele_nickname"]:
            label += f" ({r['allele_nickname']})"
        return base, int(r["allele_number"]), label

    # Otherwise mint a new allele number
    seq_res = cx.execute(
        text("SELECT nextval('public.transgene_alleles_allele_number_seq') AS n;")
    )
    allele_number = int(seq_res.scalar())
    allele_name = f"gu{allele_number}"

    cx.execute(
        text(
            """
            INSERT INTO public.transgene_alleles (
              transgene_base_code,
              allele_number,
              allele_name,
              allele_nickname
            )
            VALUES (
              :bc,
              :num,
              :aname,
              :nick
            )
            ON CONFLICT (transgene_base_code, allele_number) DO NOTHING;
            """
        ),
        {
            "bc": base,
            "num": allele_number,
            "aname": allele_name,
            "nick": nick,
        },
    )

    label = f"{base} #{allele_number}"
    if nick:
        label += f" ({nick})"
    return base, allele_number, label


def _lookup_construct_ids_for_bases(cx, bases: List[str]) -> Dict[str, str]:
    bases_norm = [norm(b) for b in bases if norm(b)]
    if not bases_norm:
        return {}

    df = pd.read_sql(
        text(
            """
            SELECT
              id::text AS construct_id,
              construct_code,
              base_code
            FROM public.constructs
            """
        ),
        cx,
    )

    mapping: Dict[str, str] = {}

    for _, r in df.iterrows():
        for val in (r["base_code"], r["construct_code"]):
            canon = normalize_construct_code(val)
            if canon and canon in bases_norm and canon not in mapping:
                mapping[canon] = r["construct_id"]

    return mapping


def ensure_group_and_genotype_for_alleles(
    cx,
    *,
    resolved_alleles: List[Dict[str, Any]],
) -> Tuple[str, str, str]:
    """
    Given resolved alleles (canonical transgene_base_code + allele_number),
    find or create genotype + fish_group + join_fish_group_alleles.
    """
    if not resolved_alleles:
        raise ValueError("No alleles to build genotype / fish_group.")

    bases = [norm(a["transgene_base_code"]) for a in resolved_alleles]
    base_to_id = _lookup_construct_ids_for_bases(cx, bases)
    missing = [b for b in bases if b not in base_to_id]
    if missing:
        raise ValueError(f"Missing construct_id for base_code(s): {missing}")

    pairs = [(norm(a["transgene_base_code"]), int(a["allele_number"])) for a in resolved_alleles]
    pairs_sorted = sorted(pairs)
    target = set(pairs_sorted)

    df = pd.read_sql(
        text(
            """
            SELECT
              fg.id::text        AS fish_group_id,
              fg.genotype_key    AS genotype_key,
              g.id::text         AS genotype_v11_id,
              c.base_code        AS construct_base_code,
              j.allele_number    AS allele_number
            FROM public.fish_groups fg
            JOIN public.genotypes_v11 g
              ON g.genotype_code = fg.genotype_key
            JOIN public.join_fish_group_alleles j
              ON j.fish_group_id = fg.id
            JOIN public.constructs c
              ON c.id = j.construct_id;
            """
        ),
        cx,
    )

    if not df.empty:
        grouped = df.groupby(
            ["fish_group_id", "genotype_key", "genotype_v11_id"], as_index=False
        )
        for (fg_id, gkey, g_id), sub in grouped:
            existing_pairs = set(
                (
                    normalize_construct_code(sub_row["construct_base_code"]) or "",
                    int(sub_row["allele_number"]),
                )
                for _, sub_row in sub.iterrows()
            )
            if existing_pairs == target:
                return fg_id, g_id, gkey

    genotype_basecodes = " + ".join(f"{b}:{n}" for b, n in pairs_sorted)

    import uuid
    genotype_code = "G-" + uuid.uuid4().hex[:8]
    genotype_pretty = genotype_basecodes

    g_row = cx.execute(
        text(
            """
            INSERT INTO public.genotypes_v11 (
              genotype_code,
              genotype_pretty,
              genotype_basecodes,
              source_system
            )
            VALUES (
              :gcode,
              :gpretty,
              :gbasecodes,
              'v11_seed_fish_from_fish_xlsx'
            )
            RETURNING id::text AS genotype_v11_id, genotype_code;
            """
        ),
        {"gcode": genotype_code, "gpretty": genotype_pretty, "gbasecodes": genotype_basecodes},
    ).fetchone()

    genotype_v11_id = g_row._mapping["genotype_v11_id"]
    genotype_code = g_row._mapping["genotype_code"]

    group_code = "GROUP-" + uuid.uuid4().hex[:8]
    fg_row = cx.execute(
        text(
            """
            INSERT INTO public.fish_groups (
              genotype_key,
              nickname,
              created_at,
              group_code
            )
            VALUES (
              :gkey,
              NULL,
              now(),
              :gcode
            )
            RETURNING id::text AS fish_group_id;
            """
        ),
        {"gkey": genotype_code, "gcode": group_code},
    ).fetchone()

    fish_group_id = fg_row._mapping["fish_group_id"]

    for base, num in pairs_sorted:
        construct_id = base_to_id[base]
        cx.execute(
            text(
                """
                INSERT INTO public.join_fish_group_alleles (
                  fish_group_id,
                  construct_id,
                  allele_number
                )
                VALUES (
                  :fgid,
                  :cid,
                  :anum
                )
                ON CONFLICT DO NOTHING;
                """
            ),
            {"fgid": fish_group_id, "cid": construct_id, "anum": num},
        )

    return fish_group_id, genotype_v11_id, genotype_code


def generate_line_code(cx) -> str:
    import uuid
    attempt = 0
    while True:
        attempt += 1
        candidate = f"LINE-{uuid.uuid4().hex[:8]}"
        existing = pd.read_sql(
            text(
                """
                SELECT 1
                FROM public.fish_lines
                WHERE line_code = :code
                LIMIT 1;
                """
            ),
            cx,
            params={"code": candidate},
        )
        if existing.empty:
            return candidate
        if attempt > 10:
            raise RuntimeError("Failed to generate unique line_code after 10 attempts")


def ensure_line_for_description(
    cx,
    *,
    fish_group_id: str,
    nickname: str,
    primary_base_code: str,
    default_bg_code: str,
) -> Tuple[str, str, bool]:
    nn = norm(nickname)
    bc = norm(primary_base_code)

    if not nn:
        raise ValueError("Line nickname is required.")
    if not bc:
        raise ValueError("Primary construct base_code is required to define the line.")
    if not fish_group_id:
        raise ValueError("fish_group_id is required to create a line.")

    existing = pd.read_sql(
        text(
            """
            SELECT id::text AS line_id, line_code::text AS line_code
            FROM public.fish_lines
            WHERE nickname = :nn
              AND construct_code = :bc
              AND fish_group_id = :fgid
            ORDER BY created_at ASC
            LIMIT 1;
            """
        ),
        cx,
        params={"nn": nn, "bc": bc, "fgid": fish_group_id},
    )

    if not existing.empty:
        r = existing.iloc[0]
        return r["line_id"], r["line_code"], False

    line_code = generate_line_code(cx)
    line_row = cx.execute(
        text(
            """
            INSERT INTO public.fish_lines (
              line_code,
              nickname,
              genetic_background,
              line_building_stage,
              notes,
              created_at,
              fish_group_id,
              group_instance_code,
              construct_code
            )
            VALUES (
              :code,
              :nickname,
              :bg,
              NULL,
              NULL,
              now(),
              :fgid,
              NULL,
              :construct_code
            )
            RETURNING id::text AS line_id, line_code;
            """
        ),
        {
            "code": line_code,
            "nickname": nn,
            "bg": default_bg_code,
            "fgid": fish_group_id,
            "construct_code": bc,
        },
    ).fetchone()

    return line_row._mapping["line_id"], line_row._mapping["line_code"], True


def generate_fish_code(provided: Optional[str]) -> str:
    s = norm(provided)
    if s:
        return s
    import uuid
    return f"FSH-{uuid.uuid4().hex[:8]}"


def create_instance_with_genotype_and_bg(
    cx,
    *,
    line_id: str,
    line_code: str,
    genotype_v11_id: str,
    fish_code: str,
    instance_stage: Optional[str],
    birthday: date,
    bg_code: str,
    notes: Optional[str],
) -> str:
    suffix = "001"
    prefix = instance_stage or "inst"
    line_instance_code = f"{line_code}-{prefix}-{suffix}"

    ins = cx.execute(
        text(
            """
            INSERT INTO public.fish_instances_v10 (
              line_id,
              fish_code,
              line_instance_code,
              birthday,
              instance_stage,
              notes,
              genotype_v11_id,
              genetic_background,
              created_at
            )
            VALUES (
              :line_id,
              :fish_code,
              :line_instance_code,
              :birthday,
              :instance_stage,
              :notes,
              :genotype_id,
              :bg,
              now()
            )
            RETURNING id::text AS fish_instance_id;
            """
        ),
        {
            "line_id": line_id,
            "fish_code": fish_code,
            "line_instance_code": line_instance_code,
            "birthday": birthday,
            "instance_stage": instance_stage,
            "notes": notes,
            "genotype_id": genotype_v11_id,
            "bg": bg_code,
        },
    ).fetchone()

    return ins._mapping["fish_instance_id"]


# ───────────────────────────────────────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fish-xlsx",
        default=FISH_XLSX_DEFAULT,
        help="Path to fish.xlsx (defaults to autoload kit).",
    )
    args = parser.parse_args()

    path = Path(args.fish_xlsx)
    if not path.exists():
        raise SystemExit(f"fish.xlsx not found: {path}")

    df = pd.read_excel(path)

    required = [
        "line_nickname",
        "birthday",
        "genetic_background",
        "instance_stage",
        "transgene_base_code",
        "allele_nickname",
        "zygosity",
        "created_by",
        "description",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing columns in fish.xlsx: {missing}")

    df = df.copy()
    df["line_nickname"] = df["line_nickname"].map(norm)
    df["genetic_background"] = df["genetic_background"].map(norm)
    df["instance_stage"] = df["instance_stage"].map(norm)
    df["transgene_base_code"] = df["transgene_base_code"].map(norm)
    df["allele_nickname"] = df["allele_nickname"].map(norm)
    df["description"] = df["description"].map(norm)
    df["birthday"] = df["birthday"].map(coerce_date)

    df = df[(df["line_nickname"] != "") & (df["transgene_base_code"] != "")]
    if df.empty:
        print("no usable rows")
        return

    engine = get_engine()

    with engine.begin() as cx:
        created_instances = 0
        created_lines = 0
        reused_lines = 0
        skipped = 0

        backgrounds = set(
            pd.read_sql(
                text("SELECT bg_code FROM public.genetic_backgrounds"),
                cx,
            )["bg_code"].map(norm)
        )

        for idx, row in df.iterrows():
            raw_code = row["transgene_base_code"]
            canonical = normalize_construct_code(raw_code)
            if canonical:
                canonical = mint_construct_if_missing(cx, canonical)

            if not canonical:
                print(
                    f"[ROW {idx}] skipping: transgene_base_code={raw_code} "
                    "does not map to a canonical construct code"
                )
                skipped += 1
                continue

            line_nick = row["line_nickname"]
            bday = row["birthday"]
            bg_code = row["genetic_background"]
            stage = row["instance_stage"]
            allele_nick = row["allele_nickname"]
            notes = row["description"]

            if not bday:
                raise ValueError(f"[ROW {idx}] missing birthday for line '{line_nick}'")
            if not bg_code or norm(bg_code) not in backgrounds:
                raise ValueError(
                    f"[ROW {idx}] genetic_background '{bg_code}' not present in public.genetic_backgrounds"
                )

            base2, num, label = ensure_allele_new_or_existing(
                cx,
                canonical_base_code=canonical,
                allele_nickname=allele_nick,
            )

            resolved_alleles = [
                {
                    "transgene_base_code": base2,
                    "allele_number": num,
                    "label": label,
                }
            ]

            fish_group_id, genotype_v11_id, genotype_code = ensure_group_and_genotype_for_alleles(
                cx,
                resolved_alleles=resolved_alleles,
            )

            line_id, line_code, created_new_line = ensure_line_for_description(
                cx,
                fish_group_id=fish_group_id,
                nickname=line_nick,
                primary_base_code=base2,
                default_bg_code=bg_code,
            )

            ensure_line_alleles_for_line(
                cx,
                line_id=line_id,
                resolved_alleles=resolved_alleles,
            )

            if created_new_line:
                created_lines += 1
            else:
                reused_lines += 1

            fish_code = generate_fish_code(None)
            fish_instance_id = create_instance_with_genotype_and_bg(
                cx,
                line_id=line_id,
                line_code=line_code,
                genotype_v11_id=genotype_v11_id,
                fish_code=fish_code,
                instance_stage=stage,
                birthday=bday,
                bg_code=bg_code,
                notes=notes,
            )

            ensure_tank_for_instance(cx, fish_instance_id, fish_code)
            created_instances += 1

            print(
                f"[ROW {idx}] line {line_code} (genotype {genotype_code}) "
                f"+ 1 instance (FSH={fish_code})"
            )

        print(
            f"[v11_seed_fish_from_fish_xlsx] total instances={created_instances}, "
            f"lines created={created_lines}, lines reused={reused_lines}, "
            f"skipped_bad_construct_code={skipped}"
        )


if __name__ == "__main__":
    main()