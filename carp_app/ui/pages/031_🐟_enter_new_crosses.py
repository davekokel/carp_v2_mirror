from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()

from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
from typing import Any, Dict, List, Tuple
import pandas as pd
import streamlit as st
from carp_app.lib.db import get_engine
from sqlalchemy import text

# =================================
# Page config
# =================================
st.set_page_config(page_title="🐟 Plan new crosses", page_icon="🐟", layout="wide")
st.title("🐟 Plan new crosses")

# 🔒 optional unlock
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

# =================================
# DB engine
# =================================
_ENGINE = None
def _get_engine():
    global _ENGINE
    if _ENGINE:
        return _ENGINE
    url = os.getenv("DB_URL")
    if not url:
        raise RuntimeError("DB_URL not set")
    _ENGINE = get_engine()
    return _ENGINE

# =================================
# Helpers: cross name & nickname, tank col augmentation
# =================================
def _augment_tank_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure tank tables include: tank_code, birthday, location, notes.
    - birthday := coalesce(activated_at, created_at)::date
    - notes    := notes or note (whichever exists)
    """
    if df is None or df.empty:
        base = pd.DataFrame(columns=["tank_code","label","status","birthday","location","notes"])
        return (df if df is not None else base).reindex(columns=base.columns, fill_value=None)

    df = df.copy()

    if "Tank code" in df.columns and "tank_code" not in df.columns:
        df.rename(columns={"Tank code": "tank_code"}, inplace=True)

    if "birthday" not in df.columns:
        at = pd.to_datetime(df["activated_at"], errors="coerce") if "activated_at" in df.columns else pd.NaT
        ct = pd.to_datetime(df["created_at"],   errors="coerce") if "created_at"   in df.columns else pd.NaT
        try:
            co = at.fillna(ct)
        except Exception:
            co = pd.to_datetime(df.get("activated_at"), errors="coerce").fillna(
                 pd.to_datetime(df.get("created_at"), errors="coerce"))
        df["birthday"] = pd.to_datetime(co, errors="coerce").dt.date

    if "location" not in df.columns:
        df["location"] = df.get("location", "")

    if "notes" not in df.columns:
        if "note" in df.columns:
            df["notes"] = df["note"]
        else:
            df["notes"] = ""

    if "tank_code" not in df.columns:
        df["tank_code"] = df.get("tank_code")

    if "label" not in df.columns:
        df["label"] = df.get("label", "")

    if "status" not in df.columns:
        df["status"] = df.get("status", "")

    return df

def _compute_cross_name(mom_code: str, dad_code: str) -> str:
    """
    Ask DB to compute the canonical cross_name (public.gen_cross_name),
    fallback to "MOM × DAD" if the function isn't present.
    """
    try:
        with _get_engine().begin() as cx:
            row = cx.execute(text("SELECT public.gen_cross_name(:m,:d)"),
                             {"m": mom_code, "d": dad_code}).fetchone()
        return row[0] if row and row[0] else f"{mom_code} × {dad_code}"
    except Exception:
        return f"{mom_code} × {dad_code}"

def _get_or_create_cross_and_set_nickname(mom_code: str, dad_code: str, created_by: str, nickname: str | None) -> Tuple[str, str]:
    """
    Returns (cross_id, cross_code).
    Reuses an existing concept for mom×dad if present; otherwise inserts one.
    Always updates cross_nickname to the provided value (or the computed cross_name).
    """
    wanted_nick = nickname or _compute_cross_name(mom_code, dad_code)
    with _get_engine().begin() as cx:
        row = cx.execute(
            text("""
              SELECT id::text, COALESCE(cross_code, id::text)
              FROM public.crosses
              WHERE upper(trim(mother_code)) = upper(trim(:m))
                AND upper(trim(father_code)) = upper(trim(:d))
              LIMIT 1
            """),
            {"m": mom_code, "d": dad_code},
        ).fetchone()

        if row:
            cross_id, cross_code = row[0], row[1]
            cx.execute(
                text("UPDATE public.crosses SET cross_nickname = :nick WHERE id = :id"),
                {"nick": wanted_nick, "id": cross_id},
            )
        else:
            cross_id, cross_code = cx.execute(
                text("""
                  INSERT INTO public.crosses (mother_code, father_code, created_by, cross_nickname)
                  VALUES (:m, :d, :by, :nick)
                  RETURNING id::text, COALESCE(cross_code, id::text)
                """),
                {"m": mom_code, "d": dad_code, "by": created_by, "nick": wanted_nick},
            ).one()
    return cross_id, cross_code

# =================================
# Filters
# =================================
with st.form("clutch_filters"):
    c1, c2, c3 = st.columns([2,1,1])
    with c1:
        q = st.text_input("Search planned clutches (code/name/nickname/mom/dad)", "")
    with c2:
        limit = int(st.number_input("Limit", min_value=1, max_value=1000, value=200, step=50))
    with c3:
        user_by = st.text_input("Created by", value=os.environ.get("USER") or os.environ.get("USERNAME") or "unknown")
    st.form_submit_button("Apply")

# =================================
# Load planned clutches
# =================================
def _load_planned_clutches(q: str, limit: int) -> pd.DataFrame:
    sql = """
      with tx_counts as (
        select clutch_id, count(*) as n_treatments
        from public.clutch_plan_treatments
        group by clutch_id
      )
      select
        p.id::text                          as clutch_id,
        coalesce(p.clutch_code, p.id::text) as clutch_code,
        coalesce(p.planned_name,'')         as name,
        coalesce(p.planned_nickname,'')     as nickname,
        p.mom_code,
        p.dad_code,
        coalesce(t.n_treatments,0)          as n_treatments,
        p.created_by,
        p.created_at
      from public.clutch_plans p
      left join tx_counts t on t.clutch_id = p.id
      where (
        :q = '' OR
        p.clutch_code ILIKE :q_like OR
        p.planned_name ILIKE :q_like OR
        p.planned_nickname ILIKE :q_like OR
        p.mom_code ILIKE :q_like OR
        p.dad_code ILIKE :q_like
      )
      order by p.created_at desc
      limit :lim
    """
    with _get_engine().begin() as cx:
        return pd.read_sql(text(sql), cx, params={"q": q or "", "q_like": f"%{q or ''}%", "lim": int(limit)})

df = _load_planned_clutches(q, limit)
st.caption(f"{len(df)} planned clutch(es)")

if df.empty:
    st.info("No planned clutches match.")
    st.stop()

# =================================
# Selection table
# =================================
df_view = df.copy()
df_view.insert(0, "✓ Select", False)
edited = st.data_editor(
    df_view,
    use_container_width=True,
    hide_index=True,
    column_order=["✓ Select","clutch_code","name","nickname","mom_code","dad_code","n_treatments","created_by","created_at"],
    column_config={
        "✓ Select":    st.column_config.CheckboxColumn("✓ Select", default=False),
        "clutch_code": st.column_config.TextColumn("clutch_code", disabled=True),
        "name":        st.column_config.TextColumn("name", disabled=True),
        "nickname":    st.column_config.TextColumn("nickname", disabled=True),
        "mom_code":    st.column_config.TextColumn("mom_code", disabled=True),
        "dad_code":    st.column_config.TextColumn("dad_code", disabled=True),
        "n_treatments":st.column_config.NumberColumn("n_treatments", disabled=True),
        "created_by":  st.column_config.TextColumn("created_by", disabled=True),
        "created_at":  st.column_config.DatetimeColumn("created_at", disabled=True),
    },
    key="planned_clutches_editor",
)
picked = edited[edited["✓ Select"]].copy()
if picked.empty:
    st.warning("Select at least one planned clutch to set up crosses.")
    st.stop()

# =================================
# Live tanks
# =================================
st.subheader("Assign crossing tanks")
LIVE_STATUSES = ("active","new_tank")

with _get_engine().begin() as cx:
    df_live = pd.read_sql(text("""
      select
        f.fish_code,
        m.container_id::text as tank_id,
        c.tank_code,
        coalesce(c.label,'')    as tank_label,
        coalesce(c.status,'')   as tank_status,
        c.created_at,
        c.activated_at,
        nullif(to_jsonb(c)->>'location','') as location,
        coalesce(
          nullif(to_jsonb(c)->>'notes',''),
          nullif(to_jsonb(c)->>'note',''),
          ''
        ) as notes
      from public.fish f
      join public.fish_tank_memberships m on m.fish_id = f.id
      join public.containers c on c.id = m.container_id
      where coalesce(
              nullif(to_jsonb(m)->>'left_at','')::timestamptz,
              nullif(to_jsonb(m)->>'ended_at','')::timestamptz
            ) is null
        and c.container_type in ('inventory_tank','holding_tank','nursery_tank')
        and c.status = any(:live_statuses)
      order by f.fish_code, c.label
    """), cx, params={"live_statuses": list(LIVE_STATUSES)})

live_by_fish: Dict[str, List[Dict[str, Any]]] = {}
for _, r in df_live.iterrows():
    live_by_fish.setdefault(r["fish_code"], []).append({
        "id":          r["tank_id"],
        "tank_code":   r.get("tank_code"),
        "label":       r.get("tank_label", ""),
        "status":      r.get("tank_status", ""),
        "created_at":  r.get("created_at"),
        "activated_at":r.get("activated_at"),
        "location":    r.get("location", ""),
        "notes":       r.get("notes", ""),
    })

assignments: List[Dict[str, Any]] = []
for _, r in picked.iterrows():
    with st.expander(f"{r['clutch_code']} — {r['name'] or r['nickname']}", expanded=False):

        # --- Cross naming UI (concept-level) ---
        computed_name = _compute_cross_name(r["mom_code"], r["dad_code"])
        st.caption(f"Cross name (computed): **{computed_name}**")
        nick_key = f"nick_{r['clutch_code']}"
        cross_nickname = st.text_input("Cross nickname (optional)", value=st.session_state.get(nick_key, computed_name), key=nick_key)

        # --- Previous live tanks (for this clutch), normalized columns ---
        st.caption("Previously used tanks (live)")

        with _get_engine().begin() as cx:
            prev_mom = pd.read_sql(
                text("""
                  select
                    cm.tank_code,
                    coalesce(cm.label,'')    as label,
                    coalesce(cm.status,'')   as status,
                    cm.created_at,
                    cm.activated_at,
                    nullif(to_jsonb(cm)->>'location','') as location,
                    coalesce(
                      nullif(to_jsonb(cm)->>'notes',''),
                      nullif(to_jsonb(cm)->>'note',''),
                      ''
                    ) as notes,
                    pc.created_at as planned_at
                  from public.planned_crosses pc
                  left join public.containers cm on cm.id = pc.mother_tank_id
                  where pc.clutch_id = :clutch_id
                    and coalesce(cm.status,'') = any(:live_statuses)
                  order by pc.created_at desc
                  limit 10
                """),
                cx, params={"clutch_id": r["clutch_id"], "live_statuses": list(LIVE_STATUSES)}
            )

            prev_dad = pd.read_sql(
                text("""
                  select
                    cf.tank_code,
                    coalesce(cf.label,'')    as label,
                    coalesce(cf.status,'')   as status,
                    cf.created_at,
                    cf.activated_at,
                    nullif(to_jsonb(cf)->>'location','') as location,
                    coalesce(
                      nullif(to_jsonb(cf)->>'notes',''),
                      nullif(to_jsonb(cf)->>'note',''),
                      ''
                    ) as notes,
                    pc.created_at as planned_at
                  from public.planned_crosses pc
                  left join public.containers cf on cf.id = pc.father_tank_id
                  where pc.clutch_id = :clutch_id
                    and coalesce(cf.status,'') = any(:live_statuses)
                  order by pc.created_at desc
                  limit 10
                """),
                cx, params={"clutch_id": r["clutch_id"], "live_statuses": list(LIVE_STATUSES)}
            )

        mom_hist = _augment_tank_cols(prev_mom)
        dad_hist = _augment_tank_cols(prev_dad)

        mom_cols = [c for c in ["tank_code","label","status","birthday","location","notes"] if c in mom_hist.columns]
        dad_cols = [c for c in ["tank_code","label","status","birthday","location","notes"] if c in dad_hist.columns]

        if mom_hist.empty and dad_hist.empty:
            st.info("No live previous tanks found for this clutch.")
        else:
            mc, dc = st.columns(2)
            with mc:
                st.caption("Mother — previously used (live)")
                st.write("—" if mom_hist.empty else "")
                if not mom_hist.empty:
                    st.dataframe(mom_hist[mom_cols], use_container_width=True, hide_index=True)
            with dc:
                st.caption("Father — previously used (live)")
                st.write("—" if dad_hist.empty else "")
                if not dad_hist.empty:
                    st.dataframe(dad_hist[dad_cols], use_container_width=True, hide_index=True)

        # --- Mother tank pick (resolve by tank_code) ---
        mom_list = live_by_fish.get(r["mom_code"], [])
        if not mom_list:
            st.warning(f"No live mother tanks for {r['mom_code']} (need status active or new_tank).")
            mom_pick = None; mom_map = {}
        else:
            mom_df = _augment_tank_cols(pd.DataFrame(mom_list))
            mom_df.insert(0, "✓ Mother", False)
            mom_cols = [c for c in ["✓ Mother","tank_code","label","status","birthday","location","notes"] if c in mom_df.columns]
            mom_table = st.data_editor(
                mom_df[mom_cols],
                use_container_width=True, hide_index=True,
                column_config={
                    "✓ Mother": st.column_config.CheckboxColumn("✓ Mother", default=False),
                    "tank_code":st.column_config.TextColumn("tank_code", disabled=True),
                    "label":    st.column_config.TextColumn("label", disabled=True),
                    "status":   st.column_config.TextColumn("status", disabled=True),
                    "birthday": st.column_config.DateColumn("birthday", disabled=True, format="YYYY-MM-DD"),
                    "location": st.column_config.TextColumn("location", disabled=True),
                    "notes":    st.column_config.TextColumn("notes", disabled=True),
                },
                key=f"mom_tbl_{r['clutch_code']}",
            )
            checked = mom_table[mom_table["✓ Mother"]]
            mom_pick = None if checked.empty else str(checked.iloc[0]["tank_code"])
            mom_map  = {t["tank_code"]: t["id"] for t in mom_list if t.get("tank_code")}

        # --- Father tank pick (resolve by tank_code) ---
        dad_list = live_by_fish.get(r["dad_code"], [])
        if not dad_list:
            st.warning(f"No live father tanks for {r['dad_code']} (need status active or new_tank).")
            dad_pick = None; dad_map = {}
        else:
            dad_df = _augment_tank_cols(pd.DataFrame(dad_list))
            dad_df.insert(0, "✓ Father", False)
            dad_cols = [c for c in ["✓ Father","tank_code","label","status","birthday","location","notes"] if c in dad_df.columns]
            dad_table = st.data_editor(
                dad_df[dad_cols],
                use_container_width=True, hide_index=True,
                column_config={
                    "✓ Father": st.column_config.CheckboxColumn("✓ Father", default=False),
                    "tank_code":st.column_config.TextColumn("tank_code", disabled=True),
                    "label":    st.column_config.TextColumn("label", disabled=True),
                    "status":   st.column_config.TextColumn("status", disabled=True),
                    "birthday": st.column_config.DateColumn("birthday", disabled=True, format="YYYY-MM-DD"),
                    "location": st.column_config.TextColumn("location", disabled=True),
                    "notes":    st.column_config.TextColumn("notes", disabled=True),
                },
                key=f"dad_tbl_{r['clutch_code']}",
            )
            checked = dad_table[dad_table["✓ Father"]]
            dad_pick = None if checked.empty else str(checked.iloc[0]["tank_code"])
            dad_map  = {t["tank_code"]: t["id"] for t in dad_list if t.get("tank_code")}

        note = st.text_input("Note (optional)", key=f"note_{r['clutch_code']}")

        assignments.append({
            "clutch_id":      r["clutch_id"],
            "clutch_code":    r["clutch_code"],
            "mom_code":       r["mom_code"],
            "dad_code":       r["dad_code"],
            "m_code":         mom_pick,   # tank_code chosen
            "f_code":         dad_pick,   # tank_code chosen
            "note":           note,
            "cross_nickname": cross_nickname,
            "_mom_map":       mom_map,    # tank_code -> id
            "_dad_map":       dad_map,    # tank_code -> id
        })

# =================================
# Save planned crosses (idempotent)
# =================================
save_btn = st.button("Save planned crosses", type="primary", use_container_width=True)
if save_btn:
    if not assignments:
        st.warning("Nothing to save.")
    else:
        saved, errors = 0, []
        with _get_engine().begin() as cx:
            # Idempotent insert: if (clutch_id, mother_tank_id, father_tank_id) already exists,
            # do nothing and fetch the existing id.
            ins_planned = text("""
              insert into public.planned_crosses
                (clutch_id, mom_code, dad_code, mother_tank_id, father_tank_id, note, created_by)
              values
                (:clutch_id, :mom, :dad, :m_id, :f_id, :note, :by)
              on conflict on constraint uq_planned_crosses_clutch_parents_canonical
              do nothing
              returning id
            """)
            get_existing = text("""
              select id
              from public.planned_crosses
              where clutch_id = :clutch_id
                and mother_tank_id = :m_id
                and father_tank_id = :f_id
              order by created_at desc
              limit 1
            """)
            link_back = text("""
              update public.planned_crosses
              set cross_id = :cross_id, cross_code = :cross_code
              where id = :planned_id
            """)

            for a in assignments:
                if not a["m_code"] or not a["f_code"]:
                    errors.append(f"{a['clutch_code']}: pick both mother and father tanks")
                    continue

                m_id = a["_mom_map"].get(a["m_code"])
                f_id = a["_dad_map"].get(a["f_code"])
                if not m_id or not f_id:
                    errors.append(f"{a['clutch_code']}: could not resolve selected tank ids")
                    continue

                # 1) insert (idempotent)
                planned_id = cx.execute(ins_planned, {
                    "clutch_id": a["clutch_id"],
                    "mom": a["mom_code"], "dad": a["dad_code"],
                    "m_id": m_id, "f_id": f_id,
                    "note": a["note"] or "",
                    "by": user_by,
                }).scalar_one_or_none()

                if planned_id is None:
                    planned_id = cx.execute(get_existing, {
                        "clutch_id": a["clutch_id"],
                        "m_id": m_id,
                        "f_id": f_id,
                    }).scalar_one()

                # 2) get-or-create concept + set nickname
                cross_id, cross_code = _get_or_create_cross_and_set_nickname(
                    mom_code=a["mom_code"], dad_code=a["dad_code"],
                    created_by=user_by, nickname=a["cross_nickname"]
                )

                # 3) link back
                cx.execute(link_back, {
                    "cross_id": str(cross_id),
                    "cross_code": cross_code,
                    "planned_id": str(planned_id),
                })

                saved += 1

        if saved:
            st.success(f"Saved {saved} planned cross(es) and linked to concept crosses (nickname stored).")
        if errors:
            st.error("Some crosses were not saved:\n- " + "\n- ".join(errors))

# =================================
# Recently saved planned crosses
# =================================
with _get_engine().begin() as cx:
    df_recent = pd.read_sql(text("""
      select
        coalesce(pc.cross_code, pc.id::text) as cross_code,
        cp.clutch_code,
        cp.planned_name,
        pc.mom_code,
        pc.dad_code,
        cm.label as mother_tank,
        cf.label as father_tank,
        pc.created_at
      from public.planned_crosses pc
      join public.clutch_plans cp on cp.id = pc.clutch_id
      left join public.containers cm on cm.id = pc.mother_tank_id
      left join public.containers cf on cf.id = pc.father_tank_id
      order by pc.created_at desc
      limit 100
    """), cx)

st.subheader("Recently saved planned crosses")
if df_recent.empty:
    st.info("No planned crosses yet.")
else:
    st.dataframe(
        df_recent[["cross_code","clutch_code","planned_name","mom_code","dad_code","mother_tank","father_tank","created_at"]],
        use_container_width=True, hide_index=True
    )