from __future__ import annotations

import re
from typing import Iterable, List, Dict

from sqlalchemy import text
from sqlalchemy.engine import Engine


TOKEN_SPLIT_RE = re.compile(r"[|;,+ ]+")


class TokenError(RuntimeError):
    pass


def split_tokens(raw: str) -> List[str]:
    if raw is None:
        return []
    s = str(raw).strip()
    if not s:
        return []
    return [t for t in TOKEN_SPLIT_RE.split(s) if t]


def canonicalize_token(tok: str) -> str:
    t = str(tok).strip().lower()
    if not t:
        raise TokenError(f"invalid construct token: {tok!r}")

    m = re.fullmatch(r"([a-z]+)(?:-)?0*([0-9]+)", t)
    if m:
        return f"{m.group(1)}-{int(m.group(2))}"

    raise TokenError(f"invalid construct token: {tok!r}")

def canonicalize_tokens(raw: str) -> List[str]:
    return [canonicalize_token(t) for t in split_tokens(raw)]


def resolve_construct_ids(engine: Engine, canonical_tokens: Iterable[str]) -> Dict[str, str]:
    toks = sorted(set(str(t).strip().lower() for t in canonical_tokens if str(t).strip()))
    if not toks:
        return {}

    with engine.begin() as cx:
        cx.execute(text("DROP TABLE IF EXISTS _tmp_construct_tokens"))
        cx.execute(text("CREATE TEMP TABLE _tmp_construct_tokens (base_code text PRIMARY KEY) ON COMMIT DROP"))
        cx.execute(
            text("INSERT INTO _tmp_construct_tokens (base_code) VALUES (:t) ON CONFLICT DO NOTHING"),
            [{"t": t} for t in toks],
        )

        rows = cx.execute(
            text(
                '''
                SELECT t.base_code, c.id::text
                FROM _tmp_construct_tokens t
                LEFT JOIN public.constructs c
                  ON lower(c.base_code) = t.base_code
                '''
            )
        ).fetchall()

    found = {r[0]: r[1] for r in rows if r[1] is not None}
    missing = [t for t in toks if t not in found]
    if missing:
        raise TokenError(f"unresolved construct tokens: {missing}")

    return found


