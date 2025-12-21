from __future__ import annotations

import os
from typing import List, Dict, Any, Tuple

import pandas as pd
from sqlalchemy import create_engine, text


def _norm(x: object) -> str:
    if x is None:
        return ""
    return str(x).strip()


def main() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise SystemExit("[STOP] DB_URL is not set")

    eng = create_engine(db_url)

    with eng.begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT
                  id::text AS construct_id,
                  code,
                  base_code,
                  legacy_base_code,
                  construct_code
                FROM public.constructs
                """
            ),
            cx,
        )

        rows: List[Dict[str, Any]] = []
        for _, r in df.iterrows():
            cid = _norm(r.get("construct_id"))
            if not cid:
                continue

            candidates: List[Tuple[str, str]] = [
                ("code", _norm(r.get("code"))),
                ("base_code", _norm(r.get("base_code"))),
                ("legacy_base_code", _norm(r.get("legacy_base_code"))),
                ("construct_code", _norm(r.get("construct_code"))),
            ]

            seen: set[str] = set()
            for kind, alias in candidates:
                if not alias:
                    continue
                key = alias.lower()
                if key in seen:
                    continue
                seen.add(key)
                rows.append({"construct_id": cid, "alias": alias, "alias_kind": kind})

        cx.execute(text("DELETE FROM public.construct_aliases;"))
        if rows:
            cx.execute(
                text(
                    """
                    INSERT INTO public.construct_aliases (construct_id, alias, alias_kind)
                    VALUES (:construct_id, :alias, :alias_kind)
                    """
                ),
                rows,
            )

        n_alias = cx.execute(text("SELECT count(*) FROM public.construct_aliases")).scalar()
        n_kind = cx.execute(text("SELECT count(distinct alias_kind) FROM public.construct_aliases")).scalar()

    print(f"[OK] construct_aliases inserted={int(n_alias or 0)} distinct_kinds={int(n_kind or 0)}")


if __name__ == "__main__":
    main()
