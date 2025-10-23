# =============================================================================
# 🧬 Select tank pairings (physical) — choose mother/father tanks and save
#     - Assumes conceptual pair/clutch are handled on the previous page
#     - Uses v_tanks for live tanks, and upserts public.tank_pairs
#     - Ensures fish_pairs row by (mom_fish_code, dad_fish_code) (ordered, unique)
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

# ─────────────────────────────────────────────────────────────────────────────
# Auth + Page
# ─────────────────────────────────────────────────────────────────────────────
import os
from datetime import date, timedelta
from typing import List, Dict, Any, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...

# ✅ Use the shared app context engine (do not import from carp_app.lib.config)
from carp_app.ui.lib.app_ctx import get_engine

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🧬 Select tank pairings", page_icon="🧬", layout="wide")
st.title("🧬 Select tank pairings")

# ─────────────────────────────────────────────────────────────────────────────
# DB engine (cached) + caption
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _cached_engine():
    return get_engine()

def _eng():
    if not os.getenv("DB_URL"):
        st.error("DB_URL not set"); st.stop()
    return _cached_engine()

with _eng().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _view_exists(schema: str, name: str) -> bool:
    with _eng().begin() as cx:
        n = pd.read_sql(
            text("""select 1 from information_schema.views
                    where table_schema=:s and table_name=:t limit 1"""),
            cx, params={"s": schema, "t": name}
        ).shape[0]
    return n > 0

def _fetch_fish_details(codes: List[str]) -> Dict[str, Dict[str, str]]:
    """
    Returns per-fish details keyed by fish_code:
      name, nickname, genetic_background, birthday, allelecode, transgene
    - allelecode: first Tg(base)guN if present (else "")
    - transgene:  first base_code if present (else "")
    """
    if not codes:
        return {}

    with _eng().begin() as cx:
        df = pd.read_sql(text("""
            with src as (
              select
                f.id,
                f.fish_code,
                coalesce(f.name,'')               as name,
                coalesce(f.nickname,'')           as nickname,
                coalesce(f.genetic_background,'') as genetic_background,
                f.date_birth                      as birthday
              from public.fish f
              where f.fish_code = any(:codes)
            ),
            alleles as (
              select
                fta.fish_id,
                fta.transgene_base_code                           as base_code,
                coalesce(ta.allele_name, '')                      as allele_name,
                ('Tg(' || fta.transgene_base_code || ')' ||
                  coalesce(ta.allele_name, ''))                  as transgene_pretty,
                row_number() over (partition by fta.fish_id
                                   order by fta.transgene_base_code, ta.allele_name) rn
              from public.fish_transgene_alleles fta
              join public.transgene_alleles ta
                on ta.transgene_base_code = fta.transgene_base_code
               and ta.allele_number       = fta.allele_number
            ),
            pick as (
              select a.fish_id, a.base_code, a.allele_name, a.transgene_pretty
              from alleles a
              where a.rn = 1
            )
            select
              s.fish_code,
              s.name,
              s.nickname,
              s.genetic_background,
              s.birthday,
              coalesce(p.base_code,'')        as transgene,
              coalesce(p.transgene_pretty,'') as allelecode
            from src s
            left join pick p on p.fish_id = s.id
        """), cx, params={"codes": list({c for c in codes if c})})

    out: Dict[str, Dict[str, str]] = {}
    if df.empty:
        return out

    for _, r in df.iterrows():
        out[str(r["fish_code"])] = {
            "name":               (r.get("name") or ""),
            "nickname":           (r.get("nickname") or ""),
            "genetic_background": (r.get("genetic_background") or ""),
            "birthday":           (pd.to_datetime(r["birthday"]).date().isoformat()
                                   if pd.notna(r.get("birthday")) else ""),
            "allelecode":         (r.get("allelecode") or ""),   # e.g., Tg(pDQM005)gu1
            "transgene":          (r.get("transgene") or ""),    # e.g., pDQM005
        }
    return out

def _load_live_tanks_for_fish(codes: List[str]) -> pd.DataFrame:
    """
    Live tanks for the given fish_code list, from v_tanks.
    Live = vt.status IN ('active','new').
    """
    if not codes:
        return pd.DataFrame(columns=[
            "fish_code","tank_code","container_id","label","status","container_type","location",
            "created_at","activated_at","deactivated_at","last_seen_at"
        ])

    sql = text("""
        select
            vt.fish_code,
            vt.tank_code,
            vt.tank_id::text             as container_id,
            ''                           as label,
            coalesce(vt.status::text,'') as status,
            'holding_tank'               as container_type,
            ''::text                     as location,
            vt.tank_created_at           as created_at,
            null::timestamptz            as activated_at,
            null::timestamptz            as deactivated_at,
            null::timestamptz            as last_seen_at
        from public.v_tanks vt
        where vt.fish_code = any(:codes)
          and vt.status::text = any(:live)
        order by vt.fish_code, vt.tank_created_at desc nulls last
    """)
    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params={
            "codes": list({c for c in codes if c}),
            "live": ["active","new"],
        })

# ─────────────────────────────────────────────────────────────────────────────
# Filters
# ─────────────────────────────────────────────────────────────────────────────
with st.form("filters", clear_on_submit=False):
    today = date.today()
    c1, c2, c3, c4 = st.columns([1,1,1,3])
    with c1: d1 = st.date_input("From", value=today - timedelta(days=14))
    with c2: d2 = st.date_input("To", value=today)
    with c3: created_by = st.text_input("Created by", value=os.environ.get("USER") or os.environ.get("USERNAME") or "")
    with c4: q = st.text_input("Omni-search (code / name / nickname / mom / dad)", value="")
    st.form_submit_button("Apply", use_container_width=True)

# Load conceptual clutch "plans" if present (optional; page works without it)
def _load_clutch_concepts(d1: date, d2: date, created_by: str, q: str) -> pd.DataFrame:
    """
    Optional: list conceptual clutch plans (if table exists).
    We keep schema-agnostic fields that are safe to show.
    """
    # If the table doesn't exist, return empty
    try:
        with _eng().begin() as cx:
            exists = pd.read_sql(text("""
              select 1 from information_schema.tables
              where table_schema='public' and table_name='clutch_plans' limit 1
            """), cx)
            if exists.empty:
                return pd.DataFrame()
            df = pd.read_sql(text("""
              select
                id::text           as clutch_id,
                coalesce(clutch_code, id::text) as clutch_code,
                mom_code, dad_code,
                created_by, created_at
              from public.clutch_plans
              where (created_at::date between :d1 and :d2)
                and (:by = '' or created_by ilike :byl)
                and (
                  :q = '' or
                  coalesce(clutch_code,'') ilike :ql or
                  coalesce(mom_code,'')    ilike :ql or
                  coalesce(dad_code,'')    ilike :ql
                )
              order by created_at desc
            """), cx, params={
                "d1": d1, "d2": d2,
                "by": (created_by or "").strip(), "byl": f"%{(created_by or '').strip()}%",
                "q":  (q or "").strip(),          "ql": f"%{(q or '').strip()}%",
            })
            return df
    except Exception:
        return pd.DataFrame()

plans = _load_clutch_concepts(d1, d2, created_by, q)
if plans is None or not isinstance(plans, pd.DataFrame):
    plans = pd.DataFrame()

# ─────────────────────────────────────────────────────────────────────────────
# 1) Top table — pick a plan (optional), derive parents for tank search
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### 1) Select a clutch concept (optional) or proceed directly")
st.caption(f"{len(plans)} concept(s) found.")

plan_df = plans.copy() if not plans.empty else pd.DataFrame()
if not plan_df.empty:
    if "✓ Select" not in plan_df.columns:
        plan_df.insert(0, "✓ Select", False)
    plan_view_cols = ["✓ Select", "clutch_code", "mom_code", "dad_code", "created_by", "created_at"]
    for c in plan_view_cols:
        if c not in plan_df.columns:
            plan_df[c] = "" if c not in ("created_at",) else pd.NaT
    plan_edited = st.data_editor(
        plan_df[plan_view_cols],
        hide_index=True,
        use_container_width=True,
        column_config={
            "✓ Select":   st.column_config.CheckboxColumn("✓", default=False),
            "clutch_code": st.column_config.TextColumn("clutch_code", disabled=True),
            "mom_code":    st.column_config.TextColumn("mom_code", disabled=True),
            "dad_code":    st.column_config.TextColumn("dad_code", disabled=True),
            "created_by":  st.column_config.TextColumn("created_by", disabled=True),
            "created_at":  st.column_config.DatetimeColumn("created_at", disabled=True),
        },
        key="plans_table",
    )
    sel_mask  = plan_edited.get("✓ Select", pd.Series(False, index=plan_edited.index)).fillna(False).astype(bool)
    sel_plans = plan_df.loc[sel_mask].reset_index(drop=True)
else:
    sel_plans = pd.DataFrame()

fixed_moms: List[str] = []
fixed_dads: List[str] = []
if not sel_plans.empty:
    fixed_moms = sorted(set([c for c in sel_plans["mom_code"].dropna().astype(str).tolist() if c.strip()]))
    fixed_dads = sorted(set([c for c in sel_plans["dad_code"].dropna().astype(str).tolist() if c.strip()]))

# ─────────────────────────────────────────────────────────────────────────────
# 2) Choose parent tanks — list LIVE TANKS for the fixed parents
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("2) Choose parent tanks (mother tank × father tank)")

selected_mom_tanks = pd.DataFrame()
selected_dad_tanks = pd.DataFrame()

if fixed_moms:
    st.markdown("**Mother tanks**")
    mom_tanks = _load_live_tanks_for_fish(fixed_moms)
    mom_details = _fetch_fish_details(mom_tanks["fish_code"].astype(str).tolist()) if not mom_tanks.empty else {}
    def _md(code, key): return mom_details.get(code, {}).get(key, "")
    if mom_tanks.empty:
        st.info("No live tanks found for the selected mom fish.")
    else:
        mt = mom_tanks.copy()
        mt["name"]       = mt["fish_code"].map(lambda c: _md(c, "name"))
        mt["nickname"]   = mt["fish_code"].map(lambda c: _md(c, "nickname"))
        mt["background"] = mt["fish_code"].map(lambda c: _md(c, "genetic_background"))
        mt["allelecode"] = mt["fish_code"].map(lambda c: _md(c, "allelecode"))
        mt["transgene"]  = mt["fish_code"].map(lambda c: _md(c, "transgene"))
        if "✓ Select" not in mt.columns:
            mt.insert(0,"✓ Select", False)

        mom_cols = [
            "✓ Select",
            "fish_code","tank_code","container_id",
            "name","nickname","background","allelecode","transgene",
            "label","status","container_type","location","created_at","last_seen_at"
        ]
        for c in mom_cols:
            if c not in mt.columns: mt[c] = ""
        mom_view = mt[mom_cols].rename(columns={"fish_code":"mom FSH","tank_code":"mom tank","container_id":"mom container"})
        mom_edit = st.data_editor(
            mom_view, hide_index=True, use_container_width=True, num_rows="fixed",
            column_config={
                "✓ Select":       st.column_config.CheckboxColumn("✓", default=False),
                "mom FSH":        st.column_config.TextColumn("mom FSH", disabled=True),
                "mom tank":       st.column_config.TextColumn("mom tank", disabled=True),
                "mom container":  st.column_config.TextColumn("mom container", disabled=True),
                "name":           st.column_config.TextColumn("name", disabled=True),
                "nickname":       st.column_config.TextColumn("nickname", disabled=True),
                "background":     st.column_config.TextColumn("background", disabled=True),
                "allelecode":     st.column_config.TextColumn("allelecode", disabled=True),
                "transgene":      st.column_config.TextColumn("transgene", disabled=True),
                "label":          st.column_config.TextColumn("label", disabled=True),
                "status":         st.column_config.TextColumn("status", disabled=True),
                "container_type": st.column_config.TextColumn("container_type", disabled=True),
                "location":       st.column_config.TextColumn("location", disabled=True),
                "created_at":     st.column_config.DatetimeColumn("created_at", disabled=True),
                "last_seen_at":   st.column_config.DatetimeColumn("last_seen_at", disabled=True),
            },
            key="mom_tanks_editor",
        )
        selected_mom_tanks = mom_edit[mom_edit["✓ Select"]].copy()
else:
    st.info("Select a clutch concept (or enter mom/dad in the previous page) to load mother tanks.")

if fixed_dads:
    st.markdown("**Father tanks**")
    dad_tanks = _load_live_tanks_for_fish(fixed_dads)
    dad_details = _fetch_fish_details(dad_tanks["fish_code"].astype(str).tolist()) if not dad_tanks.empty else {}
    def _dd(code, key): return dad_details.get(code, {}).get(key, "")
    if dad_tanks.empty:
        st.info("No live tanks found for the selected dad fish.")
    else:
        dt = dad_tanks.copy()
        dt["name"]       = dt["fish_code"].map(lambda c: _dd(c, "name"))
        dt["nickname"]   = dt["fish_code"].map(lambda c: _dd(c, "nickname"))
        dt["background"] = dt["fish_code"].map(lambda c: _dd(c, "genetic_background"))
        dt["allelecode"] = dt["fish_code"].map(lambda c: _dd(c, "allelecode"))
        dt["transgene"]  = dt["fish_code"].map(lambda c: _dd(c, "transgene"))
        if "✓ Select" not in dt.columns:
            dt.insert(0,"✓ Select", False)

        dad_cols = [
            "✓ Select",
            "fish_code","tank_code","container_id",
            "name","nickname","background","allelecode","transgene",
            "label","status","container_type","location","created_at","last_seen_at"
        ]
        for c in dad_cols:
            if c not in dt.columns: dt[c] = ""
        dad_view = dt[dad_cols].rename(columns={"fish_code":"dad FSH","tank_code":"dad tank","container_id":"dad container"})
        dad_edit = st.data_editor(
            dad_view, hide_index=True, use_container_width=True, num_rows="fixed",
            column_config={
                "✓ Select":       st.column_config.CheckboxColumn("✓", default=False),
                "dad FSH":        st.column_config.TextColumn("dad FSH", disabled=True),
                "dad tank":       st.column_config.TextColumn("dad tank", disabled=True),
                "dad container":  st.column_config.TextColumn("dad container", disabled=True),
                "name":           st.column_config.TextColumn("name", disabled=True),
                "nickname":       st.column_config.TextColumn("nickname", disabled=True),
                "background":     st.column_config.TextColumn("background", disabled=True),
                "allelecode":     st.column_config.TextColumn("allelecode", disabled=True),
                "transgene":      st.column_config.TextColumn("transgene", disabled=True),
                "label":          st.column_config.TextColumn("label", disabled=True),
                "status":         st.column_config.TextColumn("status", disabled=True),
                "container_type": st.column_config.TextColumn("container_type", disabled=True),
                "location":       st.column_config.TextColumn("location", disabled=True),
                "created_at":     st.column_config.DatetimeColumn("created_at", disabled=True),
                "last_seen_at":   st.column_config.DatetimeColumn("last_seen_at", disabled=True),
            },
            key="dad_tanks_editor",
        )
        selected_dad_tanks = dad_edit[dad_edit["✓ Select"]].copy()
else:
    st.info("Select a clutch concept (or enter mom/dad in the previous page) to load father tanks.")

# ─────────────────────────────────────────────────────────────────────────────
# Save selected tank pairs as PRE-CROSS selections (tank_pairs) + list history
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### 3) Save selection")

# Build selected tank pairs (cartesian of checked rows)
pairs: List[Tuple[str, str]] = []
if (isinstance(selected_mom_tanks, pd.DataFrame) and not selected_mom_tanks.empty) and \
   (isinstance(selected_dad_tanks, pd.DataFrame) and not selected_dad_tanks.empty):
    for _, m in selected_mom_tanks.iterrows():
        for _, d in selected_dad_tanks.iterrows():
            pairs.append((str(m["mom container"]), str(d["dad container"])))

def _get_concept_id() -> str | None:
    if not sel_plans.empty and "clutch_id" in sel_plans.columns:
        return str(sel_plans.iloc[0]["clutch_id"])
    return None

def _ensure_fish_pair(mom_fish_code: str, dad_fish_code: str, created_by_val: str) -> str:
    """
    Ensure fish_pairs row exists (ordered mom/dad by code). Returns fish_pair_id (uuid).
    """
    with _eng().begin() as cx:
        # Upsert on (mom_fish_code, dad_fish_code)
        cx.execute(text("""
          insert into public.fish_pairs (fish_pair_code, mom_fish_code, dad_fish_code, created_by)
          values (
            -- generate a new FP code only if row is new
            'FP-'||to_char(extract(year from now())::int % 100,'FM00')||
            lpad((
              select coalesce(max((regexp_match(coalesce(fish_pair_code,''),
                   '^FP-\\d{2}(\\d{4})$'))[1]::int),0) + 1
              from public.fish_pairs
              where fish_pair_code like 'FP-'||to_char(extract(year from now())::int % 100,'FM00')||'%'
            )::text, 4, '0'),
            :mom, :dad, :by
          )
          on conflict (mom_fish_code, dad_fish_code) do update
            set created_by = coalesce(excluded.created_by, public.fish_pairs.created_by)
        """), {"mom": mom_fish_code, "dad": dad_fish_code, "by": created_by_val})

        row = pd.read_sql(text("""
          select fish_pair_id
          from public.fish_pairs
          where mom_fish_code=:mom and dad_fish_code=:dad
          order by created_at desc
          limit 1
        """), cx, params={"mom": mom_fish_code, "dad": dad_fish_code})
        return str(row.iloc[0]["fish_pair_id"])

def _insert_tank_pairs(pairs: List[Tuple[str, str]], created_by: str, note: str = "") -> pd.DataFrame:
    """
    Insert selected (mother_tank_id, father_tank_id) into public.tank_pairs with status='selected'.
    - Ensures fish_pairs row per (mom_fish_code, dad_fish_code)
    - Upserts on (concept_id, mother_tank_id, father_tank_id) if concept_id present
    Returns rows inserted/updated.
    """
    concept_id = _get_concept_id()
    rows: List[Dict[str, Any]] = []

    if not pairs:
        return pd.DataFrame()

    with _eng().begin() as cx:
        mom_rows = selected_mom_tanks if isinstance(selected_mom_tanks, pd.DataFrame) else pd.DataFrame()
        dad_rows = selected_dad_tanks if isinstance(selected_dad_tanks, pd.DataFrame) else pd.DataFrame()

        for _, m in mom_rows.iterrows():
            for _, d in dad_rows.iterrows():
                mom_cid = str(m["mom container"])
                dad_cid = str(d["dad container"])
                mom_code = str(m["mom FSH"])
                dad_code = str(d["dad FSH"])

                fp_id = _ensure_fish_pair(mom_code, dad_code, created_by)

                # Insert selected tank_pair
                sql = text("""
                  insert into public.tank_pairs
                    (concept_id, fish_pair_id, mother_tank_id, father_tank_id, status, created_by, note)
                  values
                    (:concept, :fp, cast(:mom as uuid), cast(:dad as uuid), 'selected', :by, nullif(:note,''))
                  on conflict (concept_id, mother_tank_id, father_tank_id) do update
                    set updated_at = now(),
                        note = coalesce(excluded.note, public.tank_pairs.note)
                  returning id, tank_pair_code, concept_id, fish_pair_id,
                            mother_tank_id, father_tank_id, status, created_by, created_at
                """)
                res = cx.execute(sql, {
                    "concept": concept_id,
                    "fp": fp_id,
                    "mom": mom_cid,
                    "dad": dad_cid,
                    "by": created_by,
                    "note": note,
                })
                rows.extend(res.mappings().all())

    return pd.DataFrame(rows)

def _list_tank_pairs_for_selection() -> pd.DataFrame:
    """
    Show recent tank_pairs for either:
      - the selected concept_id, or
      - the selected mother/father tanks (container ids)
    """
    concept_id = _get_concept_id()

    # Collect chosen containers
    ids: List[str] = []
    if isinstance(selected_mom_tanks, pd.DataFrame) and not selected_mom_tanks.empty:
        ids += selected_mom_tanks["mom container"].astype(str).tolist()
    if isinstance(selected_dad_tanks, pd.DataFrame) and not selected_dad_tanks.empty:
        ids += selected_dad_tanks["dad container"].astype(str).tolist()
    ids = [x for x in dict.fromkeys(ids) if x]

    with _eng().begin() as cx:
        if not ids:
            if not concept_id:
                return pd.DataFrame()
            return pd.read_sql(
                text("""
                  select *
                  from public.v_tank_pairs
                  where concept_id = :concept
                  order by created_at desc
                  limit 500
                """),
                cx,
                params={"concept": concept_id},
            )

        params: Dict[str, Any] = {"concept": concept_id}
        vals_sql = ", ".join([f"(cast(:id_{i} as uuid))" for i, _ in enumerate(ids)])
        for i, uid in enumerate(ids):
            params[f"id_{i}"] = uid

        sql = text(f"""
          with ids(uuid_id) as (
            values {vals_sql}
          )
          select *
          from public.v_tank_pairs
          where ( :concept is null or concept_id = :concept )
            and (mother_tank_id in (select uuid_id from ids)
                 or father_tank_id in (select uuid_id from ids))
          order by created_at desc
          limit 500
        """)
        return pd.read_sql(sql, cx, params=params)

# ─────────────────────────────────────────────────────────────────────────────
# Commit UI
# ─────────────────────────────────────────────────────────────────────────────
c1, c2 = st.columns([1,2])
with c1:
    created_by_val = st.text_input("Created by", value=os.environ.get("USER") or os.environ.get("USERNAME") or "unknown")
    note_val = st.text_input("Note (optional)", value="")
    can_save = isinstance(selected_mom_tanks, pd.DataFrame) and not selected_mom_tanks.empty \
               and isinstance(selected_dad_tanks, pd.DataFrame) and not selected_dad_tanks.empty
    if st.button("💾 Save selected tank pair(s)", type="primary", use_container_width=True, disabled=not can_save):
        inserted = _insert_tank_pairs(
            [(str(m["mom container"]), str(d["dad container"]))
             for _, m in selected_mom_tanks.iterrows()
             for _, d in selected_dad_tanks.iterrows()],
            created_by_val, note_val
        )
        if not inserted.empty:
            st.success(f"Saved {len(inserted)} tank_pair row(s).")
        else:
            st.warning("Nothing was saved.")

with c2:
    st.markdown("**Recent tank_pairs for these tanks / concept**")
    tp = _list_tank_pairs_for_selection()
    if tp.empty:
        st.info("No tank_pairs yet for this selection.")
    else:
        preferred_cols = [
            "tank_pair_code",
            "clutch_code",
            "status",
            "mom_fish_code", "mom_tank_code",
            "dad_fish_code", "dad_tank_code",
            "created_by", "created_at",
        ]
        cols = [c for c in preferred_cols if c in tp.columns] or list(tp.columns)
        st.dataframe(tp[cols], use_container_width=True, hide_index=True)