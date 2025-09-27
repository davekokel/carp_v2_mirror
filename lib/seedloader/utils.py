from datetime import datetime
import math
import re
from typing import List, Optional, Set

import pandas as pd
import streamlit as st


# --------- generic cleaning ---------
def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.where(pd.notna(df), None)
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: None if v is None else str(v).strip())
    return df

def parse_date(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s or s.lower() == "nan":
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None

def blank(x) -> str:
    if x is None:
        return ""
    if isinstance(x, float):
        try:
            if math.isnan(x):
                return ""
        except Exception:
            pass
    s = str(x).strip()
    return "" if s.lower() == "nan" else s

def none_if_blank(x):
    s = blank(x)
    return None if s == "" else s


# --------- strict validation helpers ---------
def canon_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [re.sub(r"\s+", "_", c.strip().lower()) for c in df.columns]
    return df

def _fail(msg: str):
    st.error(msg)
    st.stop()

def require_headers(
    df: pd.DataFrame,
    required: Set[str],
    optional: Set[str] = set(),
    forbidden: Set[str] = set(),
    label: str = "file",
):
    cols = set(df.columns)
    miss = required - cols
    forb = cols & forbidden
    if miss:
        _fail(f"❌ {label}: missing required column(s): {sorted(miss)}")
    if forb:
        _fail(f"❌ {label}: forbidden column(s) present: {sorted(forb)}")
    # If you want to reject unknown columns too, uncomment:
    # extra = cols - required - optional - forbidden
    # if extra:
    #     _fail(f"❌ {label}: unknown column(s): {sorted(extra)}")

def assert_unique(df: pd.DataFrame, cols: List[str], label: str):
    dups = df.duplicated(subset=cols, keep=False)
    if dups.any():
        sample = df.loc[dups, cols].head(10).to_dict(orient="records")
        _fail(f"❌ {label}: duplicate keys in {cols}. Sample rows: {sample}")

def must_subset(left: pd.Series, right: pd.Series, label: str, keys_name="keys"):
    missing = sorted(set(left.dropna()) - set(right.dropna()))
    if missing:
        _fail(
            f"❌ {label}: {keys_name} not found in reference file: "
            f"{missing[:10]}{' …' if len(missing) > 10 else ''}"
        )


# --------- misc small helpers ---------
def derive_batch_id(zip_filename: str) -> str:
    m = re.search(r"\d{4}-\d{2}-\d{2}-\d{4}", zip_filename)
    base = m.group(0) if m else re.sub(r"\.zip$", "", zip_filename).split("/")[-1]
    return base