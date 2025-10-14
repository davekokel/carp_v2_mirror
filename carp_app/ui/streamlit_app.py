from __future__ import annotations
import importlib.util, pathlib, re, streamlit as st

ROOT = pathlib.Path(__file__).resolve().parents[3]
CARP_PAGES = ROOT / "carp_app" / "ui" / "pages"
FALLBACK_SUPA_PAGES = ROOT / "supabase" / "ui" / "pages"

def _exec_file(pyfile: pathlib.Path):
    spec = importlib.util.spec_from_file_location(pyfile.stem, str(pyfile))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    fn = getattr(mod, "main", None) or getattr(mod, "run", None)
    if callable(fn):
        fn()

def _pick_welcome(pages_dir: pathlib.Path) -> pathlib.Path | None:
    if not pages_dir.exists():
        return None
    cand = sorted(pages_dir.glob("*.py"))
    # prefer any *welcome*.py
    w = [p for p in cand if re.search("welcome", p.stem, re.IGNORECASE)]
    if w:
        return w[0]
    # else first 000_* file
    z = [p for p in cand if p.name.startswith("000_")]
    if z:
        return z[0]
    return cand[0] if cand else None

st.set_page_config(page_title="streamlit app", page_icon="👋", layout="wide")

target = _pick_welcome(CARP_PAGES) or _pick_welcome(FALLBACK_SUPA_PAGES)

if target and target.exists():
    _exec_file(target)
else:
    st.title("streamlit app")
    st.warning("No pages found in carp_app/ui/pages or supabase/ui/pages.")
