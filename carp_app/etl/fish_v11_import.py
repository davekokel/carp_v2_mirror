from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .fish_v11_core import (
    _norm,
    _coerce_date,
    load_construct_ids,
    ensure_allele_new_or_existing,
    ensure_group_and_genotype_for_alleles,
    ensure_line_for_description,
    ensure_line_alleles_for_line,
    _create_instances_with_genotype_and_bg,
)

# Required *structural* columns — must exist in CSV
REQUIRED_COLS = {
    "transgene_base_code",
    "line_nickname",
    "allele_nickname",
    "instance_stage",
    "birthday",
    "genetic_background",
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
      'Piglet24b'           -> 'piglet24b'
      'Piglet14a\xa0'       -> 'piglet14a'
      'pIGLET 14a'          -> 'piglet14a'
      'Casper/ AB'          -> 'casper/ab'
      'casper/rnf'          -> 'casper/rnf'
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

def _ensure_known_construct_basecodes(cx: Connection, basecodes: set[str]) -> None:
    """
    Ensure all construct basecodes exist in public.constructs.

    Raises ValueError listing any missing codes.
    """
    cleaned = {_norm(bc) for bc in basecodes if _norm(bc)}
    if not cleaned:
        return

    rows = cx.execute(
        text(
            """
            SELECT construct_code
            FROM public.constructs
            WHERE construct_code = ANY(:codes)
            """
        ),
        {"codes": list(cleaned)},
    ).scalars().all()

    known = set(rows)
    missing = sorted(cleaned - known)
    if missing:
        msg = (
            "Unknown construct basecodes in fish CSV "
            "(no matching rows in public.constructs): "
            + ", ".join(missing)
            + ". Add these constructs to the constructs CSV/metadata and "
            + "reload constructs before importing fish."
        )
        raise ValueError(msg)
    

def _normalize_base_code(raw: Any) -> Optional[str]:
    """
    Normalize a transgene_base_code / plasmid code into canonical base_code.

    Examples:
      'pDQM005'   -> 'pdqm-5'
      'PDQM034'   -> 'pdqm-34'
      'MGCO-35'   -> 'mgco-35'
      'mgco-35'   -> 'mgco-35'
    """
    s = _norm(str(raw) if raw is not None else None)
    if not s:
        return None

    s = s.replace(" ", "")
    m = re.match(r"^([A-Za-z]+)[-_]?0*([0-9]+)$", s)
    if not m:
        # Already looks like a canonical base_code-ish; just lower it
        return s.lower()

    prefix = m.group(1).lower()
    num = int(m.group(2))
    return f"{prefix}-{num}"


def _classify_origin_kind(
    base_norm: Optional[str],
    allele_nick: Optional[str],
    created_new_line: bool,
) -> str:
    """
    Coarse origin classification for a grouped CSV chunk.

    For the genetics loader:

      - background_only        (no base, no allele)
      - transgenic_new_line
      - transgenic_existing_line
    """
    has_base = bool(_norm(base_norm))
    has_allele = bool(_norm(allele_nick))

    # Background-only: no explicit transgene, no allele
    if not has_base and not has_allele:
        return "background_only"

    # Genotyped transgenic: both base and allele set
    if has_base and has_allele:
        return "transgenic_new_line" if created_new_line else "transgenic_existing_line"

    # Any other combo (e.g. base only, allele only) should be rejected by caller
    raise ValueError(
        "Genetics loader requires either (base + allele_nickname) or both empty. "
        "For injections/treatments, use the separate fish_v11_treatments CSV."
    )


def load_fish_from_csv(df_raw: pd.DataFrame, cx: Connection) -> Dict[str, Any]:
    """
    Canonical v11 CSV loader for fish lines • alleles • instances.

    Genetics-only version:

      VALID STRUCTURES:
        1) transgenic: base AND allele_nickname present
        2) background-only: base empty AND allele_nickname empty

      INVALID (rejected with _error):
        - base present but allele_nickname empty  (injection/treatment → other loader)
        - allele_nickname present but base empty

    CSV contract (minimal change from fish.csv):

      REQUIRED columns:
        - transgene_base_code  (construct base code, e.g. pdqm063 / pDQM063 / MGCO-35)
        - line_nickname        (line nickname)
        - allele_nickname      (allele nickname)
        - instance_stage       (e.g. P0, F1, juvenile)
        - birthday             (YYYY-MM-DD)
        - genetic_background   (bg_code from genetic_backgrounds or alias)

      OPTIONAL columns (auto-created as empty if missing):
        - fish_nickname        (per-fish nickname; used to seed fish_code if present)
        - notes                (free text)
        - zygosity             (group-level default, e.g. 'het', 'hom', 'unknown')
        - created_by           (for provenance; currently unused)
        - description          (for provenance; currently unused)
    """
    df = df_raw.copy()

    df.columns = [c.strip() for c in df.columns]

    missing = REQUIRED_COLS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in CSV: {sorted(missing)!r}")

    for col in ("fish_nickname", "notes", "zygosity", "created_by", "description"):
        if col not in df.columns:
            df[col] = ""

    for col in [
        "transgene_base_code",
        "line_nickname",
        "allele_nickname",
        "fish_nickname",
        "instance_stage",
        "genetic_background",
        "notes",
        "zygosity",
        "created_by",
        "description",
    ]:
        if col in df.columns:
            df[col] = df[col].astype("string")

    df["norm_base_code"] = df["transgene_base_code"].map(_normalize_base_code)

    # ── Backgrounds: normalize + canonicalize against genetic_backgrounds ──
    bg_df = pd.read_sql(
        text("SELECT bg_code FROM public.genetic_backgrounds;"),
        cx,
    )
    # Build mapping from normalized form -> canonical bg_code
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
        bad_bg = df.loc[~good_bg_mask].copy()
        bad_bg["_error"] = bad_bg.apply(
            lambda r: f"Unknown genetic_background {r.get('genetic_background')!r}; "
            "must match public.genetic_backgrounds.bg_code.",
            axis=1,
        )
        rejected_chunks.append(bad_bg)
        df = df.loc[good_bg_mask].copy()

    if df.empty:
        rejected = (
            pd.concat(rejected_chunks, ignore_index=True)
            if rejected_chunks
            else pd.DataFrame()
        )
        return {
            "n_instances": 0,
            "n_tanks": 0,
            "n_lines_created": 0,
            "n_lines_reused": 0,
            "rejected_rows": rejected,
        }

    # Overwrite genetic_background with canonical bg_code
    df["genetic_background"] = df["_bg_norm"].map(lambda n: bg_map.get(n, n))

    # Enforce: all normalized basecodes must exist in public.constructs
    all_bases: set[str] = {
        _norm(bc) for bc in df["norm_base_code"].tolist() if _norm(bc)
    }
    _ensure_known_construct_basecodes(cx, all_bases)

    df["_key_base"] = df["norm_base_code"].map(_norm)
    df["_key_allele"] = df["allele_nickname"].map(_norm)
    df["_key_line"] = df["line_nickname"].map(_norm)
    df["_key_bg"] = df["genetic_background"].map(_norm)

    constructs_ids_df = load_construct_ids(cx)

    n_total_instances = 0
    n_total_tanks = 0
    n_lines_created = 0
    n_lines_reused = 0
    group_errors: List[pd.DataFrame] = []

    grouped = df.groupby(
        ["_key_base", "_key_allele", "_key_line", "_key_bg"],
        dropna=False,
        sort=False,
    )

    for (_base, _allele, _line, _bg), g in grouped:
        head = g.iloc[0]
        base_norm = _norm(head.get("norm_base_code"))
        allele_nick = _norm(head.get("allele_nickname"))
        line_nickname = _norm(head.get("line_nickname"))
        bg_code = _norm(head.get("genetic_background"))

        try:
            resolved_alleles: List[Dict[str, Any]] = []
            genotype_v11_id: Optional[str] = None
            genotype_basecodes: Optional[str] = None

            has_base = bool(base_norm)
            has_allele = bool(allele_nick)

            line_building_stages = {"P0", "STABLE", "FOUNDER"}
            group_has_line_building = False
            if "instance_stage" in g.columns:
                group_has_line_building = any(
                    (_norm(s).upper() in line_building_stages)
                    for s in g["instance_stage"]
                )

            if has_base and has_allele:
                base_code, allele_number = ensure_allele_new_or_existing(
                    cx,
                    transgene_base_code=base_norm,
                    mode="Create new allele",
                    existing_allele_number=None,
                    new_allele_nickname=allele_nick,
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

                line_id, line_code, created_new_line = ensure_line_for_description(
                    cx,
                    genotype_v11_id=genotype_v11_id,
                    nickname=line_nickname
                    or (genotype_code or genotype_basecodes or "line"),
                    primary_base_code=base_norm or "",
                    default_bg_code=bg_code,
                )

                group_zygosity = _norm(head.get("zygosity")) or "unknown"
                ensure_line_alleles_for_line(
                    cx,
                    line_id=line_id,
                    resolved_alleles=resolved_alleles,
                    constructs_ids_df=constructs_ids_df,
                    default_zygosity=group_zygosity,
                )

                origin_kind = _classify_origin_kind(
                    base_norm=base_norm,
                    allele_nick=allele_nick,
                    created_new_line=created_new_line,
                )

            elif has_base and not has_allele and group_has_line_building:
                base_code, allele_number = ensure_allele_new_or_existing(
                    cx,
                    transgene_base_code=base_norm,
                    mode="Create new allele",
                    existing_allele_number=None,
                    new_allele_nickname=None,
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

                line_id, line_code, created_new_line = ensure_line_for_description(
                    cx,
                    genotype_v11_id=genotype_v11_id,
                    nickname=line_nickname
                    or (genotype_code or genotype_basecodes or "line"),
                    primary_base_code=base_norm or "",
                    default_bg_code=bg_code,
                )

                group_zygosity = _norm(head.get("zygosity")) or "unknown"
                ensure_line_alleles_for_line(
                    cx,
                    line_id=line_id,
                    resolved_alleles=resolved_alleles,
                    constructs_ids_df=constructs_ids_df,
                    default_zygosity=group_zygosity,
                )

                origin_kind = _classify_origin_kind(
                    base_norm=base_norm,
                    allele_nick="AUTO",
                    created_new_line=created_new_line,
                )

            elif not has_base and not has_allele:
                nn = line_nickname or (bg_code or "background")

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
                origin_kind = _classify_origin_kind(
                    base_norm=None,
                    allele_nick=None,
                    created_new_line=created_new_line,
                )

            else:
                raise ValueError(
                    "Genetics loader requires either (base + allele_nickname) or both empty, "
                    "or P0/stable/founder base-only for auto-minted alleles. "
                    "For injections/treatments, use the separate fish_v11_treatments CSV."
                )

            instance_rows: List[Dict[str, Any]] = []
            for _, r in g.iterrows():
                instance_rows.append(
                    {
                        "fish_code": _norm(r.get("fish_nickname")),
                        "instance_stage": _norm(r.get("instance_stage")),
                        "birthday": r.get("birthday"),
                        "genetic_background": _norm(r.get("genetic_background")),
                        "notes": _norm(r.get("notes")),
                        "origin_kind": origin_kind,
                    }
                )

            n_instances, n_tanks = _create_instances_with_genotype_and_bg(
                cx,
                line_id=line_id,
                line_code=line_code,
                genotype_v11_id=genotype_v11_id,
                instances=instance_rows,
            )

            n_total_instances += n_instances
            n_total_tanks += n_tanks
            if created_new_line:
                n_lines_created += 1
            else:
                n_lines_reused += 1

        except Exception as e:
            g_err = g.copy()
            g_err["_error"] = str(e)
            group_errors.append(g_err)
            continue

    if rejected_chunks or group_errors:
        rejected_all = []
        rejected_all.extend(rejected_chunks)
        rejected_all.extend(group_errors)
        rejected_df = pd.concat(rejected_all, ignore_index=True)
    else:
        rejected_df = pd.DataFrame()

    return {
        "n_instances": n_total_instances,
        "n_tanks": n_total_tanks,
        "n_lines_created": n_lines_created,
        "n_lines_reused": n_lines_reused,
        "rejected_rows": rejected_df,
    }
