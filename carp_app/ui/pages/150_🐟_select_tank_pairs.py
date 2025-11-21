# carp_app/ui/pages/150_🐟_select_tank_pairs.py
from __future__ import annotations
import sys, pathlib, os, uuid
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text

# ---- path/auth bootstrap ----------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...

from carp_app.ui.lib.page_engine import engine

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — 🧬 Select tank pairings", page_icon="🧬", layout="wide")
st.title("🧬 Select tank pairings")

FISH_TABLE = "fish_instance"  # canonical fish table in this schema

# ------------------ strict verification helpers ------------------------------
def _cols(schema: str, table: str) -> List[str]:
    with engine().begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema=:s AND table_name=:t
                ORDER BY ordinal_position
                """
            ),
            cx,
            params={"s": schema, "t": table},
        )
    return df["column_name"].tolist()


def _assert_table(schema: str, table: str):
    with engine().begin() as cx:
        df = pd.read_sql(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema=:s AND table_name=:t
                """
            ),
            cx,
            params={"s": schema, "t": table},
        )
    if df.empty:
        raise RuntimeError(f"Required table {schema}.{table} is missing.")


def _assert_cols(schema: str, table: str, required: List[str]):
    have = set(_cols(schema, table))
    miss = [c for c in required if c not in have]
    if miss:
        raise RuntimeError(f"{schema}.{table} missing required columns {miss}. Found: {sorted(have)}")


def _tank_pair_parent_cols() -> Tuple[str, str]:
    tp = _cols("public", "tank_pairs")
    for a, b in (("mother_tank_id", "father_tank_id"), ("tank_id_mother", "tank_id_father")):
        if a in tp and b in tp:
            return a, b
    raise RuntimeError(
        "public.tank_pairs must have mother/father UUID columns. "
        f"Expected (mother_tank_id,father_tank_id) or (tank_id_mother,tank_id_father). Found: {tp}"
    )


def _discover_tanks_fish_fk_col() -> str:
    """
    Return the column in public.tanks that FK-references public.fish_instance(id).
    Require exactly one such column; error if 0 or >1.
    """
    sql = text(
        """
        WITH fk AS (
          SELECT
            con.oid,
            con.conrelid  AS tbl_oid,
            con.confrelid AS ref_oid,
            con.conkey    AS fk_cols
          FROM pg_constraint con
          WHERE con.contype='f'
            AND con.conrelid='public.tanks'::regclass
            AND con.confrelid='public.fish_instance'::regclass
        )
        SELECT a.attname AS fk_col
        FROM fk
        JOIN LATERAL unnest(fk.fk_cols) WITH ORDINALITY k(attnum, ord) ON TRUE
        JOIN pg_attribute a ON a.attrelid=fk.tbl_oid AND a.attnum=k.attnum
        ORDER BY ord
        """
    )
    with engine().begin() as cx:
        df = pd.read_sql(sql, cx)

    if df.empty:
        raise RuntimeError(
            "No foreign key from public.tanks to public.fish_instance(id) was found. "
            "Expected exactly one FK column in public.tanks that references public.fish_instance(id)."
        )
    cols = df["fk_col"].astype(str).tolist()
    uniq = sorted(set(cols))
    if len(uniq) != 1:
        raise RuntimeError(
            "Multiple FK columns in public.tanks reference public.fish_instance(id); refusing to choose. "
            f"Columns: {uniq}"
        )
    return uniq[0]


def _verify_core_schema() -> dict:
    # Tables must exist
    for t in (FISH_TABLE, "tanks", "tank_pairs", "join_fish_transgene_alleles", "transgene_alleles"):
        _assert_table("public", t)

    # tanks requirements
    _assert_cols("public", "tanks", ["id", "tank_code", "status", "created_at"])
    tanks_cols = _cols("public", "tanks")
    fish_fk_col = _discover_tanks_fish_fk_col()
    if fish_fk_col not in tanks_cols:
        raise RuntimeError(
            f"FK column '{fish_fk_col}' referenced by constraint is not a column of public.tanks?! Found: {tanks_cols}"
        )

    # fish requirements (stage can be either of two exact names)
    _assert_cols("public", FISH_TABLE, ["id", "fish_code", "nickname", "genetic_background", "created_at"])
    fish_cols = _cols("public", FISH_TABLE)
    if "line_building_stage" not in fish_cols:
        raise RuntimeError(
            f"public.{FISH_TABLE} must include 'line_building_stage'. "
            f"Found: {fish_cols}"
        )
    stage_col = "line_building_stage"

    # genotype linkage
    _assert_cols(
        "public",
        "join_fish_transgene_alleles",
        ["fish_id", "transgene_base_code", "allele_number"],
    )
    alle_cols = _cols("public", "transgene_alleles")
    for c in ["transgene_base_code", "allele_number"]:
        if c not in alle_cols:
            raise RuntimeError(f"public.transgene_alleles missing required column '{c}'. Found: {alle_cols}")

    # tank_pairs parent columns
    mom_col, dad_col = _tank_pair_parent_cols()

    return {
        "tanks": {"id": "id", "code": "tank_code", "status": "status", "created": "created_at", "fish_fk": fish_fk_col},
        "fish": {
            "table": FISH_TABLE,
            "id": "id",
            "code": "fish_code",
            "nickname": "nickname",
            "bg": "genetic_background",
            "stage": stage_col,
            "created": "created_at",
        },
        "tank_pairs": {"mom": mom_col, "dad": dad_col},
    }


# ------------------ queries (no views, no fallbacks) -------------------------
@st.cache_data(show_spinner=False)
def search_fish(q: Optional[str], limit: int) -> pd.DataFrame:
    S = _verify_core_schema()
    t, f = S["tanks"], S["fish"]
    f_tbl = f["table"]

    sql = text(
        f"""
        WITH gp AS (
          SELECT
            f.{f['code']} AS fish_code,
            COALESCE(
              string_agg(
                DISTINCT jfta.transgene_base_code || '(' ||
                  COALESCE(NULLIF(ta.allele_name,''), ta.allele_number::text) || ')',
                ', ' ORDER BY jfta.transgene_base_code || '(' || COALESCE(NULLIF(ta.allele_name,''), ta.allele_number::text) || ')'
              ), ''
            ) AS genotype_pretty
          FROM public.{f_tbl} f
          LEFT JOIN public.join_fish_transgene_alleles jfta
            ON jfta.fish_id = f.{f['id']}
          LEFT JOIN public.transgene_alleles ta
            ON ta.transgene_base_code = jfta.transgene_base_code
           AND ta.allele_number       = jfta.allele_number
          GROUP BY f.{f['code']}
        ),
        base AS (
          SELECT
            f.{f['code']}               AS fish_code,
            f.{f['nickname']}           AS nickname,
            COALESCE(f.{f['bg']},'')    AS genetic_background,
            COALESCE(f.{f['stage']},'') AS stage,
            COALESCE(gp.genotype_pretty,'') AS genotype_pretty,
            f.{f['created']}            AS created_at
          FROM public.{f_tbl} f
          LEFT JOIN gp ON gp.fish_code = f.{f['code']}
          WHERE (:q IS NULL)
             OR (
                  f.{f['code']}                  ILIKE :ql
               OR COALESCE(f.{f['nickname']},'') ILIKE :ql
               OR COALESCE(f.{f['bg']},'')       ILIKE :ql
               OR COALESCE(f.{f['stage']},'')    ILIKE :ql
               OR COALESCE(gp.genotype_pretty,'')ILIKE :ql
             )
          ORDER BY f.{f['created']} DESC NULLS LAST, f.{f['code']}
          LIMIT :lim
        ),
        live AS (
          SELECT
            f2.{f['code']} AS fish_code,
            COUNT(*)::int  AS n_live,
            STRING_AGG(DISTINCT t.{t['code']}, ', ' ORDER BY t.{t['code']}) AS live_tank_codes
          FROM public.tanks t
          JOIN public.{f_tbl} f2 ON f2.{f['id']} = t.{t['fish_fk']}
          WHERE lower(trim(t.{t['status']}))='active'
          GROUP BY f2.{f['code']}
        )
        SELECT
          b.fish_code,
          b.nickname                        AS name,
          b.genetic_background              AS background,
          b.stage                           AS stage,
          b.genotype_pretty                 AS genotype,
          COALESCE(l.n_live,0)              AS live_tanks,
          COALESCE(l.live_tank_codes,'')    AS live_tank_codes
        FROM base b
        LEFT JOIN live l USING (fish_code)
        """
    )

    qnorm = (q or "").strip()
    params = {
        "q": (qnorm if qnorm else None),
        "ql": (f"%{qnorm}%" if qnorm else None),
        "lim": int(limit),
    }
    with engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df


def load_active_tanks_for_fish(codes: List[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame()

    S = _verify_core_schema()
    t, f = S["tanks"], S["fish"]
    f_tbl = f["table"]

    sql = text(
        f"""
        SELECT
          f2.{f['code']}                  AS fish_code,
          COALESCE(f2.{f['nickname']},'') AS fish_name,
          gp.genotype_pretty              AS genotype,
          t.{t['code']}                   AS tank_code,
          t.{t['id']}::text               AS tank_id,
          t.{t['status']}                 AS status,
          t.{t['created']}                AS created_at
        FROM public.tanks t
        JOIN public.{f_tbl} f2 ON f2.{f['id']} = t.{t['fish_fk']}
        LEFT JOIN (
          SELECT
            f3.{f['code']} AS fish_code,
            COALESCE(
              string_agg(
                DISTINCT j2.transgene_base_code || '(' ||
                  COALESCE(NULLIF(ta2.allele_name,''), ta2.allele_number::text) || ')',
                ', ' ORDER BY j2.transgene_base_code || '(' || COALESCE(NULLIF(ta2.allele_name,''), ta2.allele_number::text) || ')'
              ), ''
            ) AS genotype_pretty
          FROM public.{f_tbl} f3
          LEFT JOIN public.join_fish_transgene_alleles j2
            ON j2.fish_id = f3.{f['id']}
          LEFT JOIN public.transgene_alleles ta2
            ON ta2.transgene_base_code = j2.transgene_base_code
           AND ta2.allele_number       = j2.allele_number
          GROUP BY f3.{f['code']}
        ) gp ON gp.fish_code = f2.{f['code']}
        WHERE f2.{f['code']} = ANY(:codes)
          AND lower(trim(t.{t['status']}))='active'
        ORDER BY f2.{f['code']}, t.{t['created']} DESC NULLS LAST
        """
    )
    with engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    return df.fillna("")


def upsert_tank_pair(mother_tank_id: str, father_tank_id: str, created_by: str, note: str):
    """
    If a tank pair (mother, father) already exists, update metadata and return its code.
    Otherwise, insert a new row with:
      id             = generated UUID
      tank_pair_code = 'TP-' || first 8 chars of that UUID
    """
    mom_col, dad_col = _tank_pair_parent_cols()

    with engine().begin() as cx:
        cols = set(_cols("public", "tank_pairs"))

        # 1) Check if this pair already exists
        row = pd.read_sql(
            text(
                f"""
                SELECT id::text, tank_pair_code
                FROM public.tank_pairs
                WHERE {mom_col} = :m AND {dad_col} = :d
                LIMIT 1
                """
            ),
            cx,
            params={"m": mother_tank_id, "d": father_tank_id},
        )

        if not row.empty:
            sets = []
            params = {"id": row.iloc[0]["id"], "note": note, "by": created_by}
            if "updated_at" in cols:
                sets.append("updated_at = now()")
            if "note" in cols:
                sets.append("note = COALESCE(NULLIF(:note,''), note)")
            if "updated_by" in cols:
                sets.append("updated_by = COALESCE(NULLIF(:by,''), updated_by)")
            if sets:
                cx.execute(
                    text(f"UPDATE public.tank_pairs SET {', '.join(sets)} WHERE id = :id::uuid"),
                    params,
                )
            return False, str(row.iloc[0]["tank_pair_code"])

        # 2) Build INSERT for a new pair, explicitly setting id and tank_pair_code
        new_id = str(uuid.uuid4())
        new_code = f"TP-{new_id[:8]}"

        insert_cols = ["id", mom_col, dad_col]
        placeholders = [":id", ":m", ":d"]
        params = {"id": new_id, "m": mother_tank_id, "d": father_tank_id}

        if "created_by" in cols:
            insert_cols.append("created_by")
            placeholders.append(":by")
            params["by"] = created_by
        if "note" in cols:
            insert_cols.append("note")
            placeholders.append(":note")
            params["note"] = note
        if "status" in cols:
            insert_cols.append("status")
            placeholders.append(":st")
            params["st"] = "selected"
        if "created_at" in cols:
            insert_cols.append("created_at")
            placeholders.append("now()")

        insert_cols.append("tank_pair_code")
        placeholders.append(":tp_code")
        params["tp_code"] = new_code

        sql = text(
            """
            INSERT INTO public.tank_pairs(
                id,
                mother_tank_id,
                father_tank_id,
                active_from,
                created_at,
                tank_pair_code
            )
            VALUES (
                :id,
                :m,
                :d,
                now(),
                now(),
                :tp_code
            )
            RETURNING tank_pair_code
            """
        )
        tp_code_db = cx.execute(sql, params).scalar()
        return True, str(tp_code_db)


# ------------------ UI -------------------------------------------------------
with st.form("filters"):
    c1, c2 = st.columns([3, 1])
    with c1:
        q = st.text_input("Filter by code / nickname / background / genotype", "")
    with c2:
        limit = int(st.number_input("Rows", 1, 2000, 500, 50))
    st.form_submit_button("Apply")

df = search_fish(q, limit)
if df.empty:
    st.info("No fish match filters.")
    st.stop()

# Step 1 — pick two parent fish
st.subheader("Step 1 — Select parents (from fish registry)")
view = df.copy()
view.insert(0, "✓ Parent", False)
pick = st.data_editor(
    view,
    key="parent_table",
    width="stretch",
    hide_index=True,
    column_config={
        "✓ Parent": st.column_config.CheckboxColumn("✓", default=False),
        "fish_code": st.column_config.TextColumn("fish_code", disabled=True),
        "name": st.column_config.TextColumn("name", disabled=True),
        "background": st.column_config.TextColumn("background", disabled=True),
        "stage": st.column_config.TextColumn("stage", disabled=True),
        "genotype": st.column_config.TextColumn("genotype", disabled=True),
        "live_tanks": st.column_config.NumberColumn("live tanks"),
        "live_tank_codes": st.column_config.TextColumn("live tank codes", disabled=True),
    },
)

parents = pick.loc[pick["✓ Parent"], "fish_code"].dropna().astype(str).tolist() if not pick.empty else []
parents = list(dict.fromkeys(parents))[:2]
if len(parents) < 2:
    st.info("Select two parents above to continue.")
    st.stop()

st.success(f"Selected parents: {parents[0]} × {parents[1]}")

# Step 2 — load both parents' active tanks
st.subheader("Step 2 — Choose Mother and Father tanks (active only)")
live = load_active_tanks_for_fish(parents)
if live.empty:
    st.warning("No active tanks for selected parents.")
    st.stop()

# Mother candidates = ALL active tanks for BOTH fish
st.subheader("Mother")
m_candidates = live.copy()
m_candidates.insert(0, "✓ Mother", False)
m_sel = st.data_editor(
    m_candidates[
        ["✓ Mother", "fish_code", "fish_name", "genotype", "tank_code", "tank_id", "status", "created_at"]
    ],
    key="mother_table",
    width="stretch",
    hide_index=True,
)
m_pick = m_sel.loc[m_sel["✓ Mother"]] if not m_sel.empty else pd.DataFrame()
if m_pick.empty:
    st.info("Pick a Mother tank to continue.")
    st.stop()

mother_row = m_pick.iloc[0]
mother_fish = str(mother_row["fish_code"])
mother_tank_id = str(mother_row["tank_id"])

# Father candidates = ALL remaining active tanks for the OTHER fish
other_fish = next(f for f in parents if f != mother_fish)
f_candidates = live[live["fish_code"] == other_fish].copy()
if f_candidates.empty:
    st.warning(f"No active tanks for father fish {other_fish}.")
    st.stop()

st.subheader("Father")
f_candidates.insert(0, "✓ Father", False)
f_sel = st.data_editor(
    f_candidates[
        ["✓ Father", "fish_code", "fish_name", "genotype", "tank_code", "tank_id", "status", "created_at"]
    ],
    key="father_table",
    width="stretch",
    hide_index=True,
)
f_pick = f_sel.loc[f_sel["✓ Father"]] if not f_sel.empty else pd.DataFrame()
if f_pick.empty:
    st.info("Pick a Father tank to continue.")
    st.stop()

father_tank_id = str(f_pick.iloc[0]["tank_id"])
if mother_tank_id == father_tank_id:
    st.error("Mother and Father cannot be the same tank.")
    st.stop()

# Step 3 — save pairing
st.subheader("Step 3 — Save tank pairing")
creator = os.getenv("USER") or os.getenv("USERNAME") or "unknown"
note = st.text_input("Note (optional)", "")

if st.button("💾 Save tank pairing", type="primary", use_container_width=True):
    ok, code = upsert_tank_pair(mother_tank_id, father_tank_id, creator, note)
    st.success(f"{'Created' if ok else 'Updated'} tank_pair {code}")