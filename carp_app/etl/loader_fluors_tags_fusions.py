from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from carp_app.etl.util import get_engine_from_env, normalize_base_code

def _build_alias_maps(alias_csv: Optional[Path]) -> dict:
    maps: dict[str, dict[str, list[str]]] = {
        "fluor": {},
        "tag": {},
    }
    if not alias_csv:
        return maps

    import pandas as _pd

    df = _pd.read_csv(alias_csv)
    if df.empty:
        return maps

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    for col in ["target_kind", "target_key", "alias"]:
        if col not in df.columns:
            return maps

    df = df.dropna(subset=["target_kind", "target_key", "alias"])
    df["target_kind"] = df["target_kind"].astype(str).str.strip().str.lower()
    df["target_key"] = df["target_key"].astype(str).str.strip()
    df["alias"] = df["alias"].astype(str).str.strip()

    for _, row in df.iterrows():
        kind = row["target_kind"]
        key = row["target_key"]
        alias = row["alias"]
        if not alias:
            continue
        if kind in maps:
            m = maps[kind]
            lk = key.lower()
            if lk not in m:
                m[lk] = []
            if alias not in m[lk]:
                m[lk].append(alias)

    return maps

def load_fluors_from_csv(
    fluors_csv: str | Path,
    alias_csv: Optional[str | Path] = None,
    engine: Optional[Engine] = None,
) -> dict:
    from pathlib import Path as _Path
    import pandas as _pd

    fpath = _Path(fluors_csv)
    if not fpath.exists():
        raise FileNotFoundError(f"Fluors CSV not found: {fpath}")

    df = _pd.read_csv(fpath)
    if df.empty:
        return {"rows": 0, "inserted": 0, "updated": 0, "warnings": []}

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["nickname"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"fluors.csv is missing required columns: {missing}")

    df["nickname"] = df["nickname"].astype(str).str.strip()
    df["aliases"] = df.get("aliases", "").astype(str)
    df["excitation_nm"] = df.get("excitation_nm")
    df["emission_nm"] = df.get("emission_nm")
    if "notes" not in df.columns:
        if "note" in df.columns:
            df["notes"] = df["note"].astype(str)
        else:
            df["notes"] = ""
    else:
        df["notes"] = df["notes"].astype(str)

    alias_maps = _build_alias_maps(_Path(alias_csv) if alias_csv else None)
    fluor_alias_map = alias_maps.get("fluor", {})

    records = []
    warnings: list[str] = []

    for _, row in df.iterrows():
        code = row["nickname"]
        if not code:
            continue
        key_l = code.lower()
        alt: list[str] = []

        raw_aliases = str(row.get("aliases", "") or "")
        for part in raw_aliases.replace(";", ",").split(","):
            a = part.strip()
            if a:
                alt.append(a)

        extra = fluor_alias_map.get(key_l, [])
        for a in extra:
            if a not in alt:
                alt.append(a)

        try:
            ex_nm = int(row["excitation_nm"]) if not _pd.isna(row["excitation_nm"]) else None
        except Exception:
            ex_nm = None
            warnings.append(f"Invalid excitation_nm for fluor {code!r}, storing NULL.")

        try:
            em_nm = int(row["emission_nm"]) if not _pd.isna(row["emission_nm"]) else None
        except Exception:
            em_nm = None
            warnings.append(f"Invalid emission_nm for fluor {code!r}, storing NULL.")

        notes = row.get("notes", "") or ""

        records.append(
            {
                "fluor_code": code,
                "fluor_name": code,
                "excitation_nm": ex_nm,
                "emission_nm": em_nm,
                "alt_names": alt,
                "notes": notes.strip(),
            }
        )

    if not records:
        return {"rows": 0, "inserted": 0, "updated": 0, "warnings": warnings}

    if engine is None:
        engine = get_engine_from_env()

    sql = text(
        """
        INSERT INTO public.fluors
          (fluor_code, fluor_name, excitation_nm, emission_nm, alt_names, notes)
        VALUES
          (:code, NULLIF(:name,''), :ex_nm, :em_nm, :alt_names, NULLIF(:notes,''))
        ON CONFLICT (fluor_code) DO UPDATE
        SET fluor_name    = EXCLUDED.fluor_name,
            excitation_nm = EXCLUDED.excitation_nm,
            emission_nm   = EXCLUDED.emission_nm,
            alt_names     = EXCLUDED.alt_names,
            notes         = EXCLUDED.notes
        """
    )

    codes = {r["fluor_code"] for r in records}
    with engine.begin() as cx:
        existing = set(
            cx.execute(
                text(
                    "SELECT fluor_code FROM public.fluors WHERE lower(fluor_code) = ANY(:codes)"
                ),
                {"codes": [c.lower() for c in codes]},
            ).scalars().all()
        )

    inserted = 0
    updated = 0
    with engine.begin() as cx:
        for r in records:
            code = r["fluor_code"]
            params = {
                "code": code,
                "name": r["fluor_name"],
                "ex_nm": r["excitation_nm"],
                "em_nm": r["emission_nm"],
                "alt_names": r["alt_names"] if r["alt_names"] else None,
                "notes": r["notes"],
            }
            cx.execute(sql, params)
            if code in existing:
                updated += 1
            else:
                inserted += 1
                existing.add(code)

    return {"rows": len(records), "inserted": inserted, "updated": updated, "warnings": warnings}

def load_tags_from_excel(
    tags_xlsx: str | Path,
    alias_csv: Optional[str | Path] = None,
    engine: Optional[Engine] = None,
) -> dict:
    from pathlib import Path as _Path
    import pandas as _pd

    tpath = _Path(tags_xlsx)
    if not tpath.exists():
        raise FileNotFoundError(f"Tags Excel file not found: {tpath}")

    df = _pd.read_excel(tpath)
    if df.empty:
        return {"rows": 0, "inserted": 0, "updated": 0, "warnings": []}

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["nickname"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"tags.xlsx is missing required columns: {missing}")

    df["nickname"] = df["nickname"].astype(str).str.strip()
    df["aliases"] = df.get("aliases", "").astype(str)
    df["localization"] = df.get("localization", "").astype(str)
    df["note"] = df.get("note", "").astype(str)
    df["citation_link"] = df.get("citation_link", "").astype(str)

    alias_maps = _build_alias_maps(_Path(alias_csv) if alias_csv else None)
    tag_alias_map = alias_maps.get("tag", {})

    records = []
    warnings: list[str] = []

    for _, row in df.iterrows():
        code = row["nickname"]
        if not code:
            continue
        key_l = code.lower()

        alt: list[str] = []
        raw_aliases = str(row.get("aliases", "") or "")
        for part in raw_aliases.replace(";", ",").split(","):
            a = part.strip()
            if a:
                alt.append(a)

        extra = tag_alias_map.get(key_l, [])
        for a in extra:
            if a not in alt:
                alt.append(a)

        loc = row.get("localization", "") or ""
        note = row.get("note", "") or ""
        citation = row.get("citation_link", "") or ""
        notes = note.strip()
        if citation and citation.strip():
            if notes:
                notes = f"{notes} [citation: {citation.strip()}]"
            else:
                notes = f"[citation: {citation.strip()}]"

        records.append(
            {
                "tag_code": code,
                "tag_name": code,
                "alt_names": alt,
                "localization": loc.strip(),
                "notes": notes,
            }
        )

    if not records:
        return {"rows": 0, "inserted": 0, "updated": 0, "warnings": warnings}

    if engine is None:
        engine = get_engine_from_env()

    sql = text(
        """
        INSERT INTO public.tags
          (tag_code, tag_name, alt_names, localization, notes)
        VALUES
          (:code, NULLIF(:name,''), :alt_names, NULLIF(:loc,''), NULLIF(:notes,''))
        ON CONFLICT (tag_code) DO UPDATE
        SET tag_name    = EXCLUDED.tag_name,
            alt_names   = EXCLUDED.alt_names,
            localization = EXCLUDED.localization,
            notes       = EXCLUDED.notes
        """
    )

    codes = {r["tag_code"] for r in records}
    with engine.begin() as cx:
        existing = set(
            cx.execute(
                text(
                    "SELECT tag_code FROM public.tags WHERE lower(tag_code) = ANY(:codes)"
                ),
                {"codes": [c.lower() for c in codes]},
            ).scalars().all()
        )

    inserted = 0
    updated = 0
    with engine.begin() as cx:
        for r in records:
            code = r["tag_code"]
            params = {
                "code": code,
                "name": r["tag_name"],
                "alt_names": r["alt_names"] if r["alt_names"] else None,
                "loc": r["localization"],
                "notes": r["notes"],
            }
            cx.execute(sql, params)
            if code in existing:
                updated += 1
            else:
                inserted += 1
                existing.add(code)

    return {"rows": len(records), "inserted": inserted, "updated": updated, "warnings": warnings}

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

def _clean_tag_pos(raw, warnings: list[str], context: str) -> Optional[str]:
    s = str(raw or "").strip()
    if not s or s.lower() == "nan":
        return None
    u = s.upper()
    if u in ("N", "C"):
        return u
    warnings.append(f"Unknown tag_pos {s!r} for {context}; storing NULL.")
    return None

def _get_or_create_fusion(
    cx,
    fluor_id: str,
    tag_id: Optional[str],
    tag_pos: Optional[str],
):
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
    from pathlib import Path as _Path
    import pandas as _pd

    fpath = _Path(plasmid_fusions_csv)
    if not fpath.exists():
        raise FileNotFoundError(f"plasmid_fusions CSV not found: {fpath}")

    df = _pd.read_csv(fpath)
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
    from pathlib import Path as _Path
    import pandas as _pd

    rpath = _Path(rna_fusions_csv)
    if not rpath.exists():
        raise FileNotFoundError(f"rna_fusions CSV not found: {rpath}")

    df = _pd.read_csv(rpath)
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
