from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection
from .fish_v11_kinds import classify_instance_construct_kind

from .fish_v11_core import (
    _norm,
    _coerce_date,
    load_construct_ids,
    ensure_allele_new_or_existing,
    ensure_group_and_genotype_for_alleles,
    ensure_line_for_description,
    ensure_line_alleles_for_line,
    ensure_tank_for_instance,
    ensure_injection_treatment_single_base,
    link_instances_to_treatment,
)

# ─────────────────────────────────────────────────────────
# Small helpers
# ─────────────────────────────────────────────────────────

REQUIRED_COLS = {
    "line_nickname",
    "birthday",
    "genetic_background",
    "instance_stage",
    "treatment_basecode",
}

def _norm_bg(raw: Any | None) -> str:
    """
    Normalize a genetic_background value for matching against bg_code.

    - Treat None/NA as empty string.
    - Replace NBSP with a normal space.
    - Strip leading/trailing whitespace.
    - Lowercase.
    - Remove ALL internal whitespace.
    - Normalize spaces around '/'.

    Examples:
      'Piglet24b'      -> 'piglet24b'
      'Piglet14a\xa0'  -> 'piglet14a'
      'pIGLET14a'      -> 'piglet14a'
      'Casper/ AB'     -> 'casper/ab'
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ""

    s = str(raw).replace("\xa0", " ").strip().lower()
    if not s:
        return ""

    # Remove all whitespace
    s = re.sub(r"\s+", "", s)

    # Normalize spaces around '/'
    s = s.replace(" /", "/").replace("/ ", "/")

    return s

def _norm(s: object | None) -> str:
    if s is None:
        return ""
    text_val = str(s).strip()
    if text_val in {"", "NA", "<NA>"}:
        return ""
    return text_val


def _ensure_known_construct_basecodes(cx: Connection, basecodes: set[str]) -> None:
    """
    Ensure all construct basecodes exist in public.constructs.

    Raises ValueError listing any missing codes.
    """
    basecodes = {_norm(bc) for bc in basecodes if _norm(bc)}
    if not basecodes:
        return

    rows = cx.execute(
        text(
            """
            SELECT construct_code
            FROM public.constructs
            WHERE construct_code = ANY(:codes)
            """
        ),
        {"codes": list(basecodes)},
    ).scalars().all()

    known = set(rows)
    missing = sorted(basecodes - known)
    if missing:
        msg = (
            "Unknown construct basecodes in treatments "
            "(no matching rows in public.constructs): "
            + ", ".join(missing)
            + ". Add these constructs to the constructs CSV/metadata and "
            + "reload constructs before importing treatments."
        )
        raise ValueError(msg)

def _normalize_base_code(raw: Any) -> Optional[str]:
    """
    Normalize a construct / treatment base_code into canonical base_code.

      'pDQM005'  -> 'pdqm-5'
      'PDQM034'  -> 'pdqm-34'
      'MGCO-35'  -> 'mgco-35'
      'mgco-35'  -> 'mgco-35'
    """
    s = _norm(str(raw) if raw is not None else None)
    if not s:
        return None

    # Treat 'nan' / 'na' / '<na>' as missing, not as a basecode
    if s.lower() in {"nan", "na", "<na>"}:
        return None

    s = s.replace(" ", "")
    m = re.match(r"^([A-Za-z]+)[-_]?0*([0-9]+)$", s)
    if not m:
        return s.lower()
    prefix = m.group(1).lower()
    num = int(m.group(2))
    return f"{prefix}-{num}"


def _parse_base_list(raw: Any) -> List[str]:
    """Split on commas and normalize each basecode."""
    s = str(raw) if raw is not None else ""
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return [b for b in (_normalize_base_code(p) for p in parts) if b]


def _parse_allele_list(raw: Any) -> List[str]:
    """Split on commas and normalize allele nicknames."""
    s = str(raw) if raw is not None else ""
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return [_norm(p) for p in parts if _norm(p)]


def _insert_instances_for_group(
    cx: Connection,
    *,
    line_id: str,
    line_code: str,
    genotype_v11_id: Optional[str],
    bg_code: str,
    origin_kind: str,
    group_rows: pd.DataFrame,
) -> Tuple[int, int, List[str]]:
    """
    Insert instances for one logical group and return (n_instances, n_tanks_created, fish_instance_ids).

    Tank creation is now handled by explicit workflows (e.g. add clutch to nursery),
    so this loader only creates fish_instances_v10 rows. n_tanks_created is always 0.
    """
    n_instances = 0
    n_tanks = 0
    fish_ids: List[str] = []

    for idx, (_, r) in enumerate(group_rows.iterrows(), start=1):
        code = _norm(r.get("fish_nickname"))
        stage = _norm(r.get("instance_stage"))
        notes = _norm(r.get("description")) or _norm(r.get("notes"))
        birthday = _coerce_date(r.get("birthday"))
        bg = _norm(r.get("genetic_background")) or bg_code

        if birthday is None:
            raise ValueError("Birthday is required for each treated instance.")
        if not bg:
            raise ValueError("Genetic background (bg_code) is required for each treated instance.")

        if not code:
            code = f"FSH-{uuid.uuid4().hex[:8]}"

        suffix = f"{idx:03d}"
        prefix = stage or "treated"
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
                "bg": bg,
                "origin_kind": origin_kind,
            },
        ).fetchone()

        fid = row._mapping["fish_instance_id"]
        fish_ids.append(fid)
        n_instances += 1

        # No automatic tank creation here. Tanks are created only via explicit workflows.

    return n_instances, n_tanks, fish_ids


# ─────────────────────────────────────────────────────────
# Main loader
# ─────────────────────────────────────────────────────────

def load_treated_fish_from_csv(df_raw: pd.DataFrame, cx: Connection) -> Dict[str, Any]:
    """
    v11 loader for treated fish instances:

      • Creates / reuses injection treatments (INJ-<base>).
      • Optionally attaches genotypes / lines via transgene_basecode + allele_nickname
        (supports comma-separated lists, aligned by position).
      • Creates fish_instances_v10 + tanks.
      • Links instances to treatments via join_fish_treatments, carrying description
        and enzyme (if supplied).

    It assumes the genetics loader has already set up constructs, backgrounds, etc.
    """
    df = df_raw.copy()
    df.columns = [c.strip() for c in df.columns]

    missing = REQUIRED_COLS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in treated-fish CSV: {sorted(missing)!r}")

    for col in (
        "transgene_basecode",
        "allele_nickname",
        "zygosity",
        "created_by",
        "enzyme",
        "description",
        "fish_nickname",
        "notes",
    ):
        if col not in df.columns:
            df[col] = ""

    for col in df.columns:
        if df[col].dtype == "O":
            df[col] = df[col].astype("string")

    # ── Backgrounds: normalize + canonicalize against genetic_backgrounds ──
    bg_df = pd.read_sql(
        text("SELECT bg_code FROM public.genetic_backgrounds;"),
        cx,
    )
    # Map normalized form -> canonical bg_code
    bg_df["bg_norm"] = bg_df["bg_code"].astype("string").map(_norm_bg)
    bg_map: Dict[str, str] = {}
    for _, row in bg_df.iterrows():
        n = row["bg_norm"]
        code = row["bg_code"]
        if n and n not in bg_map:
            bg_map[n] = code

    # Normalize CSV backgrounds and check membership
    df["_bg_norm"] = df["genetic_background"].map(_norm_bg)
    bg_set = set(bg_map.keys())
    good_bg_mask = df["_bg_norm"].map(lambda v: (v or "") in bg_set)

    rejected_chunks: List[pd.DataFrame] = []

    if not good_bg_mask.all():
        bad = df.loc[~good_bg_mask].copy()
        bad["_error"] = bad.apply(
            lambda r: f"Unknown genetic_background {r.get('genetic_background')!r}; "
            "must match public.genetic_backgrounds.bg_code.",
            axis=1,
        )
        rejected_chunks.append(bad)
        df = df.loc[good_bg_mask].copy()

    if df.empty:
        rejected = (
            pd.concat(rejected_chunks, ignore_index=True)
            if rejected_chunks
            else pd.DataFrame()
        )
        return {
            "n_rows": 0,
            "n_treatments": 0,
            "n_instances_linked": 0,
            "n_instances": 0,
            "n_tanks": 0,
            "n_lines_created": 0,
            "n_lines_reused": 0,
            "rejected_rows": rejected,
        }

    # Overwrite genetic_background with canonical bg_code
    df["genetic_background"] = df["_bg_norm"].map(lambda n: bg_map.get(n, n))

    all_treat_bases: set[str] = set()
    for raw in df["treatment_basecode"]:
        for b in _parse_base_list(raw):
            all_treat_bases.add(b)
    _ensure_known_construct_basecodes(cx, all_treat_bases)

    df["_key_treat"] = df["treatment_basecode"].map(
        lambda s: ",".join(_parse_base_list(s)) or ""
    )
    df["_key_tg_base"] = df.get("transgene_basecode", "").map(
        lambda s: ",".join(_parse_base_list(s)) or ""
    )
    df["_key_allele"] = df.get("allele_nickname", "").map(_norm)
    df["_key_line"] = df["line_nickname"].map(_norm)
    df["_key_bg"] = df["_bg_norm"]
    df["_key_enzyme"] = df.get("enzyme", "").map(_norm)

    grouped = df.groupby(
        ["_key_treat", "_key_tg_base", "_key_allele", "_key_line", "_key_bg", "_key_enzyme"],
        dropna=False,
        sort=False,
    )

    constructs_ids_df = load_construct_ids(cx)

    n_rows = int(len(df))
    n_treatments_touched: set[str] = set()
    n_instances_linked = 0
    n_instances = 0
    n_tanks = 0
    n_lines_created = 0
    n_lines_reused = 0
    group_errors: List[pd.DataFrame] = []

    for (_treat_key, _tg_key, _allele_key, _line_key, _bg_key, _enz_key), g in grouped:
        head = g.iloc[0]

        try:
            line_nickname = _norm(head.get("line_nickname"))
            bg_code = _norm(head.get("genetic_background"))
            zygosity = _norm(head.get("zygosity")) or "unknown"

            treat_bases = _parse_base_list(head.get("treatment_basecode"))
            if not treat_bases:
                raise ValueError("treatment_basecode is required for treated fish.")

            tg_bases = _parse_base_list(head.get("transgene_basecode"))
            allele_nicks = _parse_allele_list(head.get("allele_nickname"))

            if tg_bases and allele_nicks and len(tg_bases) != len(allele_nicks):
                raise ValueError(
                    "transgene_basecode and allele_nickname must have the same number of comma-separated entries."
                )

            treatment_ids: List[str] = []
            for tb in treat_bases:
                tid = ensure_injection_treatment_single_base(cx, base_code=tb)
                treatment_ids.append(tid)
                n_treatments_touched.add(tb)

            resolved_alleles: List[Dict[str, Any]] = []
            genotype_v11_id: Optional[str] = None
            genotype_basecodes: Optional[str] = None

            if tg_bases:
                if not allele_nicks:
                    allele_nicks = [None] * len(tg_bases)

                for b, nick in zip(tg_bases, allele_nicks):
                    base_code, allele_number = ensure_allele_new_or_existing(
                        cx,
                        transgene_base_code=b,
                        mode="Create new allele",
                        existing_allele_number=None,
                        new_allele_nickname=nick,
                    )
                    resolved_alleles.append(
                        {
                            "transgene_base_code": base_code,
                            "allele_number": allele_number,
                        }
                    )

                genotype_v11_id, genotype_code, genotype_basecodes = (
                    ensure_group_and_genotype_for_alleles(
                        cx,
                        resolved_alleles=resolved_alleles,
                        constructs_ids_df=constructs_ids_df,
                    )
                )

                primary_base = tg_bases[0]
                line_id, line_code, created_new_line = ensure_line_for_description(
                    cx,
                    genotype_v11_id=genotype_v11_id,
                    nickname=line_nickname
                    or (genotype_code or genotype_basecodes or "treated_line"),
                    primary_base_code=primary_base,
                    default_bg_code=bg_code,
                )

                ensure_line_alleles_for_line(
                    cx,
                    line_id=line_id,
                    resolved_alleles=resolved_alleles,
                    constructs_ids_df=constructs_ids_df,
                    default_zygosity=zygosity,
                )

                origin_kind = classify_instance_construct_kind(
                    has_genotype_constructs=True,
                    has_treatment_constructs=True,
                )

            else:
                nn = line_nickname or (bg_code or "treated_background")
                line_row = pd.read_sql(
                    text(
                        """
                        SELECT id::text AS line_id, line_code::text AS line_code
                        FROM public.fish_lines
                        WHERE genotype_v11_id IS NULL
                          AND construct_code IS NULL
                          AND nickname = :nn
                          AND genetic_background = :bg
                        ORDER BY created_at ASC
                        LIMIT 1;
                        """
                    ),
                    cx,
                    params={"nn": nn, "bg": bg_code},
                )

                if not line_row.empty:
                    r0 = line_row.iloc[0]
                    line_id = r0["line_id"]
                    line_code = r0["line_code"]
                    created_new_line = False
                else:
                    line_code = f"LINE-{uuid.uuid4().hex[:8]}"
                    row_line = cx.execute(
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
                              NULL,
                              NULL,
                              :display_name
                            )
                            RETURNING id::text AS line_id, line_code;
                            """
                        ),
                        {
                            "code": line_code,
                            "nickname": nn,
                            "bg": bg_code,
                            "display_name": f"{line_code} — {nn}",
                        },
                    ).fetchone()
                    line_id = row_line._mapping["line_id"]
                    line_code = row_line._mapping["line_code"]
                    created_new_line = True

                genotype_v11_id = None
                genotype_basecodes = None
                origin_kind = classify_instance_construct_kind(
                    has_genotype_constructs=False,
                    has_treatment_constructs=True,
                )

            n_i, n_t, fish_ids = _insert_instances_for_group(
                cx,
                line_id=line_id,
                line_code=line_code,
                genotype_v11_id=genotype_v11_id,
                bg_code=bg_code,
                origin_kind=origin_kind,
                group_rows=g,
            )
            n_instances += n_i
            n_tanks += n_t

            desc = _norm(head.get("description"))
            enzyme_val = _norm(head.get("enzyme"))
            note_parts: List[str] = []
            if desc:
                note_parts.append(desc)
            if enzyme_val:
                note_parts.append(f"enzyme={enzyme_val}")
            link_note = " | ".join(note_parts) if note_parts else None

            for tid in treatment_ids:
                link_instances_to_treatment(
                    cx,
                    fish_instance_ids=fish_ids,
                    treatment_id=tid,
                    note=link_note,
                    enzyme=enzyme_val,
                )
                n_instances_linked += len(fish_ids)

        except Exception as e:
            g_err = g.copy()
            g_err["_error"] = str(e)
            group_errors.append(g_err)
            continue

    if rejected_chunks or group_errors:
        rejected_all: List[pd.DataFrame] = []
        rejected_all.extend(rejected_chunks)
        rejected_all.extend(group_errors)
        rejected_df = pd.concat(rejected_all, ignore_index=True)
    else:
        rejected_df = pd.DataFrame()

    return {
        "n_rows": n_rows,
        "n_treatments": len(n_treatments_touched),
        "n_instances_linked": n_instances_linked,
        "n_instances": n_instances,
        "n_tanks": n_tanks,
        "n_lines_created": n_lines_created,
        "n_lines_reused": n_lines_reused,
        "rejected_rows": rejected_df,
    }