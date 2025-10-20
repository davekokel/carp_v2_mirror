from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()

from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

import os, re
from typing import List, Dict, Any, Set
import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.lib.db import get_engine

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

st.set_page_config(page_title="🧬 Create clutch concepts", page_icon="🧬", layout="wide")
st.title("🧬 Define Cross — Fish, Genotype")

# ─────────────────────────────────────────────────────────────────────────────
# Engine (cache keyed by DB_URL) + DB caption
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _cached_engine(url: str):
    return get_engine()

def _get_engine():
    url = os.getenv("DB_URL")
    if not url:
        st.error("DB_URL not set"); st.stop()
    return _cached_engine(url)

with _get_engine().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

def _view_exists(schema: str, name: str) -> bool:
    with _get_engine().begin() as cx:
        n = pd.read_sql(
            text("select 1 from information_schema.views where table_schema=:s and table_name=:t limit 1"),
            cx, params={"s": schema, "t": name}
        ).shape[0]
    return n > 0

def _stage_choices() -> List[str]:
    if not _view_exists("public", "v_fish_overview_all"):
        return []
    with _get_engine().begin() as cx:
        df = pd.read_sql(text("""
            select distinct line_building_stage
            from public.v_fish_overview_all
            where coalesce(line_building_stage,'') <> ''
            order by 1
        """), cx)
    return [s for s in df["line_building_stage"].astype(str).tolist() if s]

# ─────────────────────────────────────────────────────────────────────────────
# Single-source fish search from v_fish_overview_all
# ─────────────────────────────────────────────────────────────────────────────
def _search_fish_from_view(q: str | None, stages: List[str], limit: int) -> pd.DataFrame:
    where = []
    params: Dict[str, Any] = {"lim": int(limit)}
    if q and q.strip():
        params["qq"] = f"%{q.strip()}%"
        where.append("""
          (fish_code ilike :qq
           or name ilike :qq
           or nickname ilike :qq
           or genetic_background ilike :qq
           or genotype ilike :qq
           or transgene_base_code ilike :qq
           or allele_nickname ilike :qq)
        """)
    if stages:
        params["stages"] = [s.strip() for s in stages if s.strip()]
        if params["stages"]:
            where.append("coalesce(line_building_stage,'') <> '' and line_building_stage = any(:stages)")
    where_sql = (" where " + " and ".join(where)) if where else ""
    sql = text(f"""
      select *
      from public.v_fish_overview_all
      {where_sql}
      order by created_at desc nulls last, fish_code
      limit :lim
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    # display hygiene
    SAFE_TEXT = [
        "fish_code","name","nickname","genetic_background",
        "line_building_stage","description","notes",
        "created_by","transgene_base_code","allele_nickname","zygosity",
        "transgene_base","allele_name",
        "transgene_pretty_nickname","transgene_pretty_name",
        "genotype","genotype_rollup_clean",
    ]
    for c in SAFE_TEXT:
        if c in df.columns:
            df[c] = df[c].astype("string").fillna("")
    if "n_living_tanks" in df.columns:
        df["n_living_tanks"] = pd.to_numeric(df["n_living_tanks"], errors="coerce").fillna(0).astype(int)
    if "allele_number" in df.columns:
        s = pd.to_numeric(df["allele_number"], errors="coerce")
        df["allele_number"] = s.map(lambda x: "" if pd.isna(x) else int(x))
    return df

def _map_codes_to_ids(codes: List[str]) -> Dict[str, str]:
    if not codes:
        return {}
    with _get_engine().begin() as cx:
        ids = pd.read_sql(text("select id, fish_code from public.fish where fish_code = any(:codes)"),
                          cx, params={"codes": codes})
    return dict(zip(ids["fish_code"].astype(str), ids["id"].astype(str)))

# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Select parents (fish)
# ─────────────────────────────────────────────────────────────────────────────
created_by_default = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
created_by = st.text_input("Created by", value=created_by_default)
cross_date = st.date_input("Cross date")

st.header("Step 1 — Select parents (fish)")
with st.form("fish_filters"):
    c1, c2, c3, c4 = st.columns([2,2,1,1])
    with c1:
        q = st.text_input("Filter fish (code/name/nickname/genotype/background)", "")
    with c2:
        try:
            stage_vals = st.multiselect("Stage", _stage_choices(), default=[])
        except Exception:
            stage_vals = []
    with c3:
        limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
    with c4:
        reload_click = st.form_submit_button("Reload from DB")
    submitted = st.form_submit_button("Apply")

# version token so cache invalidates when view changes
with _get_engine().begin() as cx:
    ver = pd.read_sql(text("select count(*)::int as n, coalesce(max(created_at)::text,'') as mx from public.v_fish_overview_all"), cx).iloc[0]
version_token = f"{ver['n']}|{ver['mx']}"
sig_now = f"{q}|{','.join(stage_vals)}|{limit}|{version_token}"

if reload_click:
    st.session_state.pop("_picker_sig", None)
    st.session_state.pop("_picker_src", None)

# fetch raw source df when needed
if submitted or st.session_state.get("_picker_sig") != sig_now or "_picker_src" not in st.session_state:
    src = _search_fish_from_view(q, stage_vals, limit)
    st.session_state["_picker_sig"] = sig_now
    st.session_state["_picker_src"] = src
else:
    src = st.session_state["_picker_src"]

# selection set persisted separately
sel_set: Set[str] = set(st.session_state.get("_picker_sel", []))

if src.empty:
    st.info("No fish match your filters.")
else:
    cols = [
        "fish_code","name","nickname","genetic_background",
        "transgene_base","allele_number","allele_name","allele_nickname",
        "transgene_pretty_nickname","transgene_pretty_name",
        "genotype","genotype_rollup_clean",
        "n_living_tanks","birthday","line_building_stage","created_at","created_by",
    ]
    for c in cols:
        if c not in src.columns:
            src[c] = "" if c != "n_living_tanks" else 0
    view = src[cols].copy()
    view.insert(0, "✓ Select", view["fish_code"].astype(str).isin(sel_set))
    view = view.rename(columns={
        "fish_code":"Fish code",
        "name":"Name",
        "nickname":"Nickname",
        "genetic_background":"Background",
        "transgene_base":"Transgene base",
        "allele_number":"Allele #",
        "allele_name":"Allele name",
        "allele_nickname":"Allele nickname",
        "transgene_pretty_nickname":"Transgene (pretty nickname)",
        "transgene_pretty_name":"Transgene (pretty name)",
        "genotype":"Genotype",
        "genotype_rollup_clean":"Genotype rollup",
        "n_living_tanks":"# living tanks",
        "birthday":"Birth date",
        "line_building_stage":"Stage",
        "created_at":"Created",
        "created_by":"Created by",
    })

    csa, csb = st.columns([1,1])
    with csa:
        if st.button("Select all"):
            sel_set = set(src["fish_code"].astype(str).tolist())
    with csb:
        if st.button("Clear all"):
            sel_set = set()

    edited = st.data_editor(
        view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
            "Fish code": st.column_config.TextColumn("Fish code", disabled=True),
            "Name": st.column_config.TextColumn("Name", disabled=True),
            "Nickname": st.column_config.TextColumn("Nickname", disabled=True),
            "Background": st.column_config.TextColumn("Background", disabled=True),
            "Stage": st.column_config.TextColumn("Stage", disabled=True),
            "Transgene base": st.column_config.TextColumn("Transgene base", disabled=True),
            "Allele #": st.column_config.TextColumn("Allele #", disabled=True),
            "Allele name": st.column_config.TextColumn("Allele name", disabled=True),
            "Allele nickname": st.column_config.TextColumn("Allele nickname", disabled=True),
            "Transgene (pretty nickname)": st.column_config.TextColumn("Transgene (pretty nickname)", disabled=True),
            "Transgene (pretty name)": st.column_config.TextColumn("Transgene (pretty name)", disabled=True),
            "Genotype": st.column_config.TextColumn("Genotype", disabled=True),
            "Genotype rollup": st.column_config.TextColumn("Genotype rollup", disabled=True),
            "# living tanks": st.column_config.NumberColumn("# living tanks", disabled=True, width="small"),
            "Birth date": st.column_config.DateColumn("Birth date", disabled=True, format="YYYY-MM-DD"),
            "Created": st.column_config.DatetimeColumn("Created", disabled=True, format="YYYY-MM-DD HH:mm:ss"),
            "Created by": st.column_config.TextColumn("Created by", disabled=True),
        },
        key="cross_picker_editor",
    )

    # update selection from grid
    if not edited.empty and "✓ Select" in edited.columns and "Fish code" in edited.columns:
        sel_set = set(edited.loc[edited["✓ Select"], "Fish code"].astype(str).tolist())
    st.session_state["_picker_sel"] = list(sel_set)

    # Expose selected codes + IDs
    selected_codes = sorted(list(sel_set))
    id_map = _map_codes_to_ids(selected_codes)
    ids = [id_map.get(c) for c in selected_codes]

    def _clear_parents():
        for k in ("mom_fish_code","mom_fish_id","dad_fish_code","dad_fish_id"):
            st.session_state.pop(k, None)

    def _assign_parents_from_selection():
        if len(selected_codes) == 0:
            _clear_parents()
        elif len(selected_codes) == 1:
            st.session_state["mom_fish_code"] = selected_codes[0]
            st.session_state["mom_fish_id"]   = ids[0]
            st.session_state.pop("dad_fish_code", None)
            st.session_state.pop("dad_fish_id", None)
        else:
            st.session_state["mom_fish_code"] = selected_codes[0]
            st.session_state["mom_fish_id"]   = ids[0]
            st.session_state["dad_fish_code"] = selected_codes[1]
            st.session_state["dad_fish_id"]   = ids[1]

    _assign_parents_from_selection()

    c1, c2 = st.columns(2)
    with c1:
        swap_disabled = not (st.session_state.get("mom_fish_code") and st.session_state.get("dad_fish_code"))
        if st.button("Swap Mom/Dad", use_container_width=True, disabled=swap_disabled):
            st.session_state["mom_fish_code"], st.session_state["dad_fish_code"] = (
                st.session_state.get("dad_fish_code"),
                st.session_state.get("mom_fish_code"),
            )
            st.session_state["mom_fish_id"], st.session_state["dad_fish_id"] = (
                st.session_state.get("dad_fish_id"),
                st.session_state.get("mom_fish_id"),
            )
    with c2:
        if st.button("Clear Mom/Dad", use_container_width=True):
            _clear_parents()

    st.write(f"**Mom (A) — fish:** {st.session_state.get('mom_fish_code','—')}")
    st.write(f"**Dad (B) — fish:** {st.session_state.get('dad_fish_code','—')}")

# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Genotype inheritance (same logic as before)
# ─────────────────────────────────────────────────────────────────────────────
st.header("Step 2 — Genotype inheritance")

mom_code = st.session_state.get("mom_fish_code")
dad_code = st.session_state.get("dad_fish_code")

def _fetch_parent_rows(codes: list[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=[
            "fish_code","name","nickname","genotype","genetic_background","stage","date_birth","created_at",
            "transgene_pretty_name"
        ])
    sql_base = text("""
      select fish_code, name, nickname, genotype, genetic_background, stage, date_birth, created_at
      from public.vw_fish_standard
      where fish_code = any(:codes)
    """)
    with _get_engine().begin() as cx:
        try:
            df = pd.read_sql(sql_base, cx, params={"codes": codes})
        except Exception:
            df = pd.read_sql(text("""
                select
                  fish_code,
                  name,
                  nickname,
                  genotype_print  as genotype,
                  coalesce(genetic_background_print, genetic_background) as genetic_background,
                  coalesce(line_building_stage, line_building_stage_print) as stage,
                  date_birth_print::date as date_birth,
                  created_at
                from public.vw_fish_overview_with_label
                where fish_code = any(:codes)
            """), cx, params={"codes": codes})
    try:
        clean = pd.read_sql(text("""
            select fish_code, transgene_pretty_name
            from public.v_fish_standard_clean
            where fish_code = any(:codes)
        """), _get_engine(), params={"codes": codes})
    except Exception:
        clean = pd.DataFrame(columns=["fish_code","transgene_pretty_name"])
    if not clean.empty:
        df = df.merge(clean, on="fish_code", how="left")
    else:
        if "transgene_pretty_name" not in df.columns:
            df["transgene_pretty_name"] = ""
    return df

def _split_genotype(g: str) -> list[str]:
    if not g:
        return []
    parts = [p.strip() for p in re.split(r"[;,|]+", str(g)) if p and p.strip()]
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p); out.append(p)
    return out

if not (mom_code or dad_code):
    st.info("Pick parent fish above to preview and select genotype elements.")
else:
    codes = [c for c in [mom_code, dad_code] if c]
    parents = _fetch_parent_rows(codes)
    by_code = {r["fish_code"]: r for _, r in parents.iterrows()} if not parents.empty else {}

    def _parent_block(label: str, code: str, key_prefix: str):
        col = st.container()
        with col:
            st.subheader(label)
            if not code:
                st.caption("— not set —")
                return pd.DataFrame(columns=["element","inherit?","source"])
            row = by_code.get(code)
            if row is None:
                st.warning(f"{code}: not found"); return pd.DataFrame(columns=["element","inherit?","source"])
            st.markdown(f"**{code}** — {row.get('name') or ''}")
            meta = {
                "nickname": row.get("nickname"),
                "stage": row.get("stage"),
                "genetic_background": row.get("genetic_background"),
                "date_birth": row.get("date_birth"),
            }
            show_meta = {k: v for k, v in meta.items() if v not in (None, "", pd.NaT)}
            if show_meta:
                st.write(show_meta)
            tpn = (row.get("transgene_pretty_name") or "").strip()
            elems = [tpn] if tpn else _split_genotype((row.get("genotype") or "").strip())
            if not elems:
                st.info("No genotype text available for this fish.")
                return pd.DataFrame(columns=["element","inherit?","source"])
            state_key = f"{key_prefix}_inherit_df"
            state_sig = f"{key_prefix}_sig"
            sig = "|".join(elems)
            if st.session_state.get(state_sig) != sig:
                base = pd.DataFrame({"element": elems})
                base["inherit?"] = True
                base["source"] = label.split(" ")[0]
                old = st.session_state.get(state_key)
                if isinstance(old, pd.DataFrame) and "element" in old.columns:
                    if "inherit?" not in old.columns:
                        old = old.assign(**{"inherit?": True})
                    old_small = old[["element","inherit?"]].copy()
                    merged = base.merge(old_small, on="element", how="left", suffixes=("", "_old"))
                    if "inherit?_old" in merged.columns:
                        merged["inherit?"] = merged["inherit?_old"].where(merged["inherit?_old"].notna(), merged["inherit?"])
                        merged = merged.drop(columns=["inherit?_old"])
                    base = merged
                st.session_state[state_key] = base
                st.session_state[state_sig] = sig
            df_edit = st.session_state[state_key].copy()
            ca, cb = st.columns([1,1])
            with ca:
                if st.button(f"Select all ({label})", use_container_width=True):
                    df_edit["inherit?"] = True
            with cb:
                if st.button(f"Clear all ({label})", use_container_width=True):
                    df_edit["inherit?"] = False
            df_edit = st.data_editor(
                df_edit,
                use_container_width=True,
                hide_index=True,
                column_order=["inherit?","element","source"],
                column_config={
                    "element":  st.column_config.TextColumn("element", disabled=True),
                    "inherit?": st.column_config.CheckboxColumn("inherit?", default=True),
                    "source":   st.column_config.TextColumn("source", disabled=True),
                },
                key=f"{key_prefix}_editor",
            )
            st.session_state[state_key] = df_edit.copy()
            return df_edit

    c1, c2 = st.columns(2)
    with c1:
        mom_df = _parent_block("Mom (A)", mom_code, "mom")
    with c2:
        dad_df = _parent_block("Dad (B)", dad_code, "dad")

    st.subheader("Selected elements for clutch")
    sel_frames = []
    if isinstance(mom_df, pd.DataFrame) and not mom_df.empty:
        sel_frames.append(mom_df[mom_df["inherit?"]][["element","source"]])
    if isinstance(dad_df, pd.DataFrame) and not dad_df.empty:
        sel_frames.append(dad_df[dad_df["inherit?"]][["element","source"]])
    if not sel_frames:
        st.info("No elements selected yet.")
    else:
        combined = pd.concat(sel_frames, ignore_index=True) if len(sel_frames) > 0 else pd.DataFrame(columns=["element","source"])
        combined = combined.drop_duplicates(subset=["element"], keep="first")
        st.dataframe(combined.reset_index(drop=True), use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Save clutch concept
# ─────────────────────────────────────────────────────────────────────────────
st.header("Step 3 — Save clutch concept")

def _selected_genotype_elements() -> list[str]:
    elems = []
    for key in ("mom_inherit_df", "dad_inherit_df"):
        df = st.session_state.get(key)
        if isinstance(df, pd.DataFrame) and {"inherit?","element"}.issubset(df.columns):
            elems.extend(df[df["inherit?"]]["element"].astype(str).tolist())
    seen, out = set(), []
    for e in elems:
        if e not in seen:
            seen.add(e); out.append(e)
    return out

def _format_genotype_elements(elems: list[str]) -> str:
    out = []
    for e in elems:
        e = (e or "").strip()
        m = re.match(r"^\s*([A-Za-z0-9\-]+)\s*(?:[\-\^])\s*(\d+)\s*$", e)
        if m:
            base, num = m.group(1), m.group(2)
            out.append(f"Tg({base}){num}")
        else:
            out.append(e)
    return "; ".join(out) if out else "planned-clutch"

mom_code = st.session_state.get("mom_fish_code")
dad_code = st.session_state.get("dad_fish_code")

if not (mom_code and dad_code):
    st.info("Pick Mom and Dad in Step 1 to enable saving.")
else:
    auto_name = _format_genotype_elements(_selected_genotype_elements())
    colA, colB = st.columns(2)
    with colA:
        st.text_input("planned_clutch_name", value=auto_name, disabled=True)
    with colB:
        planned_clutch_nickname = st.text_input("planned_clutch_nickname (optional)", value=auto_name)
    save_note = st.text_input("Optional clutch note", "")
    save_btn = st.button("💾 Save clutch concept", type="primary", use_container_width=True)
    if save_btn:
        ins_hdr = text("""
          insert into public.clutch_plans
            (mom_code, dad_code, cross_date, note, created_by, planned_name, planned_nickname)
          values
            (:mom, :dad, :xdate, :note, :by, :pname, :pnick)
          returning id
        """)
        with _get_engine().begin() as cx:
            cid = cx.execute(ins_hdr, {
                "mom": mom_code,
                "dad": dad_code,
                "xdate": pd.to_datetime(cross_date).date(),
                "note": save_note,
                "by": (created_by or "").strip() or (os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"),
                "pname": auto_name,
                "pnick": (planned_clutch_nickname or "").strip() or auto_name,
            }).scalar()
        st.success("Clutch concept saved.")
        st.session_state["last_clutch_plan_id"] = str(cid)

# ─────────────────────────────────────────────────────────────────────────────
# Planned clutches (recent) — mom/dad details from the same view
# ─────────────────────────────────────────────────────────────────────────────
with _get_engine().begin() as cx:
    base = pd.read_sql(text("""
      with tx_counts as (
        select clutch_id, count(*) as n_treatments
        from public.clutch_plan_treatments
        group by clutch_id
      )
      select
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
      order by p.created_at desc
      limit 100
    """), cx)

st.subheader("Planned clutches (recent)")
if base.empty:
    st.info("No planned clutches yet.")
else:
    codes = sorted(set(base["mom_code"].dropna().astype(str).tolist() + base["dad_code"].dropna().astype(str).tolist()))
    if codes:
        with _get_engine().begin() as cx:
            mom = pd.read_sql(text("""
              select fish_code,
                     genetic_background as mom_background,
                     genotype_rollup_clean as mom_genotype_rollup,
                     n_living_tanks as mom_n_living_tanks,
                     birthday as mom_birth
              from public.v_fish_overview_all
              where fish_code = any(:codes)
            """), cx, params={"codes": codes})
            dad = mom.rename(columns={
                "fish_code":"dad_code",
                "mom_background":"dad_background",
                "mom_genotype_rollup":"dad_genotype_rollup",
                "mom_n_living_tanks":"dad_n_living_tanks",
                "mom_birth":"dad_birth",
            }).copy()
            mom = mom.rename(columns={"fish_code":"mom_code"})
        out = base.merge(mom, on="mom_code", how="left").merge(dad, on="dad_code", how="left").fillna({"mom_n_living_tanks":0, "dad_n_living_tanks":0})
    else:
        out = base.copy()
    show_cols = [
        "clutch_code","name","nickname",
        "mom_code","mom_background","mom_genotype_rollup","mom_n_living_tanks","mom_birth",
        "dad_code","dad_background","dad_genotype_rollup","dad_n_living_tanks","dad_birth",
        "n_treatments","created_by","created_at"
    ]
    show_cols = [c for c in show_cols if c in out.columns]
    view2 = out[show_cols].rename(columns={
        "clutch_code":"Clutch",
        "name":"Planned name",
        "nickname":"Planned nickname",
        "mom_code":"Mom FSH",
        "mom_background":"Mom background",
        "mom_genotype_rollup":"Mom genotype rollup",
        "mom_n_living_tanks":"Mom # living tanks",
        "mom_birth":"Mom birth date",
        "dad_code":"Dad FSH",
        "dad_background":"Dad background",
        "dad_genotype_rollup":"Dad genotype rollup",
        "dad_n_living_tanks":"Dad # living tanks",
        "dad_birth":"Dad birth date",
        "n_treatments":"# tx",
        "created_by":"Created by",
        "created_at":"Created",
    })
    st.dataframe(view2, use_container_width=True, hide_index=True)