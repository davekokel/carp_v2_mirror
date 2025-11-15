from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID

# --- Nickname & placeholder helpers (copied from upload_csv_fish) ------------

_NUMERIC_NICK_RE = re.compile(r"^\d+(?:\.0+)?$")

def _is_numeric_nick(s: str | None) -> bool:
    return bool(_NUMERIC_NICK_RE.fullmatch((s or "").strip()))

_PLACEHOLDER_NICKS = {"", "unknown", "unk", "n/a", "na", "?", "-", "none"}

def _norm_allele_nick(s: str | None) -> str:
    v = (s or "").strip()
    return "" if v.lower() in _PLACEHOLDER_NICKS or _is_numeric_nick(v) else v

# zygosity normalizer
_ZYG_MAP = {
    "het": "het",
    "hetero": "het",
    "heterozygous": "het",
    "h": "het",
    "hom": "hom",
    "homo": "hom",
    "homozygous": "hom",
    "unk": "unk",
    "unknown": "unk",
    "?": "unk",
    "na": "unk",
    "n/a": "unk",
    "none": "unk",
    "": "",
}

def _norm_zygosity(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return _ZYG_MAP.get(str(s).strip().lower(), None) or None

# base-36 short code from UUID (lower 40 bits)
def _uuid_to_base36_8(uuid_str: str) -> str:
    import uuid as _uuid
    alpha = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    try:
        n = _uuid.UUID(str(uuid_str)).int & ((1 << 40) - 1)
    except Exception:
        return "FSH-????????"
    out: List[str] = []
    for _ in range(8):
        out.append(alpha[n % 36])
        n //= 36
    return "FSH-" + "".join(reversed(out))

# Excel numeric dates → date
def _parse_birthday(x) -> Optional[date]:
    if x is None or str(x).strip() == "":
        return None
    s = str(x).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        y, m, d = map(int, s.split("-"))
        return date(y, m, d)
    if re.fullmatch(r"\d{8}", s):
        y, m, d = int(s[:4]), int(s[4:6]), int(s[6:8])
        return date(y, m, d)
    try:
        n = float(s)
        if not math.isnan(n):
            return date(1899, 12, 30) + timedelta(days=int(n))
    except Exception:
        pass
    try:
        from dateutil import parser
        return parser.parse(s).date()
    except Exception:
        return None

# table existence / function existence / base-code check ----------------------

def _table_exists(cx: Connection, schema: str, table: str) -> bool:
    q = text(
        """
      SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema=:s AND table_name=:t
    )"""
    )
    return bool(cx.execute(q, {"s": schema, "t": table}).scalar())

def _fn_exists(cx: Connection, schema: str, name: str) -> bool:
    q = text(
        """
        SELECT EXISTS(
          SELECT 1 FROM pg_proc p
          JOIN pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname=:s AND p.proname=:n
        )
    """
    )
    return bool(cx.execute(q, {"s": schema, "n": name}).scalar())

def _is_valid_transgene_base(cx: Connection, base: str) -> bool:
    if not base:
        return False
    if cx.execute(
        text("select 1 from public.transgenes where transgene_base_code=:b limit 1"),
        {"b": base},
    ).scalar():
        return True
    if _table_exists(cx, "public", "plasmids"):
        if cx.execute(
            text("select 1 from public.plasmids where code=:b limit 1"), {"b": base}
        ).scalar():
            return True
    return False

# header aliases / normalization / identity key --------------------------------

ALIASES: Dict[str, List[str]] = {
    "birthday": ["birthday", "dob", "date_birth", "date of birth"],
    "genetic_background": ["genetic_background", "background", "bg", "strain"],
    "in_breeding_stage": [
        "in_breeding_stage",
        "line_building_stage",
        "lb_stage",
        "stage",
        "line_stage",
    ],
    "tg_base_code": [
        "tg_base_code",
        "transgene_base_code",
        "base_code",
        "tg_base",
        "transgene_base",
        "plasmid_code",
        "plasmid_base_code",
    ],
    "ft_code": ["ft_code", "mix_code", "treatment_code"],
    "allele_nickname": ["allele_nickname", "allele_nick", "allele_name", "allele"],
    "zygosity": ["zygosity", "zyg", "allele_zygosity"],
    "nickname": ["nickname", "nick", "name"],
    "description": ["description", "desc", "notes", "note"],
    "fluor_code": ["fluor", "fluor_code", "fluorname"],
    "tag_code": ["tag", "tag_code", "tagname"],
    "dye_code": ["dye", "dye_code", "dyename"],
    "ft_text": ["ft_text", "treatment_text", "mix_text"],
}

def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [("" if c is None else str(c)).strip().lower() for c in df.columns]
    ren: Dict[str, str] = {}
    for want, variants in ALIASES.items():
        if want in df.columns:
            continue
        for v in variants:
            if v in df.columns:
                ren[v] = want
                break
    if ren:
        df = df.rename(columns=ren)
    return df

def _identity_key(row: pd.Series) -> str:
    bday = row.get("birthday")
    if isinstance(bday, (pd.Timestamp,)):
        bstr = bday.date().isoformat()
    elif isinstance(bday, date):
        bstr = bday.isoformat()
    else:
        bstr = str(bday or "").strip()
    base = (str(row.get("tg_base_code") or "").strip())
    parts = [
        bstr,
        str(row.get("genetic_background") or "").strip(),
        str(row.get("in_breeding_stage") or "").strip(),
        base,
        str(row.get("allele_nickname") or "").strip(),
        str(row.get("nickname") or "").strip(),
    ]
    return " | ".join(parts)

# upsert fish / allele (function or fallback) ---------------------------------

def _upsert_fish(
    cx: Connection,
    *,
    birthday: date,
    genetic_background: str,
    in_breeding_stage: str,
    nickname: Optional[str],
    description: Optional[str],
    identity_key: str,
    seed_batch_id: str = "",
    actor_email: Optional[str] = None,
) -> Dict[str, Any]:
    if _fn_exists(cx, "public", "upsert_fish_by_identity"):
        q = text(
            """
          SELECT * FROM public.upsert_fish_by_identity(
            :p_seed_batch_id, :p_identity_key, :p_bday, :p_name_human,
            :p_bg, :p_nick, :p_stage, :p_desc, :p_notes, :p_by
          )
        """
        )
        return dict(
            cx.execute(
                q,
                {
                    "p_seed_batch_id": seed_batch_id,
                    "p_identity_key": identity_key,
                    "p_bday": birthday,
                    "p_name_human": None,
                    "p_bg": (genetic_background or None),
                    "p_nick": (nickname or None),
                    "p_stage": (in_breeding_stage or None),
                    "p_desc": (description or None),
                    "p_notes": None,
                    "p_by": actor_email,
                },
            ).mappings().first()
            or {}
        )

    cx.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    ihash_sql = text("SELECT encode(digest(:s,'hex'),'hex')")
    identity_hash = cx.execute(ihash_sql, {"s": identity_key}).scalar()

    found = cx.execute(
        text(
            """
        SELECT id, fish_code FROM public.fish
        WHERE identity_hash = :h OR identity_key = :k
        LIMIT 1
    """
        ),
        {"h": identity_hash, "k": identity_key},
    ).mappings().first()
    if found:
        return dict(found)

    row = cx.execute(
        text(
            """
        WITH new_id AS (SELECT gen_random_uuid() AS id)
        INSERT INTO public.fish
        (id, fish_code, birthday, genetic_background, in_breeding_stage,
         nickname, description, identity_key, identity_hash, created_at)
        SELECT
          nid.id,
          public.uuid_base36_8(nid.id),
          :bday, NULLIF(:bg,''), NULLIF(:stg,''),
          NULLIF(:nick,''), NULLIF(:desc,''), :ikey, :ihash, now()
        FROM new_id nid
        RETURNING id, fish_code
    """
        ),
        {
            "bday": birthday,
            "bg": genetic_background,
            "stg": in_breeding_stage,
            "nick": nickname or "",
            "desc": description or "",
            "ikey": identity_key,
            "ihash": identity_hash,
        },
    ).mappings().first()
    return dict(row or {})

def _upsert_allele(cx: Connection, base_code: str, csv_nickname: str) -> Optional[Dict[str, Any]]:
    base = (base_code or "").strip()
    nick = _norm_allele_nick(csv_nickname)
    if not base:
        return None

    with cx.begin_nested():
        try:
            cx.execute(
                text(
                    "INSERT INTO public.transgenes(transgene_base_code) VALUES (:b) ON CONFLICT DO NOTHING"
                ),
                {"b": base},
            )
        except Exception:
            return None

        if nick:
            got = cx.execute(
                text(
                    """
                SELECT transgene_base_code, allele_number, allele_name, allele_nickname
                FROM public.transgene_alleles
                WHERE transgene_base_code = :b
                  AND lower(allele_nickname) = lower(:n)
                LIMIT 1
            """
                ),
                {"b": base, "n": nick},
            ).mappings().first()
            if got:
                return dict(got)

        cx.execute(
            text(
                """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE c.relkind='S' AND n.nspname='public' AND c.relname='transgene_allele_global'
              ) THEN
                CREATE SEQUENCE public."transgene_allele_global";
              END IF;
            END$$;
        """
            )
        )

        while True:
            new_no = cx.execute(
                text('SELECT nextval(\'public."transgene_allele_global"\')::int')
            ).scalar()
            gu = f"gu{new_no}"
            ins = cx.execute(
                text(
                    """
                INSERT INTO public.transgene_alleles
                  (transgene_base_code, allele_number, allele_name, allele_nickname)
                VALUES (:b, :n, :aname, :nnick)
                ON CONFLICT DO NOTHING
                RETURNING transgene_base_code, allele_number, allele_name, allele_nickname
            """
                ),
                {"b": base, "n": new_no, "aname": gu, "nnick": (nick or gu)},
            ).mappings().first()
            if ins:
                return dict(ins)

# prepare df (normalize headers, parse birthday, strip text, identity_key) -----

def prepare_fish_df(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = _normalize_headers(df_raw)

    # required columns
    if "birthday" not in df.columns:
        raise ValueError("Missing required column: birthday")

    # normalize fields
    df["birthday"] = df["birthday"].apply(_parse_birthday)
    if df["birthday"].isna().any():
        raise ValueError("One or more rows have invalid `birthday` values.")

    for c in [
        "genetic_background",
        "in_breeding_stage",
        "tg_base_code",
        "ft_code",
        "allele_nickname",
        "zygosity",
        "nickname",
        "description",
        "fluor_code",
        "tag_code",
        "dye_code",
        "ft_text",
    ]:
        if c in df.columns:
            df[c] = df[c].apply(lambda v: "" if v is None else str(v).strip())

    df["identity_key"] = df.apply(_identity_key, axis=1)
    return df

# main loader ---------------------------------------------------------------

def load_fish_from_df(
    df_raw: pd.DataFrame,
    cx: Connection,
    seed_batch_id: str = "",
    actor_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Load fish + allele links + tanks from a DataFrame.

    Returns a summary dict:
      {
        "rows": int,
        "fish_upserts": int,
        "allele_links": int,
        "tanks_ensured": int,
        "inserted": [ ... ],
        "linked_rows": [ ... ],
        "created_tanks": [ ... ],
        "warnings": [str, ...],
      }
    """
    df = prepare_fish_df(df_raw)

    inserted: List[Dict[str, Any]] = []
    linked_rows: List[Dict[str, Any]] = []
    created_tanks: List[str] = []
    warnings: List[str] = []
    reused = 0

    # main loop copied from upload_csv_fish (without Streamlit calls)
    for r in df.itertuples(index=False):
        birthday = r.birthday
        bg = getattr(r, "genetic_background", "") or ""
        stage = getattr(r, "in_breeding_stage", "") or ""
        nick = getattr(r, "nickname", "") or ""
        desc = getattr(r, "description", "") or ""
        base = (getattr(r, "tg_base_code", "") or "").strip()
        csv_nick = _norm_allele_nick(getattr(r, "allele_nickname", ""))
        zyg = _norm_zygosity(getattr(r, "zygosity", ""))
        ident = getattr(r, "identity_key")

        try:
            # one transaction per row
            with cx.begin_nested():
                # upsert fish
                got = _upsert_fish(
                    cx,
                    birthday=birthday,
                    genetic_background=bg,
                    in_breeding_stage=stage,
                    nickname=nick or None,
                    description=desc or None,
                    identity_key=ident,
                    seed_batch_id=seed_batch_id,
                    actor_email=actor_email,
                )
                if not got:
                    raise RuntimeError("upsert_fish returned no row")

                fid = got.get("id")
                fcode_raw = got.get("fish_code")
                if fid is None or not fcode_raw:
                    raise RuntimeError("missing fish id/code")

                inserted.append(
                    {"fish_id": str(fid), "fish_code": fcode_raw, "identity_key": ident}
                )
                if list(df["identity_key"]).count(ident) > 1:
                    reused += 1

                # allele link only if base exists
                if base and _is_valid_transgene_base(cx, base):
                    up = _upsert_allele(cx, base, csv_nick)
                    if up:
                        cx.execute(
                            text(
                                """
                        INSERT INTO public.join_fish_transgene_alleles
                          (fish_id, transgene_base_code, allele_number, zygosity)
                        VALUES (:fid, :b, :n, :zyg)
                        ON CONFLICT (fish_id, transgene_base_code, allele_number)
                        DO UPDATE SET zygosity =
                           COALESCE(EXCLUDED.zygosity, public.join_fish_transgene_alleles.zygosity)
                    """
                            ),
                            {
                                "fid": fid,
                                "b": up["transgene_base_code"],
                                "n": up["allele_number"],
                                "zyg": zyg,
                            },
                        )
                        linked_rows.append(
                            {
                                "fish_code": fcode_raw,
                                "transgene_base_code": up["transgene_base_code"],
                                "allele_nickname": up.get("allele_nickname"),
                                "allele_number": up["allele_number"],
                                "allele_name": up["allele_name"],
                                "zygosity": zyg or "",
                            }
                        )
                elif base:
                    warnings.append(
                        f"Skipped allele link for {ident}: '{base}' not found in plasmids/transgenes."
                    )

                # ensure active tank TANK(FSH-XXXXXXXX)#1
                fshort = _uuid_to_base36_8(fid)
                tcode = f"TANK({fshort})#1"

                # update existing tank to point to this fish if needed
                cx.execute(
                    text(
                        """
                UPDATE public.tanks
                    SET fish_id = :fid
                WHERE tank_code = :tc
                    AND (fish_id IS NULL OR fish_id <> :fid)
                """
                    ),
                    {"tc": tcode, "fid": fid},
                )

                # insert if missing
                ins = cx.execute(
                    text(
                        """
                INSERT INTO public.tanks (tank_code, fish_id, status)
                SELECT :tc, :fid, 'active'
                WHERE NOT EXISTS (SELECT 1 FROM public.tanks WHERE tank_code = :tc)
                """
                    ),
                    {"tc": tcode, "fid": fid},
                ).rowcount

                if ins:
                    created_tanks.append(tcode)

        except Exception as ex:
            warnings.append(f"Skipping row (transaction rolled back): {ident} -> {ex}")
            continue

    return {
        "rows": len(df),
        "fish_upserts": len(inserted),
        "allele_links": len(linked_rows),
        "tanks_ensured": len(created_tanks),
        "inserted": inserted,
        "linked_rows": linked_rows,
        "created_tanks": created_tanks,
        "warnings": warnings,
        "reused_identity_keys": reused,
    }
