from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection


# ─────────────────────────────────────────────────────────
# Small utilities
# ─────────────────────────────────────────────────────────

def _norm(s: Any | None) -> str:
    if s is None:
        return ""
    text_val = str(s).strip()
    if text_val in {"", "NA", "<NA>"}:
        return ""
    return text_val


def _coerce_date(value: Any) -> Optional[date]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


# ─────────────────────────────────────────────────────────
# Construct + allele + genotype core
# ─────────────────────────────────────────────────────────

def load_construct_ids(cx: Connection) -> pd.DataFrame:
    """
    Minimal construct id lookup: id, construct_code, base_code.
    """
    sql = text(
        """
        SELECT
          id::text AS construct_id,
          construct_code,
          base_code
        FROM public.constructs;
        """
    )
    return pd.read_sql(sql, cx)


def ensure_injection_treatment_single_base(
    cx: Connection,
    *,
    base_code: str,
) -> str:
    """
    Ensure there is a single-base 'injection' style treatment for this construct base_code.

    Returns treatment_id::text.
    """
    base = _norm(base_code)
    if not base:
        raise ValueError("base_code is required to create an injection treatment")

    treat_code = f"INJ-{base}"

    # Try to reuse existing treatment
    row = cx.execute(
        text(
            """
            SELECT id::text AS treatment_id
            FROM public.treatments
            WHERE treat_code = :treat_code
            LIMIT 1;
            """
        ),
        {"treat_code": treat_code},
    ).fetchone()

    if row:
        return row._mapping["treatment_id"]

    treat_text = f"Injection of {base}"

    r = cx.execute(
        text(
            """
            INSERT INTO public.treatments (
              id,
              treat_code,
              kind_code,
              treat_text,
              notes,
              created_at,
              source_system,
              import_batch_id,
              nickname,
              display_name,
              treatment_type
            )
            VALUES (
              gen_random_uuid(),
              :treat_code,
              'injection_single_base',
              :treat_text,
              NULL,
              now(),
              'fish_v11_import',
              'fish_v11_import',
              :nickname,
              :display_name,
              'injection'
            )
            RETURNING id::text AS treatment_id;
            """
        ),
        {
            "treat_code": treat_code,
            "treat_text": treat_text,
            "nickname": treat_code,
            "display_name": treat_text,
        },
    ).fetchone()

    return r._mapping["treatment_id"]


def link_instances_to_treatment(
    cx: Connection,
    *,
    fish_instance_ids: List[str],
    treatment_id: str,
    note: Optional[str] = None,
    enzyme: Optional[str] = None,
) -> None:
    """
    Link one or more fish instances to a treatment, optionally recording
    an injection enzyme (tol2, phiC, Meganuclease, etc.).

    Writes into join_fish_treatments_v11 if it exists, otherwise falls
    back to join_fish_treatments. On conflict (fish_instance_id, treatment_id),
    it preserves any existing notes/enzyme unless the incoming values are
    non-empty.
    """
    # Decide which join table to use
    tbl = "public.join_fish_treatments_v11"
    has_v11 = cx.execute(
        text("SELECT to_regclass('public.join_fish_treatments_v11') IS NOT NULL")
    ).scalar()
    if not has_v11:
        tbl = "public.join_fish_treatments"

    if not fish_instance_ids:
        return

    clean_note = (note or "").strip() or None
    clean_enzyme = (enzyme or "").strip() or None

    for fid in fish_instance_ids:
        cx.execute(
            text(
                f"""
                INSERT INTO {tbl} (
                  id,
                  fish_instance_id,
                  treatment_id,
                  created_at,
                  notes,
                  enzyme
                )
                VALUES (
                  gen_random_uuid(),
                  CAST(:fid AS uuid),
                  CAST(:tid AS uuid),
                  now(),
                  :note,
                  :enzyme
                )
                ON CONFLICT (fish_instance_id, treatment_id) DO UPDATE
                  SET notes  = COALESCE(EXCLUDED.notes, {tbl}.notes),
                      enzyme = COALESCE(EXCLUDED.enzyme, {tbl}.enzyme);
                """
            ),
            {
                "fid": fid,
                "tid": treatment_id,
                "note": clean_note,
                "enzyme": clean_enzyme,
            },
        )


def ensure_allele_new_or_existing(
    cx: Connection,
    *,
    transgene_base_code: str,
    mode: str,
    existing_allele_number: Optional[int],
    new_allele_nickname: Optional[str],
) -> Tuple[str, int]:
    """
    Ensure a (transgene_base_code, allele_number) exists in transgene_alleles.

    Returns (normalized_base_code, allele_number).
    """
    base = _norm(transgene_base_code)
    if not base:
        raise ValueError("transgene_base_code is required for each allele.")

    if mode == "Reuse existing allele":
        if existing_allele_number is None:
            raise ValueError(f"{base}: no existing allele_number selected.")
        df = pd.read_sql(
            text(
                """
                SELECT allele_number
                FROM public.transgene_alleles
                WHERE transgene_base_code = :bc
                  AND allele_number = :num
                LIMIT 1;
                """
            ),
            cx,
            params={"bc": base, "num": existing_allele_number},
        )
        if df.empty:
            raise ValueError(
                f"{base}: existing allele_number {existing_allele_number} not found."
            )
        return base, int(existing_allele_number)

    if mode != "Create new allele":
        raise ValueError(f"{base}: unknown allele mode '{mode}'")

    nick = _norm(new_allele_nickname)

    # If a nickname is provided, try to reuse by nickname
    if nick:
        df = pd.read_sql(
            text(
                """
                SELECT allele_number
                FROM public.transgene_alleles
                WHERE transgene_base_code = :bc
                  AND allele_nickname = :nick
                LIMIT 1;
                """
            ),
            cx,
            params={"bc": base, "nick": nick},
        )
        if not df.empty:
            return base, int(df.iloc[0]["allele_number"])

    # Allocate new allele number and mint a canonical name
    seq_res = cx.execute(
        text("SELECT nextval('public.transgene_alleles_allele_number_seq') AS n;")
    )
    allele_number = int(seq_res.scalar())
    allele_name = f"gu{allele_number}"

    # Ensure transgene row exists
    cx.execute(
        text(
            """
            INSERT INTO public.transgenes (transgene_base_code, description, transgene_name)
            VALUES (:bc, NULL, :bc)
            ON CONSUME CONFLICT (transgene_base_code) DO NOTHING;
            """
        ),
        {"bc": base},
    )

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
            "nick": nick or allele_name,
        },
    )

    return base, allele_number


def ensure_group_and_genotype_for_alleles(
    cx: Connection,
    *,
    resolved_alleles: List[Dict[str, Any]],
    constructs_ids_df: pd.DataFrame,
) -> Tuple[str, str, str]:
    """
    Given a set of (base_code, allele_number) pairs, ensure a genotypes_v11 row exists
    and that join_genotype_constructs_v11 links it to the constructs.

    Returns (genotype_v11_id, genotype_code, genotype_basecodes).
    """
    if not resolved_alleles:
        raise ValueError("No alleles to build genotype / fish_group.")

    # Map base_code -> construct_id via constructs table
    construct_by_base: Dict[str, str] = {}
    if not constructs_ids_df.empty:
        tmp = constructs_ids_df.copy()
        tmp["base_code"] = tmp["base_code"].astype("string").str.strip().str.lower()
        for _, r in tmp.iterrows():
            base_code_norm = (r["base_code"] or "").strip().lower()
            if base_code_norm:
                construct_by_base[base_code_norm] = r["construct_id"]

    pairs: List[Tuple[str, int]] = []
    for a in resolved_alleles:
        base = (_norm(a.get("transgene_base_code")) or "").lower()
        if not base:
            continue
        if base not in construct_by_base:
            raise ValueError(f"Construct base_code {base} not found in public.constructs.")
        try:
            num = int(a.get("allele_number"))
        except Exception:
            raise ValueError(f"{base}: invalid allele_number {a.get('allele_number')!r}")
        pairs.append((base, num))

    if not pairs:
        raise ValueError("No valid (base_code, allele_number) pairs to build genotype.")

    pairs_sorted = sorted(pairs)
    genotype_basecodes = " + ".join(f"{b}:{n}" for b, n in pairs_sorted)

    # Reuse existing genotype by basecodes
    row = cx.execute(
        text(
            """
            SELECT id::text AS genotype_v11_id, genotype_code
            FROM public.genotypes_v11
            WHERE genotype_basecodes = :gb
            LIMIT 1;
            """
        ),
        {"gb": genotype_basecodes},
    ).fetchone()

    if row:
        genotype_v11_id = row._mapping["genotype_v11_id"]
        genotype_code = row._mapping["genotype_code"]
    else:
        genotype_code = "G-" + uuid.uuid4().hex[:8]
        r = cx.execute(
            text(
                """
                INSERT INTO public.genotypes_v11 (
                  id,
                  genotype_code,
                  genotype_pretty,
                  genotype_basecodes,
                  source_system,
                  created_at
                )
                VALUES (
                  gen_random_uuid(),
                  :gcode,
                  :pretty,
                  :gbasecodes,
                  'fish_v11_import',
                  now()
                )
                RETURNING id::text AS genotype_v11_id, genotype_code;
                """
            ),
            {
                "gcode": genotype_code,
                "pretty": genotype_basecodes,
                "gbasecodes": genotype_basecodes,
            },
        ).fetchone()
        genotype_v11_id = r._mapping["genotype_v11_id"]
        genotype_code = r._mapping["genotype_code"]

        # Ensure genotype→construct links
        missing_bases = [base for base, _num in pairs_sorted if base not in construct_by_base]
        if missing_bases:
            missing_str = ", ".join(sorted(set(missing_bases)))
            raise ValueError(f"Unknown construct base_code(s) in genotype: {missing_str}")

        insert_sql = text(
            """
            INSERT INTO public.join_genotype_constructs_v11 (
              genotype_id,
              construct_id,
              created_at
            )
            VALUES (
              (:gid)::uuid,
              (:cid)::uuid,
              now()
            )
            ON CONFLICT DO NOTHING;
            """
        )

        for base, _num in pairs_sorted:
            cid = construct_by_base[base]
            cx.execute(insert_sql, {"gid": genotype_v11_id, "cid": cid})

    return genotype_v11_id, genotype_code, genotype_basecodes


def ensure_line_alleles_for_line(
    cx: Connection,
    *,
    line_id: str,
    resolved_alleles: List[Dict[str, Any]],
    constructs_ids_df: pd.DataFrame,
    default_zygosity: str = "unknown",
) -> None:
    """
    Attach canonical alleles to a line in join_line_alleles.

    resolved_alleles: list of dicts with at least
      - transgene_base_code (canonical base_code, e.g. pdqm-5, mgco-35)
      - allele_number       (canonical integer from allocator)

    constructs_ids_df: output of load_construct_ids(), used to map base_code -> construct_id.
    """
    if not resolved_alleles:
        return

    # Map base_code -> construct_id via constructs table
    construct_by_base: Dict[str, str] = {}
    if not constructs_ids_df.empty:
        tmp = constructs_ids_df.copy()
        tmp["base_code"] = tmp["base_code"].astype("string").str.strip().str.lower()
        for _, r in tmp.iterrows():
            bc = (r["base_code"] or "").strip().lower()
            if bc:
                construct_by_base[bc] = r["construct_id"]

    insert_sql = text(
        """
        INSERT INTO public.join_line_alleles (
          line_id,
          construct_id,
          allele_number,
          zygosity,
          created_at
        )
        VALUES (
          (:line_id)::uuid,
          (:construct_id)::uuid,
          :allele_number,
          :zygosity,
          now()
        )
        ON CONFLICT DO NOTHING;
        """
    )

    for a in resolved_alleles:
        base = (_norm(a.get("transgene_base_code")) or "").lower()
        if not base:
            continue
        if base not in construct_by_base:
            raise ValueError(f"Construct base_code {base} not found in public.constructs for line alleles.")

        try:
            num = int(a.get("allele_number"))
        except Exception:
            raise ValueError(f"{base}: invalid allele_number {a.get('allele_number')!r} for line alleles.")

        zyg = _norm(default_zygosity) or "unknown"
        cid = construct_by_base[base]

        cx.execute(
            insert_sql,
            {
                "line_id": line_id,
                "construct_id": cid,
                "allele_number": num,
                "zygosity": zyg,
            },
        )


def _generate_line_code(cx: Connection) -> str:
    attempt = 0
    while True:
        attempt += 1
        candidate = f"LINE-{uuid.uuid4().hex[:8]}"
        df = pd.read_sql(
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
        if df.empty:
            return candidate
        if attempt > 10:
            raise RuntimeError("Failed to generate unique line_code after 10 attempts")


def ensure_line_for_description(
    cx: Connection,
    *,
    genotype_v11_id: str,
    nickname: str,
    primary_base_code: str,
    default_bg_code: Optional[str],
) -> Tuple[str, str, bool]:
    """
    Ensure a fish_lines row exists for (nickname, primary_base_code, genotype_v11_id, bg).

    Returns (line_id, line_code, created_new_line).
    """
    nn = _norm(nickname)
    bc = _norm(primary_base_code)
    bg = _norm(default_bg_code)

    if not nn:
        raise ValueError("Line nickname is required.")
    if not bc:
        raise ValueError("Primary construct base_code is required for line.")
    if not genotype_v11_id:
        raise ValueError("genotype_v11_id is required to create a line.")

    df = pd.read_sql(
        text(
            """
            SELECT id::text AS line_id, line_code::text AS line_code
            FROM public.fish_lines
            WHERE nickname = :nn
              AND construct_code = :bc
              AND genotype_v11_id = (:gid)::uuid
              AND genetic_background IS NOT DISTINCT FROM :bg
            ORDER BY created_at ASC
            LIMIT 1;
            """
        ),
        cx,
        params={"nn": nn, "bc": bc, "gid": genotype_v11_id, "bg": bg},
    )

    if not df.empty:
        r = df.iloc[0]
        return r["line_id"], r["line_code"], False

    line_code = _generate_line_code(cx)
    row = cx.execute(
        text(
            """
            INSERT INTO public.fish_lines (
              id,
              line_code,
              nickname,
              genetic_background,
              line_building_stage,
              notes,
              created_at,
              genotype_v11_id,
              construct_code,
              display_name
            )
            VALUES (
              gen_random_uuid(),
              :code,
              :nickname,
              :bg,
              NULL,
              NULL,
              now(),
              (:gid)::uuid,
              :construct_code,
              :display_name
            )
            RETURNING id::text AS line_id, line_code;
            """
        ),
        {
            "code": line_code,
            "nickname": nn,
            "bg": bg,
            "gid": genotype_v11_id,
            "construct_code": bc,
            "display_name": f"{line_code} — {nn}",
        },
    ).fetchone()

    return row._mapping["line_id"], row._mapping["line_code"], True


# ─────────────────────────────────────────────────────────
# Instances + tanks
# ─────────────────────────────────────────────────────────

def ensure_tank_for_instance(
    cx: Connection, fish_instance_id: str, fish_code: str
) -> None:
    """
    Ensure there is at least one active tank row for this fish instance.

    Canonical tank_code pattern (v11):
        {FSH}-TANK1  e.g. FSH-8d7b6637-TANK1
    """
    fish_code = (fish_code or "").strip()
    if not fish_code:
        return

    tank_code = f"{fish_code}-TANK1"

    cx.execute(
        text(
            """
            INSERT INTO public.tanks (
              id,
              tank_code,
              status,
              fish_instance_id,
              created_at
            )
            VALUES (
              gen_random_uuid(),
              :tank_code,
              'active',
              (:fid)::uuid,
              now()
            )
            ON CONFLICT (tank_code) DO NOTHING;
            """
        ),
        {"tank_code": tank_code, "fid": fish_instance_id},
    )


def _create_instances_with_genotype_and_bg(
    cx: Connection,
    *,
    line_id: str,
    line_code: str,
    genotype_v11_id: Optional[str],
    instances: List[Dict[str, Any]],
) -> Tuple[int, int]:
    """
    Create instances under the given line_id, set genotype_v11_id (or NULL),
    per-instance genetic_background + origin_kind, and create tanks.

    Returns (n_instances, n_tanks).
    """
    n_instances = 0
    n_tanks = 0

    for idx, inst in enumerate(instances, start=1):
        code = _norm(inst.get("fish_code"))
        stage = _norm(inst.get("instance_stage"))
        notes = _norm(inst.get("notes"))
        birthday = _coerce_date(inst.get("birthday"))
        bg_code = _norm(inst.get("genetic_background"))
        origin_kind = _norm(inst.get("origin_kind"))

        if birthday is None:
            raise ValueError("Birthday is required for each instance.")
        if not bg_code:
            raise ValueError("Genetic background (bg_code) is required for each instance.")

        if not code:
            code = f"FSH-{uuid.uuid4().hex[:8]}"

        suffix = f"{idx:03d}"
        prefix = stage or "inst"
        line_instance_code = f"{line_code}-{prefix}-{suffix}"

        row = cx.execute(
            text(
                """
                INSERT INTO public.fish_instances_v10 (
                  id,
                  line_id,
                  fish_code,
                  line_instance_code,
                  birthday,
                  instance_stage,
                  notes,
                  genotype_v11_id,
                  genetic_background,
                  origin_kind,
                  created_at
                )
                VALUES (
                  gen_random_uuid(),
                  (:line_id)::uuid,
                  :fish_code,
                  :line_instance_code,
                  :birthday,
                  :instance_stage,
                  :notes,
                  :genotype_v11_id,
                  :bg,
                  :origin_kind,
                  now()
                )
                RETURNING id::text AS fish_instance_id;
                """
            ),
            {
                "line_id": line_id,
                "fish_code": code,
                "line_instance_code": line_instance_code,
                "birthday": birthday,
                "instance_stage": stage,
                "notes": notes,
                "genotype_v11_id": genotype_v11_id,
                "bg": bg_code,
                "origin_kind": origin_kind,
            },
        ).fetchone()

        fish_instance_id = row._mapping["fish_instance_id"]
        n_instances += 1

        ensure_tank_for_instance(cx, fish_instance_id, code)
        n_tanks += 1

    return n_instances, n_tanks