from __future__ import annotations

from typing import List, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection


def normalize_rna_fusions_table(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Strict normalization for seed rna_fusions.csv.

    Expected headers (exact, case-insensitive):
      rna_base_code,nickname,n_fluors_per_rna,fluor,tag,tag_pos,token
    """
    df = df_raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = [
        "rna_base_code",
        "nickname",
        "n_fluors_per_rna",
        "fluor",
        "tag",
        "tag_pos",
        "token",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"rna_fusions CSV missing required column(s): {missing}")

    out = pd.DataFrame(
        {
            "rna_base_code": df["rna_base_code"].map(lambda v: "" if v is None else str(v).strip()),
            "nickname": df["nickname"].map(lambda v: "" if v is None else str(v).strip()),
            "n_fluors_per_rna": df["n_fluors_per_rna"].map(
                lambda v: 0
                if v is None or str(v).strip().lower() in {"", "nan", "none", "null"}
                else int(float(str(v).strip()))
            ),
            "fluor": df["fluor"].map(lambda v: "" if v is None else str(v).strip()),
            "tag": df["tag"].map(lambda v: "" if v is None else str(v).strip()),
            "tag_pos": df["tag_pos"].map(lambda v: "" if v is None else str(v).strip()),
            "token": df["token"].map(lambda v: "" if v is None else str(v).strip()),
        }
    )

    out = out[out["rna_base_code"] != ""].copy()
    return out


def load_rna_fusions_from_df(
    df_raw: pd.DataFrame, cx: Connection
) -> Tuple[int, List[str]]:
    """
    Validate rna_fusions against RNAs, fluors, and tags.

    Checks each row:
      - rna_base_code exists in public.rnas.rna_code
      - fluor exists in public.fluors (fluor_name or fluor_code)
      - tag exists in public.tags.tag_name

    Returns:
      (valid_rows_count, warnings)
    """
    df = normalize_rna_fusions_table(df_raw)
    warnings: List[str] = []
    valid = 0

    for row in df.to_dict(orient="records"):
        rcode = row["rna_base_code"]
        fluor = row["fluor"]
        tag = row["tag"]

        rid = cx.execute(
            text("SELECT id FROM public.rnas WHERE rna_code = :c LIMIT 1"),
            {"c": rcode},
        ).scalar()
        if not rid:
            warnings.append(f"RNA fusion row skipped: RNA '{rcode}' not found.")
            continue

        fid = cx.execute(
            text(
                """
              SELECT id FROM public.fluors
              WHERE fluor_name = :c OR fluor_code = :c
              LIMIT 1
            """
            ),
            {"c": fluor},
        ).scalar()
        if not fid:
            warnings.append(f"RNA fusion row skipped: fluor '{fluor}' not found.")
            continue

        tid = cx.execute(
            text("SELECT id FROM public.tags WHERE tag_name = :c LIMIT 1"),
            {"c": tag},
        ).scalar()
        if not tid:
            warnings.append(f"RNA fusion row skipped: tag '{tag}' not found.")
            continue

        # All checks passed
        valid += 1

    return valid, warnings
