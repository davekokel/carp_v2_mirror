from __future__ import annotations

from pathlib import Path
from typing import Optional, List

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.etl.util import get_engine_from_env, normalize_base_code


def _resolve_fluor_id(cx, name: str) -> Optional[str]:
    if not name:
        return None
    name_s = str(name).strip()
    if not name_s:
        return None
    row = cx.execute(
        text(
            """
            SELECT id
            FROM public.fluors
            WHERE lower(fluor_code) = lower(:n)
               OR EXISTS (
                    SELECT 1 FROM unnest(alt_names) a WHERE lower(a) = lower(:n)
                 )
            LIMIT 1
            """
        ),
        {"n": name_s},
    ).scalar()
    return row


def _resolve_tag_id(cx, name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    name_s = str(name).strip()
    if not name_s:
        return None
    row = cx.execute(
        text(
            """
            SELECT id
            FROM public.tags
            WHERE lower(tag_code) = lower(:n)
               OR EXISTS (
                    SELECT 1 FROM unnest(alt_names) a WHERE lower(a) = lower(:n)
                 )
            LIMIT 1
            """
        ),
        {"n": name_s},
    ).scalar()
    return row


def _clean_tag_pos(raw, has_tag: bool, context: str) -> str | None:
    """
    Normalize tag_pos.

    Rules (v7 contract):
      - If there is no tag (has_tag=False), tag_pos is ignored → always returns None.
      - If there *is* a tag (has_tag=True):
          * empty / NaN tag_pos → hard error (fail the load)
          * allowed values: 'N', 'C' (case-insensitive)
          * anything else → hard error so the CSV gets fixed.

    This forces the seed kit to be explicit about tag positions, and prevents
    creating fusions with tags but no tag_pos.
    """
    s = str(raw or "").strip()
    if not has_tag:
        # No tag, position doesn't matter
        return None

    if not s or s.lower() == "nan":
        raise ValueError(f"Missing tag_pos for tagged fusion in {context} (CSV must specify N or C).")

    u = s.upper()
    if u in ("N", "C"):
        return u

    raise ValueError(
        f"Unknown tag_pos {s!r} for {context}; expected 'N' or 'C' (update the seed CSV to use only N/C)."
    )


def _get_or_create_fusion(
    cx,
    fluor_id: str,
    tag_id: Optional[str],
    tag_pos: Optional[str],
) -> Optional[str]:
    params = {
        "fluor_id": fluor_id,
        "tag_id": tag_id,
        "tag_pos": tag_pos,
    }

    row = cx.execute(
        text(
            """
            SELECT id
            FROM public.fusions
            WHERE fluor_id = :fluor_id
              AND (
                    (:tag_id IS NULL AND tag_id IS NULL)
                 OR (tag_id = :tag_id)
              )
              AND COALESCE(tag_pos,'') = COALESCE(:tag_pos,'')
            LIMIT 1
            """
        ),
        params,
    ).scalar()

    if row:
        return row

    fid = cx.execute(
        text(
            """
            INSERT INTO public.fusions (fluor_id, tag_id, tag_pos)
            VALUES (:fluor_id, :tag_id, :tag_pos)
            RETURNING id
            """
        ),
        params,
    ).scalar()

    return fid


def load_plasmid_fusions_from_csv(
    plasmid_fusions_csv: str | Path,
    engine: Optional[Engine] = None,
) -> dict:
    """
    Load plasmid_fusions.csv into public.fusions + join_plasmid_fusions.

    Columns:
      - plasmid_base_code
      - nickname
      - n_fluors_per_plasmid
      - fluor
      - tag
      - tag_pos
    """
    path = Path(plasmid_fusions_csv)
    if not path.exists():
        raise FileNotFoundError(f"plasmid_fusions CSV not found: {path}")

    df = pd.read_csv(path)
    if df.empty:
        return {"rows": 0, "fusions_created": 0, "links_created": 0, "warnings": []}

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["plasmid_base_code", "fluor"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"plasmid_fusions.csv is missing required columns: {missing}")

    df["plasmid_base_code"] = df["plasmid_base_code"].astype(str).str.strip()
    df["fluor"] = df["fluor"].astype(str)
    df["tag"] = df.get("tag", "").astype(str)
    df["tag_pos"] = df.get("tag_pos", "")

    if engine is None:
        engine = get_engine_from_env()

    warnings: list[str] = []
    fusions_created = 0
    links_created = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            base = normalize_base_code(row["plasmid_base_code"])
            if not base:
                continue

            plasmid_id = cx.execute(
                text(
                    "SELECT id FROM public.plasmids WHERE plasmid_base_code = :b LIMIT 1"
                ),
                {"b": base},
            ).scalar()
            if not plasmid_id:
                warnings.append(f"Skipping plasmid_fusion row: plasmid_base_code {base!r} not found.")
                continue

            fluor_name = row.get("fluor", "") or ""
            fluor_id = _resolve_fluor_id(cx, fluor_name)
            if not fluor_id:
                warnings.append(f"Skipping plasmid_fusion row: fluor {fluor_name!r} not found.")
                continue

            tag_name = row.get("tag")
            tag_id = _resolve_tag_id(cx, tag_name)
            raw_pos = row.get("tag_pos")
            tag_pos = _clean_tag_pos(
                raw_pos,
                warnings,
                f"plasmid_base_code={base}, fluor={fluor_name}, tag={tag_name}",
            )

            fusion_id = _get_or_create_fusion(cx, fluor_id, tag_id, tag_pos)
            if not fusion_id:
                warnings.append(
                    f"Failed to create or find fusion for plasmid={base}, fluor={fluor_name}, tag={tag_name}, tag_pos={raw_pos!r}."
                )
                continue

            res = cx.execute(
                text(
                    """
                    INSERT INTO public.join_plasmid_fusions (plasmid_id, fusion_id)
                    VALUES (:pid, :fid)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"pid": plasmid_id, "fid": fusion_id},
            )
            if res.rowcount and res.rowcount > 0:
                links_created += 1

    return {
        "rows": len(df),
        "fusions_created": fusions_created,
        "links_created": links_created,
        "warnings": warnings,
    }


def load_rna_fusions_from_csv(
    rna_fusions_csv: str | Path,
    engine: Optional[Engine] = None,
) -> dict:
    """
    Load rna_fusions.csv into public.fusions + join_rna_fusions.

    Columns:
      - rna_base_code (e.g. 'RNA(MGCO-01)')
      - nickname
      - n_fluors_per_rna
      - fluor
      - tag
      - tag_pos
      - token
    """
    path = Path(rna_fusions_csv)
    if not path.exists():
        raise FileNotFoundError(f"rna_fusions CSV not found: {path}")

    df = pd.read_csv(path)
    if df.empty:
        return {"rows": 0, "fusions_created": 0, "links_created": 0, "warnings": []}

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["rna_base_code", "fluor"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"rna_fusions.csv is missing required columns: {missing}")

    df["rna_base_code"] = df["rna_base_code"].astype(str).str.strip()
    df["fluor"] = df.get("fluor", "").astype(str)
    df["tag"] = df.get("tag", "").astype(str)
    df["tag_pos"] = df.get("tag_pos", "")

    def _extract_rna_base(raw: str) -> str:
        s = str(raw or "").strip()
        if s.upper().startswith("RNA(") and s.endswith(")"):
            inner = s[4:-1]
        else:
            inner = s
        return normalize_base_code(inner)

    df["rna_base_code_norm"] = df["rna_base_code"].apply(_extract_rna_base)

    if engine is None:
        engine = get_engine_from_env()

    warnings: list[str] = []
    fusions_created = 0
    links_created = 0

    with engine.begin() as cx:
        for _, row in df.iterrows():
            base = row["rna_base_code_norm"]
            if not base:
                continue

            rna_id = cx.execute(
                text(
                    "SELECT id FROM public.rnas WHERE rna_base_code = :b LIMIT 1"
                ),
                {"b": base},
            ).scalar()
            if not rna_id:
                warnings.append(f"Skipping rna_fusion row: rna_base_code {base!r} not found.")
                continue

            fluor_name = row.get("fluor", "") or ""
            fluor_id = _resolve_fluor_id(cx, fluor_name)
            if not fluor_id:
                warnings.append(f"Skipping rna_fusion row: fluor {fluor_name!r} not found.")
                continue

            tag_name = row.get("tag")
            tag_id = _resolve_tag_id(cx, tag_name)
            raw_pos = row.get("tag_pos")
            tag_pos = _clean_tag_pos(
                raw_pos,
                warnings,
                f"rna_base_code={base}, fluor={fluor_name}, tag={tag_name}",
            )

            fusion_id = _get_or_create_fusion(cx, fluor_id, tag_id, tag_pos)
            if not fusion_id:
                warnings.append(
                    f"Failed to create or find fusion for rna={base}, fluor={fluor_name}, tag={tag_name}, tag_pos={raw_pos!r}."
                )
                continue

            res = cx.execute(
                text(
                    """
                    INSERT INTO public.join_rna_fusions (rna_id, fusion_id)
                    VALUES (:rid, :fid)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"rid": rna_id, "fid": fusion_id},
            )
            if res.rowcount and res.rowcount > 0:
                links_created += 1

    return {
        "rows": len(df),
        "fusions_created": fusions_created,
        "links_created": links_created,
        "warnings": warnings,
    }
