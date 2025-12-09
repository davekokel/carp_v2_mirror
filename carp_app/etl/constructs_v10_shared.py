from __future__ import annotations

import math
from typing import Any, Dict, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from carp_app.etl.construct_normalizer import normalize_construct_code


def _norm(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip()


def _norm_optional(s: Any) -> Optional[str]:
    if s is None:
        return None
    if isinstance(s, float) and math.isnan(s):
        return None
    s2 = str(s).strip()
    if not s2 or s2.lower() == "nan":
        return None
    return s2


def _as_bool_flag(v: Any) -> bool:
    s = str(v).strip().lower()
    if not s:
        return False
    return s in {"1", "true", "t", "yes", "y"}


_REQUIRED_COLS = [
    "plasmid_code",
    "plasmid_nickname",
    "resistance",
    "plasmid_notes",
    "used_for_injection_plasmid",
    "used_for_injection_rna",
    "used_for_injection_crispr",
]


_SQL_UPSERT = text(
    """
    INSERT INTO public.constructs (
      construct_code,
      base_code,
      construct_kind,
      construct_name,
      resistance,
      plasmid_notes,
      description,
      injection_use_plasmid,
      injection_use_rna,
      injection_use_crispr,
      created_at
    )
    VALUES (
      :construct_code,
      :base_code,
      :construct_kind,
      :construct_name,
      :resistance,
      :plasmid_notes,
      :description,
      :use_plasmid,
      :use_rna,
      :use_crispr,
      now()
    )
    ON CONFLICT (construct_code) DO UPDATE SET
      construct_name          = EXCLUDED.construct_name,
      resistance              = EXCLUDED.resistance,
      plasmid_notes           = EXCLUDED.plasmid_notes,
      description             = EXCLUDED.description,
      injection_use_plasmid   = public.constructs.injection_use_plasmid
                                 OR EXCLUDED.injection_use_plasmid,
      injection_use_rna       = public.constructs.injection_use_rna
                                 OR EXCLUDED.injection_use_rna,
      injection_use_crispr    = public.constructs.injection_use_crispr
                                 OR EXCLUDED.injection_use_crispr
    ;
    """
)


def load_constructs_from_df(df: pd.DataFrame, cx: Connection) -> Dict[str, Any]:
    missing = [c for c in _REQUIRED_COLS if c not in df.columns]
    if missing:
        raise RuntimeError(
            f"[v10_load_constructs] missing required column(s): {missing}"
        )

    df = df.copy()
    df["plasmid_code"] = df["plasmid_code"].astype("string").fillna("").str.strip()

    base = (
        df.sort_values("plasmid_code")
        .groupby("plasmid_code", as_index=False)
        .first()
    )

    upserted = 0
    rejected: list[Dict[str, Any]] = []

    for _, row in base.iterrows():
        raw_code = _norm(row["plasmid_code"])
        if not raw_code:
            continue

        construct_kind = "plasmid"

        canonical = normalize_construct_code(raw_code)
        if not canonical:
            rejected.append(
                {
                    "plasmid_code": raw_code,
                    "_error": "could not normalize construct_code",
                }
            )
            continue

        base_code = canonical

        nickname = _norm_optional(row.get("plasmid_nickname"))
        construct_name = nickname

        resistance = _norm_optional(row.get("resistance"))
        plasmid_notes = _norm_optional(row.get("plasmid_notes"))
        description = plasmid_notes

        use_plasmid = _as_bool_flag(row.get("used_for_injection_plasmid"))
        use_rna = _as_bool_flag(row.get("used_for_injection_rna"))
        use_crispr = _as_bool_flag(row.get("used_for_injection_crispr"))

        cx.execute(
            _SQL_UPSERT,
            {
                "construct_code": canonical,
                "base_code": base_code,
                "construct_kind": construct_kind,
                "construct_name": construct_name,
                "resistance": resistance,
                "plasmid_notes": plasmid_notes,
                "description": description,
                "use_plasmid": use_plasmid,
                "use_rna": use_rna,
                "use_crispr": use_crispr,
            },
        )
        upserted += 1

    rejected_df = pd.DataFrame(rejected) if rejected else None

    return {
        "n_csv_rows": int(len(df)),
        "n_base_rows": int(len(base)),
        "n_upserted": int(upserted),
        "n_rejected": int(len(rejected)),
        "rejected_rows": rejected_df,
    }
