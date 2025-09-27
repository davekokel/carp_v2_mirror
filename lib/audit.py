from typing import Any, Dict, Optional
from sqlalchemy import text
from sqlalchemy.engine import Engine, Connection

def log_event(conn: Connection | Engine, page: str, action: str, meta: Optional[Dict[str, Any]] = None) -> None:
    """Fire-and-forget audit insert; never crash the app if it fails."""
    try:
        sql = text("insert into public.audit_events(actor,page,action,meta) values (current_user, :page, :action, :meta)")
        if hasattr(conn, "begin"):  # Engine
            with conn.begin() as cx:
                cx.execute(sql, {"page": page, "action": action, "meta": meta})
        else:  # Connection
            conn.execute(sql, {"page": page, "action": action, "meta": meta})
    except Exception:
        # swallow: audits must not break UX
        pass
