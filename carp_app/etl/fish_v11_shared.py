from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


def _norm(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None


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


def load_construct_ids(engine: Engine) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          id::text AS construct_id,
          construct_code
        FROM public.constructs;
        """
    )
    with engine.begin() as cx:
        return pd.read_sql(sql, cx)


def ensure_allele_new_or_existing(
    cx,
    *,
    transgene_base_code: str,
    mode: str,
    existing_allele_number: Optional[int],
    new_allele_nickname: Optional[str],
) -> Tuple[str, int]:
    base = _norm(transgene_base_code)
    if not base:
        raise ValueError("transgene_base_code is required for each allele.")

    if mode == "Reuse existing allele":
        if existing_allele_number is None:
            raise ValueError(f"{base}: no existing allele_number selected.")
        row = pd.read_sql(
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
        if row.empty:
            raise ValueError(
                f"{base}: existing allele_number {existing_allele_number} not found."
            )
        return base, int(existing_allele_number)

    if mode != "Create new allele":
        raise ValueError(f"{base}: unknown allele mode '{mode}'")

    nick = _norm(new_allele_nickname)
    if not nick:
        raise ValueError(f"{base}: new allele_nickname is required to create an allele.")

    row = pd.read_sql(
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
    if not row.empty:
        return base, int(row.iloc[0]["allele_number"])

    seq_res = cx.execute(
        text("SELECT nextval('public.transgene_alleles_allele_number_seq') AS n;")
    )
    allele_number = int(seq_res.scalar())
    allele_name = f"gu{allele_number}"

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

    return base, allele_number


def _generate_line_code(cx) -> str:
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


def ensure_group_and_genotype_for_alleles(
    cx,
    *,
    resolved_alleles: List[Dict[str, Any]],
    constructs_ids_df: pd.DataFrame,
) -> Tuple[str, str, str]:
    if not resolved_alleles:
        raise ValueError("No alleles to build genotype / fish_group.")

    code_to_id = {
        r["construct_code"]: r["construct_id"]
        for _, r in constructs_ids_df.iterrows()
    }

    pairs: List[Tuple[str, int]] = []
    for a in resolved_alleles:
        base = a["transgene_base_code"]
        num = int(a["allele_number"])
        if base not in code_to_id:
            raise ValueError(f"Construct code {base} not found in public.constructs.")
        pairs.append((base, num))

    pairs_sorted = sorted(pairs)
    target_set = set(pairs_sorted)

    df = pd.read_sql(
        text(
            """
            SELECT
              fg.id::text        AS fish_group_id,
              fg.genotype_key    AS genotype_key,
              g.id::text         AS genotype_v11_id,
              c.construct_code   AS construct_code,
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
                (str(sub_row["construct_code"]), int(sub_row["allele_number"]))
                for _, sub_row in sub.iterrows()
            )
            if existing_pairs == target_set:
                return fg_id, g_id, gkey

    base_parts = [f"{code}:{num}" for code, num in pairs_sorted]
    genotype_basecodes = " + ".join(base_parts)
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
              'fish_v11_loaded'
            )
            RETURNING id::text AS genotype_v11_id, genotype_code;
            """
        ),
        {
            "gcode": genotype_code,
            "gpretty": genotype_pretty,
            "gbasecodes": genotype_basecodes,
        },
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
        construct_id = code_to_id[base]
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


def ensure_line_for_group(
    cx,
    *,
    fish_group_id: str,
    nickname: str,
    primary_base_code: str,
    default_bg_code: Optional[str],
) -> Tuple[str, str, bool]:
    nn = _norm(nickname)
    bc = _norm(primary_base_code)

    if not nn:
        raise ValueError("Line nickname is required.")
    if not bc:
        raise ValueError("Primary construct base_code is required.")
    if not fish_group_id:
        raise ValueError("fish_group_id is required.")

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

    line_code = _generate_line_code(cx)

    line_row = cx.execute(
        text(
            """
            INSERT INTO public.fish_lines (
              line_code,
              nickname,
              genetic_background,
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


def create_instances_with_genotype_and_bg(
    cx,
    *,
    line_id: str,
    line_code: str,
    genotype_v11_id: str,
    instances: List[Dict[str, Any]],
) -> Tuple[int, int]:
    """
    Insert fish_instances_v10 rows with instance-stage + instance-level background,
    and create tanks. Idempotent: if fish_code already exists, skip that instance.
    Returns (n_instances_inserted, n_tanks_inserted).
    """
    n_instances = 0
    n_tanks = 0

    for idx, inst in enumerate(instances, start=1):
        code = _norm(inst.get("fish_code"))
        stage = _norm(inst.get("instance_stage"))
        notes = _norm(inst.get("notes"))
        birthday = _coerce_date(inst.get("birthday"))
        bg_code = _norm(inst.get("genetic_background"))

        if birthday is None:
            raise ValueError("Birthday is required for each instance.")
        if not bg_code:
            raise ValueError("Genetic background (bg_code) is required for each instance.")

        if not code:
            suffix = f"{idx:03d}"
            prefix = stage or "FSH"
            code = f"{line_code}-{prefix}-{suffix}"

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
                ON CONFLICT (fish_code) DO NOTHING
                RETURNING id::text AS fish_instance_id;
                """
            ),
            {
                "line_id": line_id,
                "fish_code": code,
                "line_instance_code": code,
                "birthday": birthday,
                "instance_stage": stage,
                "notes": notes,
                "genotype_id": genotype_v11_id,
                "bg": bg_code,
            },
        ).fetchone()

        if not ins:
            continue

        fish_id = ins._mapping["fish_instance_id"]
        n_instances += 1

        tank_code = f"{code}-T1"
        cx.execute(
            text(
                """
                INSERT INTO public.tanks (
                  fish_instance_id,
                  tank_code,
                  status,
                  created_at
                )
                VALUES (
                  :fid,
                  :tank_code,
                  'active',
                  now()
                )
                ON CONFLICT DO NOTHING;
                """
            ),
            {"fid": fish_id, "tank_code": tank_code},
        )
        n_tanks += 1

    return n_instances, n_tanks
