# carp_app/ui/pages/008_📤_upload_csv_fish.py
from __future__ import annotations

import io, os, sys, re, math, pathlib
from datetime import date, timedelta
from typing import Optional, List, Dict, Any

import pandas as pd
import streamlit as st
import uuid
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.engine import Engine

# repo root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# auth / engine
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine
from carp_app.lib.time import utc_now

# ──────────────────────────── Page / Auth ────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Upload Fish from CSV", page_icon="🐟", layout="wide")
st.title("🐟 Upload Fish from CSV — Forward Links & Alleles")

# ────────────────────────── Engine / Utilities ───────────────────────
_ENGINE: Optional[Engine] = None
def _eng() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        if not os.getenv("DB_URL"):
            raise RuntimeError("DB_URL is not set")
        _ENGINE = get_engine()
    return _ENGINE

# ────────────────────────── Nickname & Placeholder Helpers ───────────────────────
_NUMERIC_NICK_RE = re.compile(r"^\d+(?:\.0+)?$")

def _is_numeric_nick(s: str | None) -> bool:
    return bool(_NUMERIC_NICK_RE.fullmatch((s or "").strip()))

_PLACEHOLDER_NICKS = {"", "unknown", "unk", "n/a", "na", "?", "-", "none"}
def _norm_allele_nick(s: str | None) -> str:
    v = (s or "").strip()
    return "" if v.lower() in _PLACEHOLDER_NICKS or _is_numeric_nick(v) else v

def _fn_exists(cx, schema: str, name: str) -> bool:
    q = text("""
        SELECT EXISTS(
          SELECT 1 FROM pg_proc p
          JOIN pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname=:s AND p.proname=:n
        )
    """)
    return bool(cx.execute(q, {"s": schema, "n": name}).scalar())

def _is_valid_transgene_base(cx, base: str) -> bool:
    if not base:
        return False
    if cx.execute(text("select 1 from public.transgenes where transgene_base_code=:b limit 1"), {"b": base}).scalar():
        return True
    if _table_exists(cx, "public", "plasmids"):
        if cx.execute(text("select 1 from public.plasmids where code=:b limit 1"), {"b": base}).scalar():
            return True
    return False

def _table_exists(cx, schema: str, table: str) -> bool:
    q = text("""
      SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema=:s AND table_name=:t
    )""")
    return bool(cx.execute(q, {"s": schema, "t": table}).scalar())

# base-36 short code from UUID (lower 40 bits)
def _uuid_to_base36_8(uuid_str: str) -> str:
    import uuid as _uuid
    alpha = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    try:
        n = _uuid.UUID(str(uuid_str)).int & ((1 << 40) - 1)
    except Exception:
        return "FSH-????????"
    out = []
    for _ in range(8):
        out.append(alpha[n % 36])
        n //= 36
    return "FSH-" + "".join(reversed(out))

# zygosity normalizer
_ZYG_MAP = {
    "het":"het","hetero":"het","heterozygous":"het","h":"het",
    "hom":"hom","homo":"hom","homozygous":"hom",
    "unk":"unk","unknown":"unk","?":"unk","na":"unk","n/a":"unk","none":"unk","":""
}
def _norm_zygosity(s: Optional[str]) -> Optional[str]:
    if not s: return None
    return _ZYG_MAP.get(str(s).strip().lower(), None) or None

# Excel numeric dates → date
def _parse_birthday(x) -> Optional[date]:
    if x is None or str(x).strip() == "":
        return None
    s = str(x).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        y, m, d = map(int, s.split("-")); return date(y, m, d)
    if re.fullmatch(r"\d{8}", s):
        y, m, d = int(s[:4]), int(s[4:6]), int(s[6:8]); return date(y, m, d)
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

# ──────────────────────────── File Reader ────────────────────────────
def _read_table(uploaded) -> pd.DataFrame:
    raw = io.BytesIO(uploaded.getvalue())
    name = (uploaded.name or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        xls = pd.ExcelFile(raw)
        sheet = st.selectbox("Worksheet", xls.sheet_names, index=0)
        tmp = pd.read_excel(xls, sheet_name=sheet, header=None, dtype=object)
        tmp = tmp.applymap(lambda v: None if (v is ... or (isinstance(v, float) and math.isnan(v))) else v)
        header_row = None
        for i in range(min(20, len(tmp))):
            vals = [("" if v is None else str(v)).strip() for v in tmp.iloc[i].tolist()]
            if sum(bool(v) for v in vals) >= max(2, int(len(vals)*0.5)) and not all(v.lower().startswith("unnamed") for v in vals if v):
                header_row = i; break
        if header_row is None:
            st.error("Could not detect header row. Ensure first non-empty row contains column names.")
            st.stop()
        cols = [("" if v is None else str(v)).strip().lower() for v in tmp.iloc[header_row].tolist()]
        df = tmp.iloc[header_row+1:].copy()
        df.columns = cols
        df = df.loc[:, [c for c in df.columns if c and not str(c).lower().startswith("unnamed")]]
        df = df.reset_index(drop=True)
        return df
    else:
        df = pd.read_csv(raw, dtype=object)
        df = df.applymap(lambda v: None if (v is ... ) else v)
        return df

# ─────────────────────── Column mapping / identity ───────────────────
ALIASES: Dict[str, List[str]] = {
    "birthday": ["birthday","dob","date_birth","date of birth"],
    "genetic_background": ["genetic_background","background","bg","strain"],
    "in_breeding_stage": ["in_breeding_stage","line_building_stage","lb_stage","stage","line_stage"],
    "tg_base_code": ["tg_base_code","transgene_base_code","base_code","tg_base","transgene_base","plasmid_code","plasmid_base_code"],
    "ft_code": ["ft_code","mix_code","treatment_code"],
    "allele_nickname": ["allele_nickname","allele_nick","allele_name","allele"],
    "zygosity": ["zygosity","zyg","allele_zygosity"],
    "nickname": ["nickname","nick","name"],
    "description": ["description","desc","notes","note"],
    "fluor_code": ["fluor","fluor_code","fluorname"],
    "tag_code": ["tag","tag_code","tagname"],
    "dye_code": ["dye","dye_code","dyename"],
    "ft_text": ["ft_text","treatment_text","mix_text"],
}

def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [("" if c is None else str(c)).strip().lower() for c in df.columns]
    ren: Dict[str,str] = {}
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

# ─────────────── Upsert fish (function if present; else fallback) ────────────
def _upsert_fish(
    cx, *, birthday: date, genetic_background: str, in_breeding_stage: str,
    nickname: Optional[str], description: Optional[str],
    identity_key: str
) -> Dict[str, Any]:
    if _fn_exists(cx, "public", "upsert_fish_by_identity"):
        q = text("""
          SELECT * FROM public.upsert_fish_by_identity(
            :p_seed_batch_id, :p_identity_key, :p_bday, :p_name_human,
            :p_bg, :p_nick, :p_stage, :p_desc, :p_notes, :p_by
          )
        """)
        return (cx.execute(q, {
            "p_seed_batch_id": st.session_state.get("fish_seed_batch", ""),
            "p_identity_key":  identity_key,
            "p_bday":          birthday,
            "p_name_human":    None,
            "p_bg":            (genetic_background or None),
            "p_nick":          (nickname or None),
            "p_stage":         (in_breeding_stage or None),
            "p_desc":          (description or None),
            "p_notes":         None,
            "p_by":            (getattr(user, "email", None) or os.environ.get("USER") or None),
        }).mappings().first() or {})
    # Fallback
    cx.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    ihash_sql = text("SELECT encode(digest(:s,'sha256'),'hex')")
    identity_hash = cx.execute(ihash_sql, {"s": identity_key}).scalar()

    found = cx.execute(text("""
        SELECT id, fish_code FROM public.fish
        WHERE identity_hash = :h OR identity_key = :k
        LIMIT 1
    """), {"h": identity_hash, "k": identity_key}).mappings().first()
    if found:
        return dict(found)

    row = cx.execute(text("""
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
    """), {
        "bday": birthday, "bg": genetic_background, "stg": in_breeding_stage,
        "nick": nickname or "", "desc": description or "",
        "ikey": identity_key, "ihash": identity_hash
    }).mappings().first()
    return dict(row or {})

# ─────────── upsert allele via function; fallback emulation if missing ───────
def _upsert_allele(cx, base_code: str, csv_nickname: str) -> Optional[Dict[str, Any]]:
    base = (base_code or "").strip()
    nick = _norm_allele_nick(csv_nickname)
    if not base:
        return None

    # open a nested transaction to isolate any internal error
    with cx.begin_nested():
        try:
            cx.execute(text("INSERT INTO public.transgenes(transgene_base_code) VALUES (:b) ON CONFLICT DO NOTHING"), {"b": base})
        except Exception:
            # skip if the transgenes insert fails
            return None

        if nick:
            got = cx.execute(text("""
                SELECT transgene_base_code, allele_number, allele_name, allele_nickname
                FROM public.transgene_alleles
                WHERE transgene_base_code = :b
                  AND lower(allele_nickname) = lower(:n)
                LIMIT 1
            """), {"b": base, "n": nick}).mappings().first()
            if got:
                return dict(got)

        cx.execute(text("""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE c.relkind='S' AND n.nspname='public' AND c.relname='transgene_allele_global'
              ) THEN
                CREATE SEQUENCE public."transgene_allele_global";
              END IF;
            END$$;
        """))

        while True:
            new_no = cx.execute(text('SELECT nextval(\'public."transgene_allele_global"\')::int')).scalar()
            gu = f"gu{new_no}"
            ins = cx.execute(text("""
                INSERT INTO public.transgene_alleles
                  (transgene_base_code, allele_number, allele_name, allele_nickname)
                VALUES (:b, :n, :aname, :nnick)
                ON CONFLICT DO NOTHING
                RETURNING transgene_base_code, allele_number, allele_name, allele_nickname
            """), {"b": base, "n": new_no, "aname": gu, "nnick": (nick or gu)}).mappings().first()
            if ins:
                return dict(ins)

# format identity key for preview
def _fmt_identity(row: pd.Series) -> str:
    return _identity_key(row)

# ─────────────────────────────── UI: Upload ──────────────────────────
st.caption("CSV/XLSX columns — **required**: `birthday`; **recommended**: `tg_base_code` or `ft_code`, `allele_nickname`, `in_breeding_stage`, `genetic_background`, `nickname`. Nicknames are treated **as strings**.")

uploaded = st.file_uploader("Choose fish CSV/XLSX", type=["csv","xlsx","xls"])
if not uploaded:
    st.info("Select a file to begin.")
    st.stop()

st.session_state["fish_seed_batch"] = pathlib.Path(uploaded.name).stem

try:
    df = _read_table(uploaded)
except Exception as e:
    st.error(f"Failed to read file: {e}")
    st.stop()

df = _normalize_headers(df)

required = ["birthday"]
missing = [c for c in required if c not in df.columns]
if missing:
    st.error("Missing required column(s): " + ", ".join(missing))
    st.stop()

# normalize fields
df["birthday"] = df["birthday"].apply(_parse_birthday)
if df["birthday"].isna().any():
    st.error("One or more rows have invalid `birthday` values.")
    st.stop()

for c in ["genetic_background","in_breeding_stage","tg_base_code","ft_code",
          "allele_nickname","zygosity","nickname","description",
          "fluor_code","tag_code","dye_code","ft_text"]:
    if c in df.columns:
        df[c] = df[c].apply(lambda v: "" if v is None else str(v).strip())

df["identity_key"] = df.apply(_identity_key, axis=1)

st.subheader("Preview (first 30 rows)")
show_cols = [c for c in ["birthday","genetic_background","in_breeding_stage","tg_base_code","ft_code","allele_nickname","zygosity","nickname","description"] if c in df.columns]
preview = df[["identity_key"] + show_cols].head(30)
st.dataframe(preview, width="stretch", hide_index=True)
st.caption(f"{len(df)} rows detected")

if not st.button("Process upload", type="primary"):
    st.stop()

# ───────────────────────── Process rows (per-row transactions) ─────────────────
inserted: List[Dict[str,Any]] = []
linked_rows: List[Dict[str,Any]] = []
created_tanks: List[str] = []
reused = 0

for r in df.itertuples(index=False):
    birthday = r.birthday
    bg       = getattr(r, "genetic_background", "") or ""
    stage    = getattr(r, "in_breeding_stage", "") or ""
    nick     = getattr(r, "nickname", "") or ""
    desc     = getattr(r, "description", "") or ""
    base     = (getattr(r, "tg_base_code", "") or "").strip()
    csv_nick = _norm_allele_nick(getattr(r, "allele_nickname", ""))
    zyg      = _norm_zygosity(getattr(r, "zygosity", ""))
    ident    = getattr(r, "identity_key")

    try:
        with _eng().begin() as cx:
            # upsert fish (function or fallback)
            got = _upsert_fish(
                cx,
                birthday=birthday,
                genetic_background=bg,
                in_breeding_stage=stage,
                nickname=nick or None,
                description=desc or None,
                identity_key=ident,
            )
            if not got:
                raise RuntimeError("upsert_fish returned no row")

            fid = got.get("id")
            fcode_raw = got.get("fish_code")
            if fid is None or not fcode_raw:
                raise RuntimeError("missing fish id/code")

            inserted.append({"fish_id": str(fid), "fish_code": fcode_raw, "identity_key": ident})
            if df["identity_key"].tolist().count(ident) > 1:
                reused += 1

            # allele link only if base exists in transgenes/plasmids
            if base and _is_valid_transgene_base(cx, base):
                up = _upsert_allele(cx, base, csv_nick)
                if up:
                    cx.execute(text("""
                        INSERT INTO public.join_fish_transgene_alleles
                          (fish_id, transgene_base_code, allele_number, zygosity)
                        VALUES (:fid, :b, :n, :zyg)
                        ON CONFLICT (fish_id, transgene_base_code, allele_number)
                        DO UPDATE SET zygosity =
                           COALESCE(EXCLUDED.zygosity, public.join_fish_transgene_alleles.zygosity)
                    """), {"fid": fid, "b": up["transgene_base_code"], "n": up["allele_number"], "zyg": zyg})
                    linked_rows.append({
                        "fish_code": fcode_raw,
                        "transgene_base_code": up["transgene_base_code"],
                        "allele_nickname": up.get("allele_nickname"),
                        "allele_number": up["allele_number"],
                        "allele_name": up["allele_name"],
                        "zygosity": zyg or "",
                    })
            elif base:
                st.info(f"Skipped allele link for {ident}: '{base}' not found in plasmids/transgenes.")

            # ensure active tank TANK(FSH-XXXXXXXX)#1, owned by this fish
            fshort = _uuid_to_base36_8(fid)
            tcode = f"TANK({fshort})#1"

            # 1) if a row already exists for this tank_code, make sure it points to this fish
            cx.execute(
                text("""
                UPDATE public.tanks
                    SET fish_id = :fid
                WHERE tank_code = :tc
                    AND (fish_id IS NULL OR fish_id <> :fid)
                """),
                {"tc": tcode, "fid": fid}
            )

            # 2) if it still doesn't exist, create it with fish_id
            ins = cx.execute(
                text("""
                INSERT INTO public.tanks (tank_code, fish_id, status)
                SELECT :tc, :fid, 'active'
                WHERE NOT EXISTS (SELECT 1 FROM public.tanks WHERE tank_code = :tc)
                """),
                {"tc": tcode, "fid": fid}
            ).rowcount

            if ins:
                created_tanks.append(tcode)

    except Exception as ex:
        st.warning(f"Skipping row (transaction rolled back): {ident}\n{ex}")
        continue

# ───────────────────────────── Summary / Output ──────────────────────
st.success(f"Completed. Processed {len(df)} rows. Fish upserts: {len(inserted)}. Allele links: {len(linked_rows)}. Tanks ensured: {len(created_tanks)}.")

# --- Verification: show the fish we just touched ---
if inserted:
    fish_ids = [uuid.UUID(str(row["fish_id"])) for row in inserted]
    if fish_ids:
        with _eng().begin() as cx:
            sql = text("""
                SELECT
                  f.fish_code,
                  f.birthday,
                  COALESCE(f.genetic_background,'')  AS genetic_background,
                  COALESCE(f.in_breeding_stage,'')   AS in_breeding_stage,
                  COALESCE(f.nickname,'')            AS nickname,
                  jfta.transgene_base_code,
                  ta.allele_number,
                  COALESCE(ta.allele_name,'')        AS allele_name,
                  COALESCE(ta.allele_nickname,'')    AS allele_name_override,
                  COALESCE(jfta.zygosity,'')         AS zygosity
                FROM public.fish f
                LEFT JOIN public.join_fish_transgene_alleles jfta
                  ON jfta.fish_id = f.id
                LEFT JOIN public.transgene_alleles ta
                  ON ta.transgene_base_code = jfta.transgene_base_code
                 AND ta.allele_number       = jfta.allele_number
                WHERE f.id = ANY(:ids)
                ORDER BY f.fish_code, jfta.transgene_base_code, ta.allele_number
            """).bindparams(bindparam("ids", type_=ARRAY(UUID(as_uuid=True))))

            preview = pd.read_sql(sql, cx, params={"ids": fish_ids})

        st.subheader("Verification (fish + allele links)")
        st.dataframe(preview, width="stretch", hide_index=True)

        st.download_button(
            "⬇︎ Download linked alleles (CSV)",
            data=preview.to_csv(index=False).encode("utf-8"),
            file_name=f"fish_alleles_linked_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
            type="secondary",
            width="stretch",
        )

# tanks preview
if created_tanks:
    tanks_df = pd.DataFrame({"tank_code": created_tanks})
    st.subheader("Tanks ensured (this run)")
    st.dataframe(tanks_df, width="stretch", hide_index=True)
    st.download_button(
        "⬇︎ Download ensured tanks (CSV)",
        data=tanks_df.to_csv(index=False).encode("utf-8"),
        file_name=f"fish_tanks_ensured_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
        type="secondary",
        width="stretch",
    )

# result export
if inserted:
    out_df = pd.DataFrame(inserted)
    st.subheader("Fish upserts (this run)")
    st.dataframe(out_df, width="stretch", hide_index=True)
    st.download_button(
        "⬇︎ Download fish upserts (CSV)",
        data=out_df.to_csv(index=False).encode("utf-8"),
        file_name=f"fish_upserts_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
        type="secondary",
        width="stretch",
    )