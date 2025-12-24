from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

CLUSTER_PREFIX_DEFAULT = "/clusterfs/vast/abcabc/"

RE_WS = re.compile(r"\s+")
ROI_ROOT_RE = re.compile(r"^(Aang_Foundation|Korra_Foundation)/(\d{8}[^/]+)/(.+)$")
FISH_RE = re.compile(r"^(fish[^_/]+)", re.IGNORECASE)

EXP_KEY_RE = re.compile(r"(20\d{6}[_-][A-Za-z0-9][A-Za-z0-9_-]*)")


def nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    if x is pd.NA:
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in ("nan", "none", "na", "n/a", "<na>")


def clean_str(x) -> str:
    if x is None or x is pd.NA:
        return ""
    if isinstance(x, float) and pd.isna(x):
        return ""
    s = str(x).replace("¬†", " ").replace("\u00a0", " ")
    s = RE_WS.sub(" ", s).strip()
    if s.lower() in ("nan", "none", "na", "n/a", "<na>"):
        return ""
    return s


def dataset_from_foundation(foundation_long: str) -> Optional[str]:
    s = str(foundation_long or "")
    if "Aang_Foundation" in s:
        return "aang"
    if "Korra_Foundation" in s:
        return "korra"
    return None


def iso_from_yyyymmdd(yyyymmdd: str) -> Optional[str]:
    try:
        dt = pd.to_datetime(str(yyyymmdd), format="%Y%m%d", errors="raise").date()
        return dt.isoformat()
    except Exception:
        return None


def fish_from_roi_name(roi_name: str) -> Optional[str]:
    if not roi_name:
        return None
    m = FISH_RE.match(str(roi_name).strip())
    return m.group(1) if m else None


def strip_cluster_prefix(p: str, cluster_prefix: str = CLUSTER_PREFIX_DEFAULT) -> str:
    s = clean_str(p)
    if s.startswith(cluster_prefix):
        s = s[len(cluster_prefix):]
    s = s.lstrip("./")
    return s


def win_to_posix_path(x: object) -> str:
    t = clean_str(x)
    if not t:
        return ""
    t = t.replace("\\", "/")
    t = re.sub(r"^[A-Za-z]:", "", t)
    t = re.sub(r"/+", "/", t)
    if t and not t.startswith("/"):
        t = "/" + t
    return t


def to_cluster_path_from_any(x: object, cluster_prefix: str = CLUSTER_PREFIX_DEFAULT) -> str:
    t = win_to_posix_path(x)
    if not t:
        return ""
    if cluster_prefix in t:
        return t
    m = re.search(r"/abcabc/(Aang_Foundation|Korra_Foundation)/(.+)$", t)
    if m:
        return cluster_prefix + m.group(1) + "/" + m.group(2)
    m2 = re.search(r"/(Aang_Foundation|Korra_Foundation)/(.+)$", t)
    if m2:
        return cluster_prefix + m2.group(1) + "/" + m2.group(2)
    return ""


def foundation_guess_from_location(x: object) -> str | None:
    t = win_to_posix_path(x)
    if not t:
        return None
    if "Aang_Foundation" in t:
        return "aang"
    if "Korra_Foundation" in t:
        return "korra"
    return None


def experiment_key_guess_from_location(x: object) -> str | None:
    t = win_to_posix_path(x)
    if not t:
        return None
    m = EXP_KEY_RE.search(t)
    return m.group(1) if m else None
