from __future__ import annotations

from typing import List, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection


def normalize_plasmid_fusions_table(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Strict normalization for seed plasmid_fusions.csv.

    Expected headers (exact, case-insensitive):
      plasmid_base_code,nickname,n_fluors_per_plasmid,fluor,tag,tag_pos
    """
    df = df_raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = [
        "plasmid_base_code",
        "nickname",
        "n_fluors_per_plasmid",
        "fluor",
        "tag",
        "tag_pos",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"plasmid_fusions CSV missing required column(s): {missing}")

    out = pd.DataFrame(
        {
            "plasmid_base_code": df["plasmid_base_code"].map(
                lambda v: "" if v is None else str(v).strip()
            ),
            "nickname": df["nickname"].map(lambda v: "" if v is None else str(v).strip()),
            "n_fluors_per_plasmid": df["n_fluors_per_plasmid"].map(
                lambda v: 0
                if v is None or str(v).strip().lower() in {"", "nan", "none", "null"}
                else int(float(str(v).strip()))
            ),
            "fluor": df["fluor"].map(lambda v: "" if v is None else str(v).strip()),
            "tag": df["tag"].map(lambda v: "" if v is None else str(v).strip()),
            "tag_pos": df["tag_pos"].map(lambda v: "" if v is None else str(v).strip()),
            # token is optional; we don't need it for validation
        }
    )

    out = out[out["plasmid_base_code"] != ""].copy()
    return out


def load_plasmid_fusions_from_df(
    df_raw: pd.DataFrame, cx: Connection
) -> Tuple[int, List[str]]:
    """
    Validate plasmid_fusions against plasmids, fluors, and tags.

    Checks each row:
      - plasmid_base_code exists in public.plasmids.code
      - fluor exists in public.fluors (fluor_name or fluor_code)
      - tag exists in public.tags.tag_name

    Returns:
      (valid_rows_count, warnings)
    """
    df = normalize_plasmid_fusions_table(df_raw)
    warnings: List[str] = []
    valid = 0

    for row in df.to_dict(orient="records"):
        pcode = row["plasmid_base_code"]
        fluor = row["fluor"]
        tag = row["tag"]

        pid = cx.execute(
            text("SELECT id FROM public.plasmids WHERE code = :c LIMIT 1"),
            {"c": pcode},
        ).scalar()
        if not pid:
            warnings.append(f"Plasmid fusion row skipped: plasmid '{pcode}' not found.")
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
            warnings.append(f"Plasmid fusion row skipped: fluor '{fluor}' not found.")
            continue

        tid = cx.execute(
            text("SELECT id FROM public.tags WHERE tag_name = :c LIMIT 1"),
            {"c": tag},
        ).scalar()
        if not tid:
            warnings.append(f"Plasmid fusion row skipped: tag '{tag}' not found.")
            continue

        valid += 1

    return valid, warnings
