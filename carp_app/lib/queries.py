from __future__ import annotations
from pathlib import Path
from importlib.machinery import SourceFileLoader

# Load project-local supabase/queries.py under a unique module name to avoid clashes
ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "supabase" / "queries.py"
_local = SourceFileLoader("carp_local_queries", str(MODULE_PATH)).load_module()

# Re-export public symbols
for _k in dir(_local):
    if not _k.startswith("_"):
        globals()[_k] = getattr(_local, _k)
