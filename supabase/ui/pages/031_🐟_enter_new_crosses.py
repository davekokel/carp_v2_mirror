from __future__ import annotations
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import os
from typing import Any, Dict, List
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# =================================
# Page config
# =================================
st.set_page_config(page_title="🐟 Plan new crosses", page_icon="🐟", layout="wide")
st.title("🐟 Plan new crosses")

# 🔒 optional unlock
try:
    from supabase.ui.auth_gate import require_app_unlock
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
    _ENGINE = create_engine(url, future=True)
    return _ENGINE

# =================================
# Helpers: cross name & nickname
# =================================
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

def _get_or_create_cross_and_set_nickname(mom_code: str, dad_code: str, created_by: str, nickname: str | None) -> tuple[str, str]:
    """
    Returns (cross_id, cross_code).
    Reuses an existing concept for mom×dad if present; otherwise inserts one.
    Always updates cross_nickname to the provided value (or the computed cross_name).
    """
    wanted_nick = nickname or _compute_cross_name(mom_code, dad_code)
    with _get_engine().begin() as cx:
        # Try to find existing concept (case-insensitive on codes)
        row = cx.execute(
            text("""
              SELECT id_uuid::text, COALESCE(cross_code, id_uuid::text)
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
                text("UPDATE public.crosses SET cross_nickname = :nick WHERE id_uuid = :id"),
                {"nick": wanted_nick, "id": cross_id},
            )
        else:
            cross_id, cross_code = cx.execute(
                text("""
                  INSERT INTO public.crosses (mother_code, father_code, created_by, cross_nickname)
                  VALUES (:m, :d, :by, :nick)
                  RETURNING id_uuid::text, COALESCE(cross_code, id_uuid::text)
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
        p.id_uuid::text                          as clutch_id,
        coalesce(p.clutch_code, p.id_uuid::text) as clutch_code,
        coalesce(p.planned_name,'')              as name,
        coalesce(p.planned_nickname,'')          as nickname,
        p.mom_code,
        p.dad_code,
        coalesce(t.n_treatments,0)               as n_treatments,
        p.created_by,
        p.created_at
      from public.clutch_plans p
      left join tx_counts t on t.clutch_id = p.id_uuid
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
        coalesce(c.label,'')   as tank_label,
        coalesce(c.status,'')  as tank_status
      from public.fish f
      join public.fish_tank_memberships m on m.fish_id = f.id and m.left_at is null
      join public.containers c on c.id_uuid = m.container_id
      where c.container_type in ('inventory_tank','holding_tank','nursery_tank')
        and c.status = any(:live_statuses)
      order by f.fish_code, c.label
    """), cx, params={"live_statuses": list(LIVE_STATUSES)})

live_by_fish: Dict[str, List[Dict[str, str]]] = {}
for _, r in df_live.iterrows():
    live_by_fish.setdefault(r["fish_code"], []).append({
        "id":     r["tank_id"],
        "label":  r["tank_label"],
        "status": r["tank_status"],
    })

assignments: List[Dict[str, Any]] = []
for _, r in picked.iterrows():
    with st.expander(f"{r['clutch_code']} — {r['name'] or r['nickname']}", expanded=False):

        # --- Cross naming UI (concept-level) ---
        computed_name = _compute_cross_name(r["mom_code"], r["dad_code"])
        st.caption(f"Cross name (computed): **{computed_name}**")
        nick_key = f"nick_{r['clutch_code']}"
        cross_nickname = st.text_input("Cross nickname (optional)", value=st.session_state.get(nick_key, computed_name), key=nick_key)

        # Previous live tanks
        st.caption("Previously used tanks (live)")
        with _get_engine().begin() as cx:
            prev = pd.read_sql(text("""
              select
                cm.label as mother_tank, coalesce(cm.status,'') as mother_status,
                cf.label as father_tank, coalesce(cf.status,'') as father_status,
                pc.created_at
              from public.planned_crosses pc
              left join public.containers cm on cm.id_uuid = pc.mother_tank_id
              left join public.containers cf on cf.id_uuid = pc.father_tank_id
              where pc.clutch_id = :clutch_id
                and (coalesce(cm.status,'') = any(:live_statuses)
                     or coalesce(cf.status,'') = any(:live_statuses))
              order by pc.created_at desc
              limit 10
            """), cx, params={"clutch_id": r["clutch_id"], "live_statuses": list(LIVE_STATUSES)})

        if prev.empty:
            st.info("No live previous tanks found for this clutch.")
        else:
            st.dataframe(prev[["mother_tank","mother_status","father_tank","father_status","created_at"]],
                         use_container_width=True, hide_index=True)

        # Mother tank pick
        mom_list = live_by_fish.get(r["mom_code"], [])
        if not mom_list:
            st.warning(f"No live mother tanks for {r['mom_code']} (need status active or new_tank).")
            mom_pick = None; mom_map = {}
        else:
            mom_df = pd.DataFrame(mom_list)
            mom_df.insert(0, "✓ Mother", False)
            mom_table = st.data_editor(
                mom_df.rename(columns={"label":"label","status":"status"}),
                use_container_width=True, hide_index=True,
                column_order=["✓ Mother","label","status"],
                column_config={
                    "✓ Mother": st.column_config.CheckboxColumn("✓ Mother", default=False),
                    "label":    st.column_config.TextColumn("label", disabled=True),
                    "status":   st.column_config.TextColumn("status", disabled=True),
                },
                key=f"mom_tbl_{r['clutch_code']}",
            )
            checked = mom_table[mom_table["✓ Mother"]]
            mom_pick = None if checked.empty else str(checked.iloc[0]["label"])
            mom_map  = {t["label"]: t["id"] for t in mom_list}

        # Father tank pick
        dad_list = live_by_fish.get(r["dad_code"], [])
        if not dad_list:
            st.warning(f"No live father tanks for {r['dad_code']} (need status active or new_tank).")
            dad_pick = None; dad_map = {}
        else:
            dad_df = pd.DataFrame(dad_list)
            dad_df.insert(0, "✓ Father", False)
            dad_table = st.data_editor(
                dad_df.rename(columns={"label":"label","status":"status"}),
                use_container_width=True, hide_index=True,
                column_order=["✓ Father","label","status"],
                column_config={
                    "✓ Father": st.column_config.CheckboxColumn("✓ Father", default=False),
                    "label":    st.column_config.TextColumn("label", disabled=True),
                    "status":   st.column_config.TextColumn("status", disabled=True),
                },
                key=f"dad_tbl_{r['clutch_code']}",
            )
            checked = dad_table[dad_table["✓ Father"]]
            dad_pick = None if checked.empty else str(checked.iloc[0]["label"])
            dad_map  = {t["label"]: t["id"] for t in dad_list}

        note = st.text_input("Note (optional)", key=f"note_{r['clutch_code']}")

        assignments.append({
            "clutch_id":      r["clutch_id"],
            "clutch_code":    r["clutch_code"],
            "mom_code":       r["mom_code"],
            "dad_code":       r["dad_code"],
            "m_label":        mom_pick,
            "f_label":        dad_pick,
            "note":           note,
            "cross_nickname": cross_nickname,  # <-- new
            "_mom_map":       mom_map,
            "_dad_map":       dad_map,
        })

# =================================
# Save planned crosses
# =================================
save_btn = st.button("Save planned crosses", type="primary", use_container_width=True)
if save_btn:
    if not assignments:
        st.warning("Nothing to save.")
    else:
        saved, errors = 0, []
        with _get_engine().begin() as cx:
            ins_planned = text("""
              insert into public.planned_crosses
                (clutch_id, mom_code, dad_code, mother_tank_id, father_tank_id, note, created_by)
              values
                (:clutch_id, :mom, :dad, :m_id, :f_id, :note, :by)
              returning id_uuid
            """)
            link_back = text("""
              update public.planned_crosses
              set cross_id = :cross_id, cross_code = :cross_code
              where id_uuid = :planned_id
            """)

            for a in assignments:
                if not a["m_label"] or not a["f_label"]:
                    errors.append(f"{a['clutch_code']}: pick both mother and father tanks")
                    continue

                m_id = a["_mom_map"].get(a["m_label"])
                f_id = a["_dad_map"].get(a["f_label"])
                if not m_id or not f_id:
                    errors.append(f"{a['clutch_code']}: could not resolve selected tank ids")
                    continue

                # 1) insert planned_cross
                planned_id = cx.execute(ins_planned, {
                    "clutch_id": a["clutch_id"],
                    "mom": a["mom_code"], "dad": a["dad_code"],
                    "m_id": m_id, "f_id": f_id,
                    "note": a["note"], "by": user_by,
                }).scalar()

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
        coalesce(pc.cross_code, pc.id_uuid::text) as cross_code,
        cp.clutch_code,
        cp.planned_name,
        pc.mom_code,
        pc.dad_code,
        cm.label as mother_tank,
        cf.label as father_tank,
        pc.created_at
      from public.planned_crosses pc
      join public.clutch_plans cp on cp.id_uuid = pc.clutch_id
      left join public.containers cm on cm.id_uuid = pc.mother_tank_id
      left join public.containers cf on cf.id_uuid = pc.father_tank_id
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