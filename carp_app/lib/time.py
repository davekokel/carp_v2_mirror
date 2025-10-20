from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd

UTC = timezone.utc

def utc_now() -> datetime:
    return datetime.now(tz=UTC)

def utc_today() -> pd.Timestamp.date:
    return pd.Timestamp.now(tz="UTC").date()

def now_in(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))

def to_tz(ts, tz_name: str) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.tz_convert(ZoneInfo(tz_name))
