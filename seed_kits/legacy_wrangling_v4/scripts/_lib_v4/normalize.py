from __future__ import annotations

import re
import pandas as pd

RE_WS = re.compile(r"\s+")
EXP_KEY_RE = re.compile(r"(20\d{6}[_-][A-Za-z0-9][A-Za-z0-9_-]*)")

NULLISH = {"", "nan", "none", "na", "n/a", "<na>"}

def nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, float) and pd.isna(x):
        return False
    s = str(x).strip()
    return s != "" and s.lower() not in NULLISH

def clean_str(x) -> str:
    if x is None:
        return ""
    s = str(x).replace("¬†", " ").replace("\u00a0", " ")
    s = RE_WS.sub(" ", s).strip()
    return s

def win_to_posix_path(s: str) -> str:
    t = clean_str(s)
    if not t:
        return ""
    t = t.replace("\\", "/")
    t = re.sub(r"^[A-Za-z]:", "", t)
    t = re.sub(r"/+", "/", t)
    if t and not t.startswith("/"):
        t = "/" + t
    return t

def to_cluster_path_from_any(s: str, cluster_prefix: str = "/clusterfs/vast/abcabc/") -> str:
    t = win_to_posix_path(s)
    if not t:
        return ""
    if t.startswith(cluster_prefix):
        return t
    m = re.search(r"/abcabc/(Aang_Foundation|Korra_Foundation)/(.+)$", t)
    if m:
        return cluster_prefix + m.group(1) + "/" + m.group(2)
    m2 = re.search(r"/(Aang_Foundation|Korra_Foundation)/(.+)$", t)
    if m2:
        return cluster_prefix + m2.group(1) + "/" + m2.group(2)
    return ""

def foundation_guess_from_location(s: str) -> str | None:
    t = win_to_posix_path(s)
    if "Aang_Foundation" in t:
        return "aang"
    if "Korra_Foundation" in t:
        return "korra"
    return None

def experiment_key_guess_from_location(s: str) -> str | None:
    t = win_to_posix_path(s)
    m = EXP_KEY_RE.search(t or "")
    return m.group(1) if m else None
