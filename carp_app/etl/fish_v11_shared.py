from __future__ import annotations

import uuid
import re
import math
from datetime import date, datetime
from typing import Any, Dict, List, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection


# ───────── basic helpers ─────────


def _norm(s: Any | None) -> str | None:
    """
    Normalize a value to a clean string or None.

    Treats pandas NaN / None-like sentinels ('nan', 'NaN', 'None', 'null', '')
    as None so that background-only rows with empty base/allele really look
    empty to the rest of the loader.
    """
    if s is None:
        return None

    if isinstance(s, float) and math.isnan(s):
        return None

    s = str(s).strip()
    if not s:
        return None

    if s.lower() in {"nan", "none", "null", "na", "n/a"}:
        return None

    return s


def _coerce_date(value: Any) -> date | None:
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


# ───────── lookup helpers ─────────


def load_construct_ids(cx: Connection) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          id::text AS construct_id,
          construct_code
        FROM public.constructs;
        """
    )
    return pd.read_sql(sql, cx)


def _lookup_canonical_base(cx: Connection, base_raw: str) -> str | None:
    """
    Given something like 'pDQM005' or 'PDQM005', try to resolve it to a canonical
    base_code in public.constructs (e.g. 'pdqm-5').
    """

    def _query(bc: str) -> str | None:
        row = pd.read_sql(
            text(
                """
                SELECT
                  COALESCE(base_code, construct_code) AS base_code
                FROM public.constructs
                WHERE base_code = :bc
                   OR construct_code = :bc
                   OR base_code ILIKE :bc_ilike
                   OR construct_code ILIKE :bc_ilike
                ORDER BY base_code
                LIMIT 1;
                """
            ),
            cx,
            params={"bc": bc, "bc_ilike": bc},
        )
        if row.empty:
            return None
        return str(row.iloc[0]["base_code"]).strip()

    # 1) try raw string
    bc = _query(base_raw)
    if bc is not None:
        return bc

    # 2) try letters+digits pattern, e.g. pDQM005 -> pdqm-5
    m = re.match(r"^([A-Za-z]+)[-_]?0*([0-9]+)$", base_raw.strip())
    if m:
        letters = m.group(1).lower()
        num = int(m.group(2))
        candidate = f"{letters}-{num}"
        bc = _query(candidate)
        if bc is not None:
            return bc

    return None


# ───────── allele / genotype / line helpers ─────────


def _ensure_allele_new_or_existing(
    cx: Connection,
    *,
    transgene_base_code: str,
    mode: str,
    existing_allele_number: int | None,
    new_allele_nickname: str | None,
) -> Tuple[str, int, str]:
    """
    Ensure a row exists in public.transgene_alleles and return
    (canonical_base_code, allele_number, human_label).

    Behavior:
      - Normalize legacy base codes like 'pDQM005' → 'pdqm-5'.
      - Enforce that the final base code exists in public.constructs.
    """
    base_raw = _norm(transgene_base_code)
    if not base_raw:
        raise ValueError("transgene_base_code is required for each allele.")

    base = _lookup_canonical_base(cx, base_raw)
    if base is None:
        raise ValueError(
            f"{base_raw}: base code not found in public.constructs. "
            "Fix the CSV (use a known base_code/alias) or load constructs first."
        )

    # reuse existing allele by number
    if mode == "Reuse existing allele":
        if existing_allele_number is None:
            raise ValueError(f"{base}: no existing allele_number provided to reuse.")
        row = pd.read_sql(
            text(
                """
                SELECT allele_number, COALESCE(allele_nickname,'') AS allele_nickname
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
        r = row.iloc[0]
        label = f"{base} #{int(r['allele_number'])}"
        if r["allele_nickname"]:
            label += f" ({r['allele_nickname']})"
        return base, int(r["allele_number"]), label

    # create new allele by nickname
    if mode != "Create new allele":
        raise ValueError(f"{base}: unknown allele mode '{mode}'")

    nick = _norm(new_allele_nickname)
    if not nick:
        raise ValueError(f"{base}: new allele_nickname is required to create an allele.")

    row = pd.read_sql(
        text(
            """
            SELECT allele_number, COALESCE(allele_nickname,'') AS allele_nickname
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
        r = row.iloc[0]
        label = f"{base} #{int(r['allele_number'])}"
        if r["allele_nickname"]:
            label += f" ({r['allele_nickname']})"
        return base, int(r["allele_number"]), label

    # create new allele
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

    label = f"{base} #{allele_number} ({nick})"
    return base, allele_number, label


def _ensure_genotype_for_alleles(
    cx: Connection,
    *,
    resolved_alleles: List[Dict[str, Any]],
    constructs_ids_df: pd.DataFrame,
) -> Tuple[str, str]:
    """
    Given resolved alleles, ensure a genotype_v11 exists, or create one.

    Returns (genotype_v11_id, genotype_code).

    Canonicalization uses genotype_basecodes as the key, and join_genotype_constructs_v11
    as the normalized composition table.
    """
    if not resolved_alleles:
        raise ValueError("No alleles to build genotype.")

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
    base_parts = [f"{code}:{num}" for code, num in pairs_sorted]
    genotype_basecodes = " + ".join(base_parts)

    # try reuse by basecodes
    row = pd.read_sql(
        text(
            """
            SELECT id::text AS genotype_v11_id, genotype_code
            FROM public.genotypes_v11
            WHERE genotype_basecodes = :gbase
            LIMIT 1;
            """
        ),
        cx,
        params={"gbase": genotype_basecodes},
    )
    if not row.empty:
        r = row.iloc[0]
        return r["genotype_v11_id"], r["genotype_code"]

    # create new genotype
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
              'fish_v11_shared'
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

    # populate join_genotype_constructs_v11
    for base, _num in pairs_sorted:
        construct_id = code_to_id[base]
        cx.execute(
            text(
                """
                INSERT INTO public.join_genotype_constructs_v11 (
                  genotype_id,
                  construct_id,
                  created_at
                )
                VALUES (
                  :gid,
                  :cid,
                  now()
                )
                ON CONFLICT DO NOTHING;
                """
            ),
            {"gid": genotype_v11_id, "cid": construct_id},
        )

    return genotype_v11_id, genotype_code


def _generate_line_code(cx: Connection) -> str:
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


def _ensure_line_for_description(
    cx: Connection,
    *,
    genotype_v11_id: str,
    nickname: str,
    primary_base_code: str,
    default_bg_code: str | None,
) -> Tuple[str, str, bool]:
    """
    Ensure a line exists for (genotype, nickname, primary_base_code, background).

    Returns (line_id, line_code, created_new_line).
    """
    nn = _norm(nickname)
    bc = _norm(primary_base_code)

    if not nn:
        raise ValueError("Line nickname is required.")
    if not bc:
        raise ValueError("Primary construct base_code is required to define the line.")
    if not genotype_v11_id:
        raise ValueError("genotype_v11_id is required to create a line.")

    existing = pd.read_sql(
        text(
            """
            SELECT id::text AS line_id, line_code::text AS line_code
            FROM public.fish_lines
            WHERE nickname = :nn
              AND construct_code = :bc
              AND genotype_v11_id = :gid
              AND genetic_background IS NOT DISTINCT FROM :bg
            ORDER BY created_at ASC
            LIMIT 1;
            """
        ),
        cx,
        params={"nn": nn, "bc": bc, "gid": genotype_v11_id, "bg": default_bg_code},
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
              line_building_stage,
              notes,
              created_at,
              fish_group_id,
              group_instance_code,
              construct_code,
              genotype_v11_id
            )
            VALUES (
              :code,
              :nickname,
              :bg,
              NULL,
              NULL,
              now(),
              NULL,
              NULL,
              :construct_code,
              :gid
            )
            RETURNING id::text AS line_id, line_code;
            """
        ),
        {
            "code": line_code,
            "nickname": nn,
            "bg": default_bg_code,
            "construct_code": bc,
            "gid": genotype_v11_id,
        },
    ).fetchone()

    return line_row._mapping["line_id"], line_row._mapping["line_code"], True


def _create_instances_with_genotype_and_bg(
    cx: Connection,
    *,
    line_id: str,
    line_code: str,
    genotype_v11_id: str | None,
    instances: List[Dict[str, Any]],
) -> Tuple[int, int]:
    """
    Create instances under the given line_id, set genotype_v11_id (which may be NULL),
    genetic_background, and create tanks. Returns (n_instances, n_tanks).

    fish_code is auto-generated if not provided.
    """
    n_instances = 0
    n_tanks = 0

    for idx, inst in enumerate(instances, start=1):
        provided_fish_code = _norm(inst.get("fish_code"))
        stage = _norm(inst.get("instance_stage"))
        notes = _norm(inst.get("notes"))
        birthday = _coerce_date(inst.get("birthday"))
        bg_code = _norm(inst.get("genetic_background"))

        if birthday is None:
            raise ValueError("Birthday is required for each instance.")
        if not bg_code:
            raise ValueError("Genetic background (bg_code) is required for each instance.")

        fish_code = provided_fish_code or f"FSH-{uuid.uuid4().hex[:8]}"

        suffix = f"{idx:03d}"
        prefix = stage or "inst"
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
                ON CONFLICT (fish_code) DO NOTHING
                RETURNING id::text AS fish_instance_id;
                """
            ),
            {
                "line_id": line_id,
                "fish_code": fish_code,
                "line_instance_code": line_instance_code,
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

        # simple tanks: one tank per instance, tank_code = FSH-xxxxxx-TANK1
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
                  CAST(:fid AS uuid),
                  now()
                )
                ON CONFLICT DO NOTHING;
                """
            ),
            {"tank_code": tank_code, "fid": fish_id},
        )
        n_tanks += 1

    return n_instances, n_tanks


# ───────── instance-row preparation ─────────


def _prepare_instance_rows(g: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Turn grouped CSV rows into normalized instance dicts with:
      - instance_stage
      - birthday
      - genetic_background
      - notes (fish_nickname and/or notes merged)
    """
    rows: List[Dict[str, Any]] = []
    for _, r in g.iterrows():
        fish_nickname = _norm(r.get("fish_nickname"))
        base_note = _norm(r.get("notes"))
        if fish_nickname and base_note:
            notes = f"{fish_nickname}: {base_note}"
        elif fish_nickname:
            notes = fish_nickname
        else:
            notes = base_note

        rows.append(
            {
                "fish_code": None,
                "instance_stage": _norm(r.get("instance_stage")),
                "birthday": r.get("birthday"),
                "genetic_background": _norm(r.get("genetic_background")),
                "notes": notes,
            }
        )
    return rows


# ───────── canonical CSV loader ─────────


def load_fish_from_csv(df_csv: pd.DataFrame, cx: Connection) -> Dict[str, Any]:
    """
    Canonical v11 fish CSV loader.

    Behavior:
      • If transgene_base_code AND allele_nickname are both present:
          -> treat as genotyped line (true allele)
      • If both empty:
          -> treat as background-only line (no genotype)
      • If base present, allele empty, and stage ~ 'inject':
          -> treat as background-only with injection annotation
      • Otherwise:
          -> reject group as invalid.

    fish_code is always auto-generated.
    """

    # 1) CSV contract
    required_cols = [
        "line_nickname",
        "instance_stage",
        "birthday",
        "genetic_background",
    ]
    missing = [c for c in required_cols if c not in df_csv.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {', '.join(missing)}")

    has_base = "transgene_base_code" in df_csv.columns
    has_allele = "allele_nickname" in df_csv.columns

    constructs_ids_df = load_construct_ids(cx)

    # backgrounds
    bg_df = pd.read_sql(
        text("SELECT bg_code FROM public.genetic_backgrounds;"),
        cx,
    )
    valid_bg = {str(b).strip() for b in bg_df["bg_code"].tolist()}

    n_total_instances = 0
    n_total_tanks = 0
    n_lines_created = 0
    n_lines_reused = 0
    rejected_groups: List[pd.DataFrame] = []

    # group keys
    group_cols = []
    if has_base:
        group_cols.append("transgene_base_code")
    else:
        df_csv["__transgene_base_code__"] = None
        group_cols.append("__transgene_base_code__")

    group_cols.append("line_nickname")

    if has_allele:
        group_cols.append("allele_nickname")
    else:
        df_csv["__allele_nickname__"] = None
        group_cols.append("__allele_nickname__")

    # 2) group + dispatch
    for group_vals, g in df_csv.groupby(group_cols, dropna=False):
        if has_base and has_allele:
            base_raw, line_nickname_raw, allele_nick_raw = group_vals
        elif has_base and not has_allele:
            base_raw, line_nickname_raw, _dummy = group_vals
            allele_nick_raw = None
        elif not has_base and has_allele:
            _dummy, line_nickname_raw, allele_nick_raw = group_vals
            base_raw = None
        else:
            _dummy1, line_nickname_raw, _dummy2 = group_vals
            base_raw = None
            allele_nick_raw = None

        try:
            base = _norm(base_raw)
            line_nickname = _norm(line_nickname_raw)
            allele_nick = _norm(allele_nick_raw)

            instance_rows = _prepare_instance_rows(g)
            if not instance_rows:
                continue

            default_bg_for_line = instance_rows[0]["genetic_background"]
            inst_stage0 = instance_rows[0]["instance_stage"]

            # basic validation
            if not line_nickname:
                raise ValueError("line_nickname is required.")
            if not default_bg_for_line:
                raise ValueError(
                    f"{line_nickname}: genetic_background is required for instances."
                )
            if default_bg_for_line not in valid_bg:
                raise ValueError(
                    f"{line_nickname}: genetic_background '{default_bg_for_line}' "
                    "is not present in public.genetic_backgrounds."
                )

            # ───────── background-only path ─────────
            if not base and not allele_nick:
                existing = pd.read_sql(
                    text(
                        """
                        SELECT id::text AS line_id, line_code::text AS line_code
                        FROM public.fish_lines
                        WHERE fish_group_id IS NULL
                          AND construct_code IS NULL
                          AND nickname = :nn
                          AND genetic_background = :bg
                        ORDER BY created_at ASC
                        LIMIT 1;
                        """
                    ),
                    cx,
                    params={"nn": line_nickname, "bg": default_bg_for_line},
                )

                if not existing.empty:
                    r0 = existing.iloc[0]
                    line_id = r0["line_id"]
                    line_code = r0["line_code"]
                    created_new_line = False
                else:
                    line_code = _generate_line_code(cx)
                    row_ins = cx.execute(
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
                              construct_code,
                              genotype_v11_id
                            )
                            VALUES (
                              :code,
                              :nickname,
                              :bg,
                              NULL,
                              NULL,
                              now(),
                              NULL,
                              NULL,
                              NULL,
                              NULL
                            )
                            RETURNING id::text AS line_id, line_code;
                            """
                        ),
                        {
                            "code": line_code,
                            "nickname": line_nickname,
                            "bg": default_bg_for_line,
                        },
                    ).fetchone()
                    line_id = row_ins._mapping["line_id"]
                    line_code = row_ins._mapping["line_code"]
                    created_new_line = True

                if created_new_line:
                    n_lines_created += 1
                else:
                    n_lines_reused += 1

                n_instances, n_tanks = _create_instances_with_genotype_and_bg(
                    cx,
                    line_id=line_id,
                    line_code=line_code,
                    genotype_v11_id=None,
                    instances=instance_rows,
                )

                n_total_instances += n_instances
                n_total_tanks += n_tanks
                continue

            # ───────── injection-as-background-only path ─────────
            if base and not allele_nick:
                is_injection = bool(inst_stage0 and "inject" in inst_stage0.lower())
                if is_injection:
                    injection_tag = f"INJECTION:{base}"
                    for inst in instance_rows:
                        if inst.get("notes"):
                            inst["notes"] = f"{injection_tag} — {inst['notes']}"
                        else:
                            inst["notes"] = injection_tag

                    existing = pd.read_sql(
                        text(
                            """
                            SELECT id::text AS line_id, line_code::text AS line_code
                            FROM public.fish_lines
                            WHERE fish_group_id IS NULL
                              AND construct_code IS NULL
                              AND nickname = :nn
                              AND genetic_background = :bg
                            ORDER BY created_at ASC
                            LIMIT 1;
                            """
                        ),
                        cx,
                        params={"nn": line_nickname, "bg": default_bg_for_line},
                    )

                    if not existing.empty:
                        r0 = existing.iloc[0]
                        line_id = r0["line_id"]
                        line_code = r0["line_code"]
                        created_new_line = False
                    else:
                        line_code = _generate_line_code(cx)
                        row_ins = cx.execute(
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
                                  construct_code,
                                  genotype_v11_id
                                )
                                VALUES (
                                  :code,
                                  :nickname,
                                  :bg,
                                  NULL,
                                  NULL,
                                  now(),
                                  NULL,
                                  NULL,
                                  NULL,
                                  NULL
                                )
                                RETURNING id::text AS line_id, line_code;
                                """
                            ),
                            {
                                "code": line_code,
                                "nickname": line_nickname,
                                "bg": default_bg_for_line,
                            },
                        ).fetchone()
                        line_id = row_ins._mapping["line_id"]
                        line_code = row_ins._mapping["line_code"]
                        created_new_line = True

                    if created_new_line:
                        n_lines_created += 1
                    else:
                        n_lines_reused += 1

                    n_instances, n_tanks = _create_instances_with_genotype_and_bg(
                        cx,
                        line_id=line_id,
                        line_code=line_code,
                        genotype_v11_id=None,
                        instances=instance_rows,
                    )

                    n_total_instances += n_instances
                    n_total_tanks += n_tanks
                    continue

            # ───────── invalid mixed group ─────────
            if (base and not allele_nick) or (allele_nick and not base):
                raise ValueError(
                    f"{base or line_nickname}: must have both transgene_base_code "
                    "and allele_nickname for genotyped lines, or leave both blank "
                    "for background-only lines."
                )

            # ───────── genotyped path ─────────
            mode = "Create new allele"
            existing_num = None
            new_nick = allele_nick

            base2, num, label = _ensure_allele_new_or_existing(
                cx,
                transgene_base_code=base,
                mode=mode,
                existing_allele_number=existing_num,
                new_allele_nickname=new_nick,
            )
            resolved_alleles = [
                {"transgene_base_code": base2, "allele_number": num, "label": label}
            ]

            genotype_v11_id, genotype_code = _ensure_genotype_for_alleles(
                cx,
                resolved_alleles=resolved_alleles,
                constructs_ids_df=constructs_ids_df,
            )

            primary_base_code = base2

            line_id, line_code, created_new_line = _ensure_line_for_description(
                cx,
                genotype_v11_id=genotype_v11_id,
                nickname=line_nickname,
                primary_base_code=primary_base_code,
                default_bg_code=default_bg_for_line,
            )

            if created_new_line:
                n_lines_created += 1
            else:
                n_lines_reused += 1

            n_instances, n_tanks = _create_instances_with_genotype_and_bg(
                cx,
                line_id=line_id,
                line_code=line_code,
                genotype_v11_id=genotype_v11_id,
                instances=instance_rows,
            )

            n_total_instances += n_instances
            n_total_tanks += n_tanks

        except Exception as e:
            g_copy = g.copy()
            g_copy["_error"] = str(e)
            rejected_groups.append(g_copy)
            continue

    if rejected_groups:
        rejected_rows = pd.concat(rejected_groups, ignore_index=True)
    else:
        rejected_rows = pd.DataFrame()

    return {
        "n_instances": n_total_instances,
        "n_tanks": n_total_tanks,
        "n_lines_created": n_lines_created,
        "n_lines_reused": n_lines_reused,
        "rejected_rows": rejected_rows,
    }
