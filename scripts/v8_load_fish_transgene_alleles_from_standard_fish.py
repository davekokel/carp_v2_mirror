from __future__ import annotations

import argparse
import sys
import pathlib
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import text, bindparam
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import ARRAY, UUID

# ---- repo bootstrap ---------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.lib.page_engine import engine as get_engine  # type: ignore


# ---- helpers ----------------------------------------------------------------
def _load_dataframe(path: pathlib.Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"fish XLSX not found: {path}")
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _build_fish_map(engine: Engine) -> Dict[str, Tuple[str, str]]:
    """
    Map nickname -> (fish_id, fish_code)

    Assumes v7_load_fish_standard has already loaded fish_instance.
    """
    sql = text(
        """
        SELECT id::text AS fish_id, fish_code::text, nickname
        FROM public.fish_instance
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    df["nickname"] = df["nickname"].astype("string").str.strip()
    mapping: Dict[str, Tuple[str, str]] = {}
    for _, row in df.iterrows():
        nick = row["nickname"]
        if not nick:
            continue
        mapping[str(nick)] = (str(row["fish_id"]), str(row["fish_code"]))
    return mapping


def _build_allele_map(engine: Engine) -> Dict[Tuple[str, str], int]:
    """
    Map (transgene_base_code, allele_nickname) -> allele_number
    from public.transgene_alleles.
    """
    sql = text(
        """
        SELECT
          transgene_base_code,
          allele_number,
          COALESCE(allele_nickname, '') AS allele_nickname
        FROM public.transgene_alleles
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    df["transgene_base_code"] = df["transgene_base_code"].astype("string").str.strip()
    df["allele_nickname"] = df["allele_nickname"].astype("string").str.strip()

    mapping: Dict[Tuple[str, str], int] = {}
    for _, row in df.iterrows():
        base = str(row["transgene_base_code"])
        nick = str(row["allele_nickname"])
        mapping[(base, nick)] = int(row["allele_number"])
    return mapping


def _prepare_join_rows(
    df_fish: pd.DataFrame,
    fish_map: Dict[str, Tuple[str, str]],
    allele_map: Dict[Tuple[str, str], int],
) -> List[Dict[str, object]]:
    """
    From fish.xlsx rows, build join_fish_transgene_alleles payload.
    """
    required_cols = {"nickname", "transgene_base_code", "allele_nickname"}
    missing = required_cols - set(df_fish.columns)
    if missing:
        raise ValueError(
            f"fish.xlsx is missing required columns: {sorted(missing)}"
        )

    df = df_fish.copy()
    df["nickname"] = df["nickname"].astype("string").str.strip()
    df["transgene_base_code"] = df["transgene_base_code"].astype("string").str.strip()
    df["allele_nickname"] = df["allele_nickname"].astype("string").str.strip()
    if "zygosity" in df.columns:
        df["zygosity"] = df["zygosity"].astype("string").str.strip()
    else:
        df["zygosity"] = ""

    rows: List[Dict[str, object]] = []
    skipped_no_fish = 0
    skipped_no_allele = 0

    for _, row in df.iterrows():
        nick = str(row["nickname"])
        base = str(row["transgene_base_code"])
        nick_allele = str(row["allele_nickname"])

        if not nick or not base or not nick_allele:
            continue

        if nick not in fish_map:
            skipped_no_fish += 1
            continue

        key = (base, nick_allele)
        if key not in allele_map:
            skipped_no_allele += 1
            continue

        allele_number = allele_map[key]
        fish_id, _ = fish_map[nick]
        zyg = str(row.get("zygosity", "") or "")

        rows.append(
            {
                "fish_id": fish_id,
                "transgene_base_code": base,
                "allele_number": int(allele_number),
                "zygosity": zyg,
            }
        )

    total = len(df)
    print(
        f"[INFO] v8_load_fish_transgene_alleles: "
        f"input_rows={total}, prepared={len(rows)}, "
        f"skipped_no_fish={skipped_no_fish}, skipped_no_allele={skipped_no_allele}"
    )
    return rows


def _upsert_join(engine: Engine, rows: List[Dict[str, object]]) -> None:
    if not rows:
        print("[INFO] v8_load_fish_transgene_alleles: nothing to upsert.")
        return

    import uuid as _uuid

    fish_ids_uuid = sorted({_uuid.UUID(r["fish_id"]) for r in rows if r.get("fish_id")})

    delete_sql = text(
        """
        DELETE FROM public.join_fish_transgene_alleles
        WHERE fish_id = ANY(:fish_ids)
        """
    ).bindparams(bindparam("fish_ids", type_=ARRAY(UUID(as_uuid=True))))

    insert_sql = text(
        """
        INSERT INTO public.join_fish_transgene_alleles (
          fish_id,
          transgene_base_code,
          allele_number,
          zygosity
        )
        VALUES (
          :fish_id,
          :transgene_base_code,
          :allele_number,
          NULLIF(:zygosity, '')
        )
        ON CONFLICT (fish_id, transgene_base_code, allele_number)
        DO UPDATE SET
          zygosity = COALESCE(
            NULLIF(EXCLUDED.zygosity, ''),
            join_fish_transgene_alleles.zygosity
          )
        """
    )

    with engine.begin() as cx:
        cx.execute(delete_sql, {"fish_ids": fish_ids_uuid})
        cx.execute(insert_sql, rows)

    print(
        f"[INFO] v8_load_fish_transgene_alleles: upserted {len(rows)} row(s) "
        f"for {len(fish_ids_uuid)} fish."
    )


# ---- main -------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Link standard fish to canonical transgene alleles (v8)."
    )
    parser.add_argument(
        "--fish-xlsx",
        required=True,
        help="Path to standard fish.xlsx used by v7_load_fish_standard.py",
    )
    args = parser.parse_args()

    fish_path = pathlib.Path(args.fish_xlsx)
    df_fish = _load_dataframe(fish_path)

    engine = get_engine()
    fish_map = _build_fish_map(engine)
    allele_map = _build_allele_map(engine)

    rows = _prepare_join_rows(df_fish, fish_map, allele_map)
    _upsert_join(engine, rows)


if __name__ == "__main__":
    main()
