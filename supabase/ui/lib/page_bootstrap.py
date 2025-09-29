# supabase/ui/lib/page_bootstrap.py
from lib.authz import require_app_access, read_only_banner, logout_button
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def secure_page(title: str | None = "🔐 CARP — Private", show_logout: bool = True) -> None:
    """Call at the very top of any Streamlit page."""
    require_app_access(title or "🔐 CARP — Private")
    read_only_banner()
    if show_logout:
        logout_button("sidebar")