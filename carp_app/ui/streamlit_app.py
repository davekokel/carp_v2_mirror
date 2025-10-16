import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

from __future__ import annotations
import sys; print("BOOT: streamlit_app start", flush=True)
import importlib.util
import pathlib
import re
import streamlit as st

# repo root = .../carp_v2
ROOT = pathlib.Path(__file__).resolve().parents[2]
PAGES = ROOT / "carp_app" / "ui" / "pages"

def _exec(pyfile: pathlib.Path) -> None:
    spec = importlib.util.spec_from_file_location(pyfile.stem, str(pyfile))
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    fn = getattr(mod, "main", None) or getattr(mod, "run", None)
    if callable(fn):
        fn()

def _pick_welcome() -> pathlib.Path | None:
    if not PAGES.exists():
        return None
    files = sorted(PAGES.glob("*.py"))
    if not files:
        return None
    # 1) prefer any *welcome*.py (case-insensitive)
    for p in files:
        if re.search("welcome", p.stem, re.IGNORECASE):
            return p
    # 2) else prefer a numbered landing page
    for p in files:
        if p.name.startswith("000_"):
            return p
    # 3) else first file
    return files[0]

st.set_page_config(page_title="CARP", page_icon="👋", layout="wide")

target = _pick_welcome()
if target and target.exists():
    _exec(target)
else:
    st.title("CARP")
    if not PAGES.exists():
        st.warning("No pages folder found at carp_app/ui/pages.")
    else:
        names = [p.name for p in sorted(PAGES.glob("*.py"))]
        if names:
            st.info("Found pages but couldn’t select a welcome file:")
            st.write(names)
        else:
            st.warning("No .py files in carp_app/ui/pages.")
