# carp_app/ui/pages/170_🔎_overview_tank_pairs.py
from __future__ import annotations

import sys, pathlib
from typing import Tuple, Set, Dict, Any
import pandas as pd
import streamlit as st
from sqlalchemy import text

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
from carp_app.ui.lib.page_engine import engine

# ── Auth / page ──────────────────────────────────────────────────────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — 🔎 Overview: Tank pairs", page_icon="🔎", layout="wide")
st.title("🔎 Overview: Tank pairs")

# sanity caption
with engine().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# ── schema helpers ───────────────────────────────────────────────────────────
def _cols(schema: str, rel: str) -> Set[str]:
    with engine().begin() as cx:
        df = pd.read_sql(
            text("""
              select column_name
              from information_schema.columns
              where table_schema=:s and table_name=:r
            """),
            cx, params={"s": schema, "r": rel}
        )
    return set(df["column_name"].tolist())

def _rel_exists(schema: str, name: str) -> bool:
    with engine().begin() as cx:
        n = pd.read_sql(
            text("""
              select count(*)::int n from (
                select 1 from information_schema.tables where table_schema=:s and table_name=:n
                union all
                select 1 from information_schema.views  where table_schema=:s and table_name=:n
              ) z
            """),
            cx, params={"s": schema, "n": name}
        )["n"][0]
    return n > 0

def _tank_pair_parent_cols() -> Tuple[str, str]:
    c = _cols("public", "tank_pairs")
    for a, b in (("mother_tank_id","father_tank_id"),
                 ("tank_id_mother","tank_id_father")):
        if a in c and b in c:
            return a, b
    raise RuntimeError("public.tank_pairs must have parent UUID columns (mother_tank_id/father_tank_id or tank_id_mother/tank_id_father).")

# verify required relations
if not _rel_exists("public","tank_pairs"):
    st.error("public.tank_pairs not found."); st.stop()
if not _rel_exists("public","tanks"):
    st.error("public.tanks not found."); st.stop()
if not _rel_exists("public","fish"):
    st.error("public.fish not found."); st.stop()
if not _rel_exists("public","v_fish_overview"):
    st.error("public.v_fish_overview not found (required by this page)."); st.stop()

tp_cols = _cols("public", "tank_pairs")
mom_col, dad_col = _tank_pair_parent_cols()
have_tp_code    = "tank_pair_code" in tp_cols
have_fishpair   = "fish_pair_code" in tp_cols
have_status     = "status" in tp_cols
have_created    = "created_at" in tp_cols
have_creator    = "created_by" in tp_cols
have_note       = "note" in tp_cols
have_updated    = "updated_at" in tp_cols
have_updated_by = "updated_by" in tp_cols

# ── filters ──────────────────────────────────────────────────────────────────
with st.form("filters"):
    c1, c2, c3, c4 = st.columns([3,1,1,1])
    q   = c1.text_input("Search (pair/fish/tank/genotype/fluors/fusions/tags)")
    d1  = c2.date_input("Created from", value=None) if have_created else None
    d2  = c3.date_input("Created to",   value=None) if have_created else None
    status_val = c4.selectbox("Status", ["(any)","selected","scheduled","retired","closed"], index=0) if have_status else "(any)"
    submitted = st.form_submit_button("Apply")

where, params = [], {}
if have_created and d1: where.append("tp.created_at >= :d1"); params["d1"] = str(d1)
if have_created and d2: where.append("tp.created_at <= :d2"); params["d2"] = str(d2)
if have_status and status_val != "(any)": where.append("coalesce(tp.status,'') = :st"); params["st"] = status_val
where_sql = ("WHERE " + " AND ".join(where)) if where else ""

order_clause = "tp.created_at desc nulls last, tp.tank_pair_code" if (have_created and have_tp_code) else \
               "tp.created_at desc nulls last" if have_created else \
               "tp.tank_pair_code" if have_tp_code else f"tp.{mom_col}"

# ── query (use v_fish_overview for rich fish metadata) ───────────────────────
sql = text(f"""
WITH tp AS (
  SELECT * FROM public.tank_pairs tp
  {where_sql}
),
tm AS (
  SELECT t.id::uuid AS tank_id, t.tank_code, f.fish_code
  FROM public.tanks t
  JOIN public.fish f ON f.id = t.fish_id
),
mom AS (
  SELECT
    m.tank_id,
    m.tank_code,
    m.fish_code,
    vo.genotype_pretty      AS genotype,
    vo.fusions,
    vo.fluors,
    vo.tags,
    vo.markers,
    vo.nickname,
    vo.genetic_background,
    vo.line_building_stage,
    vo.birthday
  FROM tm m
  LEFT JOIN public.v_fish_overview vo ON vo.fish_code_raw = m.fish_code
),
dad AS (
  SELECT
    d.tank_id,
    d.tank_code,
    d.fish_code,
    vo.genotype_pretty      AS genotype,
    vo.fusions,
    vo.fluors,
    vo.tags,
    vo.markers,
    vo.nickname,
    vo.genetic_background,
    vo.line_building_stage,
    vo.birthday
  FROM tm d
  LEFT JOIN public.v_fish_overview vo ON vo.fish_code_raw = d.fish_code
)
SELECT
  tp.id::text                                           AS tank_pair_id,
  {('tp.tank_pair_code' if have_tp_code else 'NULL::text')}        AS tank_pair_code,
  {('tp.fish_pair_code' if have_fishpair else 'NULL::text')}       AS fish_pair_code,
  {('tp.status'         if have_status else "'unknown'::text")}    AS status,
  {('tp.created_at'     if have_created else 'NULL::timestamptz')} AS created_at,
  {('tp.created_by'     if have_creator else 'NULL::text')}        AS created_by,
  {('tp.updated_at'     if have_updated else 'NULL::timestamptz')} AS updated_at,
  {('tp.updated_by'     if have_updated_by else 'NULL::text')}     AS updated_by,
  {('tp.note'           if have_note else 'NULL::text')}           AS note,

  mom.fish_code           AS mom_fish_code,
  mom.tank_code           AS mom_tank_code,
  mom.genotype            AS mom_genotype,
  mom.fusions             AS mom_fusions,
  mom.fluors              AS mom_fluors,
  mom.tags                AS mom_tags,
  mom.markers             AS mom_markers,
  mom.nickname            AS mom_nickname,
  mom.genetic_background  AS mom_genetic_background,
  mom.line_building_stage AS mom_line_building_stage,
  mom.birthday            AS mom_birthday,

  dad.fish_code           AS dad_fish_code,
  dad.tank_code           AS dad_tank_code,
  dad.genotype            AS dad_genotype,
  dad.fusions             AS dad_fusions,
  dad.fluors              AS dad_fluors,
  dad.tags                AS dad_tags,
  dad.markers             AS dad_markers,
  dad.nickname            AS dad_nickname,
  dad.genetic_background  AS dad_genetic_background,
  dad.line_building_stage AS dad_line_building_stage,
  dad.birthday            AS dad_birthday

FROM tp
LEFT JOIN mom ON mom.tank_id = tp.{mom_col}
LEFT JOIN dad ON dad.tank_id = tp.{dad_col}
{"WHERE (" + " OR ".join([
    "coalesce(tp.tank_pair_code,'') ilike :q" if have_tp_code else None,
    "coalesce(tp.fish_pair_code,'') ilike :q" if have_fishpair else None,
    "coalesce(mom.fish_code,'') ilike :q",
    "coalesce(dad.fish_code,'') ilike :q",
    "coalesce(mom.tank_code,'') ilike :q",
    "coalesce(dad.tank_code,'') ilike :q",
    "coalesce(mom.genotype,'') ilike :q",
    "coalesce(dad.genotype,'') ilike :q",
    "coalesce(mom.fusions,'') ilike :q",
    "coalesce(dad.fusions,'') ilike :q",
    "coalesce(mom.fluors,'') ilike :q",
    "coalesce(dad.fluors,'') ilike :q",
    "coalesce(mom.tags,'') ilike :q",
    "coalesce(dad.tags,'') ilike :q",
    "coalesce(mom.markers,'') ilike :q",
    "coalesce(dad.markers,'') ilike :q",
]) + ")" if (q and q.strip()) else ""}

ORDER BY {order_clause}
LIMIT :lim
""")

params["lim"] = 500
if q and q.strip():
    params["q"] = f"%{q.strip()}%"

with engine().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

st.caption(f"{len(df)} pair(s)")
if df.empty:
    st.info("No tank pairs match your filters."); st.stop()

# ── selection via checkbox on the table (no dropdown) ────────────────────────
table_cols = [
    "tank_pair_code","fish_pair_code","status","created_at","created_by",
    "mom_fish_code","mom_tank_code","mom_genotype",
    "dad_fish_code","dad_tank_code","dad_genotype",
]
table_cols = [c for c in table_cols if c in df.columns]
view = df[["tank_pair_id"] + table_cols].copy()
view.insert(0, "✓ Select", False)

grid = st.data_editor(
    view,
    key="tpairs_table",
    hide_index=True,
    use_container_width=True,
    column_config={"✓ Select": st.column_config.CheckboxColumn("✓", default=False)},
)
picked = grid.loc[grid["✓ Select"]].copy() if not grid.empty else pd.DataFrame()

if picked.shape[0] != 1:
    st.info("Check exactly one tank pair above to view details."); st.stop()

sel = picked.iloc[0].to_dict()
pair_id = str(sel["tank_pair_id"])
pair_code = str(sel.get("tank_pair_code") or pair_id)

# ── pivot helpers ────────────────────────────────────────────────────────────
def _pivot(title: str, d: Dict[str, Any]):
    rows = [
        {"field":"fish code",           "value": d.get("fish_code","")},
        {"field":"nickname",            "value": d.get("nickname","")},
        {"field":"genetic background",  "value": d.get("genetic_background","")},
        {"field":"line building stage", "value": d.get("line_building_stage","")},
        {"field":"birthday",            "value": d.get("birthday","")},
        {"field":"tank code",           "value": d.get("tank_code","")},
        {"field":"genotype",            "value": d.get("genotype","")},
        {"field":"fusions",             "value": d.get("fusions","")},
        {"field":"fluors",              "value": d.get("fluors","")},
        {"field":"tags",                "value": d.get("tags","")},
        {"field":"markers",             "value": d.get("markers","")},
    ]
    st.subheader(title)
    st.data_editor(pd.DataFrame(rows), hide_index=True, use_container_width=True, disabled=True)

mom = {
    "fish_code":           df.loc[df["tank_pair_id"]==pair_id, "mom_fish_code"].iloc[0],
    "nickname":            df.loc[df["tank_pair_id"]==pair_id, "mom_nickname"].iloc[0],
    "genetic_background":  df.loc[df["tank_pair_id"]==pair_id, "mom_genetic_background"].iloc[0],
    "line_building_stage": df.loc[df["tank_pair_id"]==pair_id, "mom_line_building_stage"].iloc[0],
    "birthday":            df.loc[df["tank_pair_id"]==pair_id, "mom_birthday"].iloc[0],
    "tank_code":           df.loc[df["tank_pair_id"]==pair_id, "mom_tank_code"].iloc[0],
    "genotype":            df.loc[df["tank_pair_id"]==pair_id, "mom_genotype"].iloc[0],
    "fusions":             df.loc[df["tank_pair_id"]==pair_id, "mom_fusions"].iloc[0],
    "fluors":              df.loc[df["tank_pair_id"]==pair_id, "mom_fluors"].iloc[0],
    "tags":                df.loc[df["tank_pair_id"]==pair_id, "mom_tags"].iloc[0],
    "markers":             df.loc[df["tank_pair_id"]==pair_id, "mom_markers"].iloc[0],
}
dad = {
    "fish_code":           df.loc[df["tank_pair_id"]==pair_id, "dad_fish_code"].iloc[0],
    "nickname":            df.loc[df["tank_pair_id"]==pair_id, "dad_nickname"].iloc[0],
    "genetic_background":  df.loc[df["tank_pair_id"]==pair_id, "dad_genetic_background"].iloc[0],
    "line_building_stage": df.loc[df["tank_pair_id"]==pair_id, "dad_line_building_stage"].iloc[0],
    "birthday":            df.loc[df["tank_pair_id"]==pair_id, "dad_birthday"].iloc[0],
    "tank_code":           df.loc[df["tank_pair_id"]==pair_id, "dad_tank_code"].iloc[0],
    "genotype":            df.loc[df["tank_pair_id"]==pair_id, "dad_genotype"].iloc[0],
    "fusions":             df.loc[df["tank_pair_id"]==pair_id, "dad_fusions"].iloc[0],
    "fluors":              df.loc[df["tank_pair_id"]==pair_id, "dad_fluors"].iloc[0],
    "tags":                df.loc[df["tank_pair_id"]==pair_id, "dad_tags"].iloc[0],
    "markers":             df.loc[df["tank_pair_id"]==pair_id, "dad_markers"].iloc[0],
}

c1, c2 = st.columns(2)
with c1: _pivot("Mother — profile", mom)
with c2: _pivot("Father — profile", dad)

# ── edit section (no add-new) ────────────────────────────────────────────────
st.subheader("Edit")
with st.form("edit_pair"):
    c1, c2 = st.columns(2)
    status_new = c1.selectbox("status", ["selected","scheduled","retired","closed"], index=0) if have_status else None
    note_new   = c1.text_input("note", value=str(df.loc[df["tank_pair_id"]==pair_id, "note"].iloc[0]) if have_note else "")
    upd_by     = c2.text_input("updated_by", value=str(df.loc[df["tank_pair_id"]==pair_id, "updated_by"].iloc[0]) if have_updated_by else "")
    saved = st.form_submit_button("Save", type="primary", use_container_width=True)

if saved:
    to_set, params_u = [], {"id": pair_id}
    if have_status and status_new is not None: to_set.append("status = :st"); params_u["st"] = status_new
    if have_note:                               to_set.append("note = :nt"); params_u["nt"] = note_new or ""
    if have_updated_by:                         to_set.append("updated_by = :ub"); params_u["ub"] = upd_by or ""
    if have_updated:                            to_set.append("updated_at = now()")
    if to_set:
        sql_u = text(f"UPDATE public.tank_pairs SET {', '.join(to_set)} WHERE id = :id::uuid RETURNING tank_pair_code")
        with engine().begin() as cx:
            code = pd.read_sql(sql_u, cx, params=params_u).iloc[0][0]
        st.success(f"Updated tank_pair {code}")
        st.rerun()