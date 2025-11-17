from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

def get_engine_from_env(env_var: str = "DB_URL") -> Engine:
    url = os.getenv(env_var, "").strip()
    if not url:
        raise RuntimeError(
            f"{env_var} is not set. Source scripts/use_db.sh and run use_local/use_staging first."
        )
    return create_engine(url)

_GENERIC_CODE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*?)-?0*(\d+)$")

def normalize_base_code(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return s
    m = _GENERIC_CODE_RE.match(s)
    if m:
        prefix, digits = m.groups()
        return f"{prefix.upper()}-{int(digits)}"
    return s

def _load_csv_normalized(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df
