from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from carp_app.pipelines.construct_tokens import canonicalize_token, TokenError


class FishImportError(RuntimeError):
    pass


REQ_TRANSGENICS = [
    "line_nickname",
    "birthday",
    "genetic_background",
    "instance_stage",
    "transgene_base_code",
    "allele_nickname",
    "zygosity",
    "created_by",
    "description",
]

REQ_TREATED = [
    "line_nickname",
    "birthday",
    "genetic_background",
    "instance_stage",
    "treatment_basecode",
    "transgene_basecode",
    "allele_nickname",
    "zygosity",
    "created_by",
    "enzyme",
    "description",
]


def _nonempty(x: Any) -> bool:
    if x is None:
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")


def _require_cols(df: pd.DataFrame, required: List[str], path: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise FishImportError(f"{path}: missing required columns: {missing}")


def _norm_date(s: Any, field: str, path: str) -> str:
    if not _nonempty(s):
        raise FishImportError(f"{path}: {field} is required")
    dt = pd.to_datetime([s], errors="coerce")[0]
    if pd.isna(dt):
        raise FishImportError(f"{path}: invalid date in {field}: {s!r}")
    return dt.strftime("%Y-%m-%d")


def _norm_token(s: Any, field: str, path: str) -> str:
    if not _nonempty(s):
        raise FishImportError(f"{path}: {field} is required")
    try:
        return canonicalize_token(str(s))
    except TokenError as e:
        raise FishImportError(f"{path}: invalid {field}: {s!r} ({e})") from e

def _norm_transgene_base_code(v, field: str, path: str) -> str:
    t = _norm_token(v, field, path)
    t = str(t).strip().lower()
    if t.startswith("swin-") or t.startswith("swin"):
        t = re.sub(r"^swin", "pswin", t)
    return t


def _norm_allele_number(allele_nickname: Any, path: str) -> int:
    if not _nonempty(allele_nickname):
        raise FishImportError(f"{path}: allele_nickname is required")
    s = str(allele_nickname).strip()
    if not s.isdigit():
        raise FishImportError(f"{path}: allele_nickname must be an integer string (got {allele_nickname!r})")
    return int(s)


def _norm_string(s: Any) -> Optional[str]:
    return str(s).strip() if _nonempty(s) else None


def load_fish_transgenics_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    _require_cols(df, REQ_TRANSGENICS, path)

    out = pd.DataFrame()
    out["line_nickname"] = df["line_nickname"].astype(str).str.strip()
    out["birthday"] = df["birthday"].apply(lambda v: _norm_date(v, "birthday", path))
    out["genetic_background"] = df["genetic_background"].astype(str).str.strip()
    out["instance_stage"] = df["instance_stage"].astype(str).str.strip()

    out["transgene_base_code"] = df["transgene_base_code"].apply(lambda v: _norm_transgene_base_code(v, "transgene_base_code", path))
    out["allele_number"] = df["allele_nickname"].apply(lambda v: _norm_allele_number(v, path))
    out["zygosity"] = df["zygosity"].astype(str).str.strip()

    out["created_by"] = df["created_by"].astype(str).str.strip()
    out["description"] = df["description"].apply(_norm_string)

    return out


def load_fish_treated_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    _require_cols(df, REQ_TREATED, path)

    out = pd.DataFrame()
    out["line_nickname"] = df["line_nickname"].astype(str).str.strip()
    out["birthday"] = df["birthday"].apply(lambda v: _norm_date(v, "birthday", path))
    out["genetic_background"] = df["genetic_background"].astype(str).str.strip()
    out["instance_stage"] = df["instance_stage"].astype(str).str.strip()

    out["treatment_basecode"] = df["treatment_basecode"].apply(lambda v: _norm_token(v, "treatment_basecode", path))
    out["transgene_base_code"] = df["transgene_basecode"].apply(lambda v: _norm_transgene_base_code(v, "transgene_basecode", path))
    out["allele_number"] = df["allele_nickname"].apply(lambda v: _norm_allele_number(v, path))
    out["zygosity"] = df["zygosity"].astype(str).str.strip()

    out["enzyme"] = df["enzyme"].apply(_norm_string)
    out["created_by"] = df["created_by"].astype(str).str.strip()
    out["description"] = df["description"].apply(_norm_string)

    return out
