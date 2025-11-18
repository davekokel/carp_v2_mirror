from __future__ import annotations

import os, sys, pathlib
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

# repo root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.etl.util import get_engine_from_env, normalize_base_code

SEED_DIR = ROOT / "seed_kits" / "2025-11-15-121231-autoload"
CONSTRUCTS_CSV = SEED_DIR / "constructs_plasmid.csv"


def _load_constructs_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"constructs_plasmid.csv not found: {path}")
    df = pd.read_csv(path)
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    required = [
        "plasmid_code",
        "plasmid_name",
        "plasmid_nickname",
        "resistance",
        "plasmid_notes",
        "fluor_code",
        "tag_code",
        "tag_pos",
    ]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"constructs_plasmid.csv missing required column: {col}")

    for col in required:
        df[col] = df[col].fillna("").astype(str).str.strip()

    return df


def _ensure_plasmid(engine: Engine, code: str, name: str, nickname: str,
                    resistance: str, notes: str) -> str:
    """
    Upsert a plasmid row and return its id.
    We treat 'code' as the plasmid code, and derive plasmid_base_code via normalize_base_code.
    """
    base_code = normalize_base_code(code)
    if not base_code:
        base_code = code.strip().upper()

    with engine.begin() as cx:
        pid = cx.execute(
            text(
                """
                INSERT INTO public.plasmids
                  (plasmid_base_code, code, name, nickname, resistance, notes)
                VALUES
                  (:base_code, :code, NULLIF(:name,''), NULLIF(:nick,''), NULLIF(:resistance,''), NULLIF(:notes,''))
                ON CONFLICT (plasmid_base_code) DO UPDATE
                  SET code       = COALESCE(EXCLUDED.code, public.plasmids.code),
                      name       = EXCLUDED.name,
                      nickname   = EXCLUDED.nickname,
                      resistance = EXCLUDED.resistance,
                      notes      = EXCLUDED.notes
                RETURNING id
                """
            ),
            {
                "base_code": base_code,
                "code": code,
                "name": name,
                "nick": nickname,
                "resistance": resistance,
                "notes": notes,
            },
        ).scalar()

    return str(pid)


def _resolve_fluor_id(cx, name: Optional[str]) -> Optional[str]:
    """
    Resolve a fluor identifier (canonical or alias) to fluors.id.
    Mirrors the logic used in the original loader: exact code OR alt_names match.
    """
    if not name:
        return None
    n = str(name).strip()
    if not n:
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
        {"n": n},
    ).scalar()
    return str(row) if row else None


def _resolve_tag_id(cx, name: Optional[str]) -> Optional[str]:
    """
    Resolve a tag identifier (canonical or alias) to tags.id.
    Mirrors the logic used in the original loader: exact code OR alt_names match.
    """
    if not name:
        return None
    n = str(name).strip()
    if not n:
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
        {"n": n},
    ).scalar()
    return str(row) if row else None


def _ensure_fusion(engine: Engine, fluor_code: Optional[str],
                   tag_code: Optional[str], tag_pos: Optional[str]) -> Optional[str]:
    """
    Ensure a fusions row exists for (fluor_code, tag_code, tag_pos) and return its id.
    If both fluor_code and tag_code are empty, returns None.
    """
    fluor_code = (fluor_code or "").strip()
    tag_code = (tag_code or "").strip()
    tag_pos = (tag_pos or "").strip()

    if not fluor_code and not tag_code:
        return None

    with engine.begin() as cx:
        fid = _resolve_fluor_id(cx, fluor_code)
        tid = _resolve_tag_id(cx, tag_code)

        if fluor_code and not fid:
            raise ValueError(f"unknown fluor_code: {fluor_code!r} (load fluors first)")
        if tag_code and not tid:
            raise ValueError(f"unknown tag_code: {tag_code!r} (load tags first)")

        fusion_id = cx.execute(
            text(
                """
                WITH ins AS (
                  INSERT INTO public.fusions (fluor_id, tag_id, tag_pos)
                  VALUES (:fid, :tid, NULLIF(:pos,''))
                  ON CONFLICT DO NOTHING
                  RETURNING id
                )
                SELECT id FROM ins
                UNION ALL
                SELECT id FROM public.fusions
                 WHERE (fluor_id IS NOT DISTINCT FROM :fid)
                   AND (tag_id  IS NOT DISTINCT FROM :tid)
                   AND COALESCE(tag_pos,'') = COALESCE(:pos,'')
                LIMIT 1
                """
            ),
            {"fid": fid, "tid": tid, "pos": tag_pos},
        ).scalar()

    if not fusion_id:
        raise RuntimeError(
            f"unable to create or locate fusion for fluor={fluor_code!r}, tag={tag_code!r}, tag_pos={tag_pos!r}"
        )
    return str(fusion_id)


def load_constructs_plasmid(engine: Engine, csv_path: Path) -> dict:
    df = _load_constructs_csv(csv_path)

    # Upsert plasmids
    plasmid_ids: dict[str, str] = {}
    plasmid_rows = (
        df[["plasmid_code", "plasmid_name", "plasmid_nickname", "resistance", "plasmid_notes"]]
        .drop_duplicates()
    )

    for _, row in plasmid_rows.iterrows():
        code = row["plasmid_code"]
        if not code:
            continue
        pid = _ensure_plasmid(
            engine,
            code=code,
            name=row["plasmid_name"],
            nickname=row["plasmid_nickname"],
            resistance=row["resistance"],
            notes=row["plasmid_notes"],
        )
        plasmid_ids[code] = pid

    # Link fusions
    links_created = 0
    fusion_errors: list[str] = []

    with engine.begin() as cx:
        for _, row in df.iterrows():
            code = row["plasmid_code"]
            if not code:
                continue
            pid = plasmid_ids.get(code)
            if not pid:
                continue

            fluor = row["fluor_code"]
            tag = row["tag_code"]
            pos = row["tag_pos"]

            fluor = (fluor or "").strip()
            tag = (tag or "").strip()
            pos = (pos or "").strip()

            if not fluor and not tag:
                # no fluor/tag on this row -> nothing to link
                continue

            try:
                fusion_id = _ensure_fusion(engine, fluor, tag, pos)
            except Exception as e:
                fusion_errors.append(f"{code}/{fluor}/{tag}/{pos}: {e}")
                continue

            if not fusion_id:
                continue

            res = cx.execute(
                text(
                    """
                    INSERT INTO public.join_plasmid_fusions (plasmid_id, fusion_id)
                    VALUES (:pid, :fid)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"pid": pid, "fid": fusion_id},
            )
            if res.rowcount and res.rowcount > 0:
                links_created += 1

    return {
        "plasmids_upserted": len(plasmid_ids),
        "links_created": links_created,
        "fusion_errors": fusion_errors,
    }


def main() -> None:
    print(f"DB_URL={os.getenv('DB_URL')}")
    engine = get_engine_from_env()

    summary = load_constructs_plasmid(engine, CONSTRUCTS_CSV)
    print("Summary:", summary)


if __name__ == "__main__":
    main()
