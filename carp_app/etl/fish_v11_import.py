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


def _classify_origin_kind(group: pd.DataFrame, created_new_line: bool) -> str:
    """
    Coarse origin classification for a grouped CSV chunk.

    For now:
      - background_only        (no base, no allele OR injection-only coerced to bg)
      - transgenic_new_line
      - transgenic_existing_line
    """
    row = group.iloc[0]
    base = _norm(row.get("norm_base_code"))
    allele = _norm(row.get("allele_nickname"))

    # Background-only: no explicit transgene, no allele
    if not base and not allele:
        return "background_only"

    # Genotyped transgenic: both base and allele set
    if base and allele:
        return "transgenic_new_line" if created_new_line else "transgenic_existing_line"

    # Any other combo (e.g. base only, allele only) should have been normalized or rejected
    raise ValueError(
        f"{base or allele}: must have both transgene_base_code and allele_nickname for "
        "genotyped lines, or leave both blank for background-only lines."
    )


def load_fish_from_csv(df_raw: pd.DataFrame, cx: Connection) -> Dict[str, Any]:
    """
    Canonical v11 CSV loader for fish lines • alleles • instances.

    CSV contract (minimal change from fish.csv):

      REQUIRED columns:
        - transgene_base_code  (construct base code, e.g. pdqm063 / pDQM063 / MGCO-35)
        - line_nickname        (line nickname)
        - allele_nickname      (allele nickname; if present with base → genotyped line)
        - instance_stage       (e.g. P0, F1, juvenile)
        - birthday             (YYYY-MM-DD)
        - genetic_background   (bg_code from genetic_backgrounds)

      OPTIONAL columns (auto-created as empty if missing):
        - fish_nickname        (per-fish nickname; used to seed fish_code if present)
        - notes                (free text, we may decorate with e.g. INJECTION:TAG)

    Behavior:

      • Rows are grouped by (norm_base_code, line_nickname, allele_nickname, bg).
      • If both base+allele present → create/reuse allele, genotype, line; origin_kind
        is transgenic_new_line vs transgenic_existing_line.
      • If base present but allele empty → treated as “injection” background-only; we
        clear base and prefix notes with 'INJECTION:<base>'.
      • If both base & allele empty → background-only line, no genotypes_v11 row.
      • All genetic_background values are validated against public.genetic_backgrounds.
      • On any per-group error, that group’s rows are emitted as rejected_rows with
        an _error column; other groups still import.
    """
    df = df_raw.copy()

    # Normalize column names (strip spaces)
    df.columns = [c.strip() for c in df.columns]

    # Ensure required structural columns are present
    missing = REQUIRED_COLS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in CSV: {sorted(missing)!r}")

    # Ensure optional columns exist; synthesize empty ones if absent
    for col in ("fish_nickname", "notes"):
        if col not in df.columns:
            df[col] = ""

    # Force string-ish representation for text columns that now exist
    for col in [
        "transgene_base_code",
        "line_nickname",
        "allele_nickname",
        "fish_nickname",
        "instance_stage",
        "genetic_background",
        "notes",
    ]:
        if col in df.columns:
            df[col] = df[col].astype("string")

    # Normalize base codes into canonical base_code (may be NULL)
    df["norm_base_code"] = df["transgene_base_code"].map(_normalize_base_code)

    # Validate genetic_background values
    bg_df = pd.read_sql(
        text("SELECT bg_code FROM public.genetic_backgrounds;"),
        cx,
    )
    bg_set = {(_norm(b) or "") for b in bg_df["bg_code"].astype("string")}
    df["_bg_norm"] = df["genetic_background"].map(_norm)
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
        rejected = pd.concat(rejected_chunks, ignore_index=True) if rejected_chunks else pd.DataFrame()
        return {
            "n_instances": 0,
            "n_tanks": 0,
            "n_lines_created": 0,
            "n_lines_reused": 0,
            "rejected_rows": rejected,
        }

    # Coerce injection rows: base present, allele_nickname empty → background-only with note
    def _maybe_injection(row: pd.Series) -> pd.Series:
        base = _norm(row.get("norm_base_code"))
        allele = _norm(row.get("allele_nickname"))
        notes = _norm(row.get("notes")) or ""
        stage = (_norm(row.get("instance_stage")) or "").lower()

        if base and not allele:
            tag = f"INJECTION:{base}"
            notes = f"{tag}" if not notes else f"{tag} | {notes}"
            row["norm_base_code"] = None
            row["transgene_base_code"] = ""
            row["notes"] = notes
        return row

    df = df.apply(_maybe_injection, axis=1)

    # Prepare counts
    n_total_instances = 0
    n_total_tanks = 0
    n_lines_created = 0
    n_lines_reused = 0

    constructs_ids_df = load_construct_ids(cx)

    # Group rows by logical “line+allele+background” cluster
    df["_key_base"] = df["norm_base_code"].map(_norm)
    df["_key_allele"] = df["allele_nickname"].map(_norm)
    df["_key_line"] = df["line_nickname"].map(_norm)
    df["_key_bg"] = df["_bg_norm"]

    grouped = df.groupby(
        ["_key_base", "_key_allele", "_key_line", "_key_bg"],
        dropna=False,
        sort=False,
    )

    group_errors: List[pd.DataFrame] = []

    for (_base, _allele, _line, _bg), g in grouped:
        # Single representative row for error messages
        g_head = g.head(1).copy()

        try:
            base_norm = _norm(g_head.iloc[0].get("norm_base_code"))
            allele_nick = _norm(g_head.iloc[0].get("allele_nickname"))
            line_nickname = _norm(g_head.iloc[0].get("line_nickname"))
            bg_code = _norm(g_head.iloc[0].get("genetic_background"))

            resolved_alleles: List[Dict[str, Any]] = []
            genotype_v11_id: Optional[str] = None

            # Genotyped group (base + allele) → build genotype + allele set
            if base_norm and allele_nick:
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
            else:
                # Background-only cluster: no genotype
                genotype_v11_id = None
                genotype_code = None
                genotype_basecodes = None

            primary_base_code = base_norm
            default_bg_code = bg_code

            # Ensure/lookup line
            if genotype_v11_id:
                line_id, line_code, created_new_line = ensure_line_for_description(
                    cx,
                    genotype_v11_id=genotype_v11_id,
                    nickname=line_nickname or (genotype_code or genotype_basecodes or "line"),
                    primary_base_code=primary_base_code or "",
                    default_bg_code=default_bg_code,
                )
            else:
                # Background-only lines: no genotype/construct linkage
                nn = line_nickname or (bg_code or "background")
                df_line = pd.read_sql(
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
                if not df_line.empty:
                    r = df_line.iloc[0]
                    line_id = r["line_id"]
                    line_code = r["line_code"]
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

            origin_kind = _classify_origin_kind(g, created_new_line)

            # Build instance rows for this group
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

            # Insert instances (background-only gets genotype_v11_id=None)
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

    # Stitch together rejected rows (bad bg + group-level failures)
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
