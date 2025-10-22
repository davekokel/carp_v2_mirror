from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()

from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

import os, re
from typing import List, Dict, Any, Set, Optional, Tuple
import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.lib.db import get_engine

# ✅ Page config must be the first Streamlit call
st.set_page_config(page_title="🧬 Define Cross — Fish, Genotype", page_icon="🧬", layout="wide")
st.title("🧬 Define Cross — Fish, Genotype")

# Debug fingerprint so we know we’re editing the file the app runs
import hashlib, pathlib as _pl
_srcp = _pl.Path(__file__).resolve()
st.caption("SRC=" + str(_srcp.name) + " • SHA256=" + hashlib.sha256(_srcp.read_bytes()).hexdigest()[:12])

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

# ─────────────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _cached_engine(url: str):
    return get_engine()

def _eng():
    url = os.getenv("DB_URL")
    if not url:
        st.error("DB_URL not set"); st.stop()
    return _cached_engine(url)

with _eng().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _view_exists(schema: str, name: str) -> bool:
    with _eng().begin() as cx:
        n = pd.read_sql(
            text("select 1 from information_schema.views where table_schema=:s and table_name=:t limit 1"),
            cx, params={"s": schema, "t": name}
        ).shape[0]
    return n > 0

def _table_exists(schema: str, name: str) -> bool:
    with _eng().begin() as cx:
        n = pd.read_sql(
            text("select 1 from information_schema.tables where table_schema=:s and table_name=:t limit 1"),
            cx, params={"s": schema, "t": name}
        ).shape[0]
    return n > 0

# ─────────────────────────────────────────────────────────────────────────────
# Enriched fish search (tank-centric; no stage dependency)
# ─────────────────────────────────────────────────────────────────────────────
def _search_fish_enriched(q: Optional[str], stages: List[str], limit: int) -> pd.DataFrame:
    where = []
    params: Dict[str, Any] = {"lim": int(limit)}
    if q and q.strip():
        params["qq"] = f"%{q.strip()}%"
        where.append("""
          (f.fish_code ilike :qq
           or f.name ilike :qq
           or f.nickname ilike :qq
           or f.genetic_background ilike :qq
           or ta.allele_nickname ilike :qq
           or fta.transgene_base_code ilike :qq
           or ('Tg(' || fta.transgene_base_code || ')' || ta.allele_name) ilike :qq)
        """)
    where_sql = (" where " + " and ".join(where)) if where else ""

    sql = text(f"""
        with alleles as (
            select
            f.id                           as fish_id,
            f.fish_code,
            f.name,
            f.nickname,
            f.genetic_background,
            f.genotype,
            null::text                     as line_building_stage,  -- stub, keep grid shape
            f.date_birth                   as birthday,
            f.created_at,
            f.created_by,
            fta.transgene_base_code,
            fta.allele_number,
            ta.allele_name,
            ta.allele_nickname::text      as allele_nickname,
            ('Tg(' || fta.transgene_base_code || ')' || ta.allele_name) as transgene_pretty
            from public.fish f
            left join public.fish_transgene_alleles fta on fta.fish_id = f.id
            left join public.transgene_alleles ta
                on ta.transgene_base_code = fta.transgene_base_code
                and ta.allele_number       = fta.allele_number
        ),
        geno as (
            select
            a.fish_code,
            string_agg(a.transgene_pretty, '; ' order by a.transgene_pretty) as genotype_rollup
            from alleles a
            group by a.fish_code
        ),
        tanks as (
            -- IMPORTANT: join v_tanks by fish_code (v_tanks has no fish_id)
            select
            f.id as fish_id,
            vt.tank_code::text as tank_code,
            vt.status::text    as tank_status
            from public.fish f
            left join public.v_tanks vt on vt.fish_code = f.fish_code
        )
        select
            a.fish_code,
            a.name,
            a.nickname,
            a.genetic_background,
            a.genotype,
            a.line_building_stage,
            a.birthday,
            a.created_at,
            a.created_by,
            a.transgene_base_code   as transgene_base,
            a.allele_number,
            a.allele_name,
            a.allele_nickname,
            a.transgene_pretty      as transgene_pretty_name,
            a.transgene_pretty      as transgene_pretty_nickname,
            g.genotype_rollup       as genotype_rollup_clean,
            coalesce(t.tank_code, '')   as tank_code,
            coalesce(t.tank_status, '') as tank_status,
            0::int as n_living_tanks
        from alleles a
        left join geno  g on g.fish_code = a.fish_code
        left join tanks t on t.fish_id = a.fish_id
        {where_sql}
        order by a.created_at desc nulls last, a.fish_code
        limit :lim
        """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    # hygiene
    for c in ["fish_code","name","nickname","genetic_background","genotype",
              "line_building_stage","created_by","transgene_base","allele_name","allele_nickname",
              "transgene_pretty_nickname","transgene_pretty_name","genotype_rollup_clean","tank_code","tank_status"]:
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
    with _eng().begin() as cx:
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
        stage_vals: List[str] = []
        st.caption("Stage filter not available in this DB shape.")
    with c3:
        limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
    with c4:
        action = st.radio("Action", ("Apply", "Reload"), horizontal=True, label_visibility="collapsed")
    submitted = st.form_submit_button("Run")

if submitted and action == "Reload":
    st.session_state.pop("_picker_sig", None)
    st.session_state.pop("_picker_src", None)

with _eng().begin() as cx:
    ver = pd.read_sql(text("select count(*)::int as n, coalesce(max(created_at)::text,'') as mx from public.fish"), cx).iloc[0]
version_token = f"{ver['n']}|{ver['mx']}"
sig_now = f"{q}|{','.join(stage_vals)}|{limit}|{version_token}"

if submitted or st.session_state.get("_picker_sig") != sig_now or "_picker_src" not in st.session_state:
    src = _search_fish_enriched(q, stage_vals, limit)
    st.session_state["_picker_sig"] = sig_now
    st.session_state["_picker_src"] = src
else:
    src = st.session_state["_picker_src"]

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
        "name":"Fish name",
        "nickname":"Fish nickname",
        "genetic_background":"Genetic background",
        "transgene_base":"Transgene base code",
        "allele_number":"Allele number",
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
            "Fish name": st.column_config.TextColumn("Fish name", disabled=True),
            "Fish nickname": st.column_config.TextColumn("Fish nickname", disabled=True),
            "Genetic background": st.column_config.TextColumn("Genetic background", disabled=True),
            "Stage": st.column_config.TextColumn("Stage", disabled=True),
            "Transgene base code": st.column_config.TextColumn("Transgene base code", disabled=True),
            "Allele number": st.column_config.TextColumn("Allele number", disabled=True),
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

    if not edited.empty and "✓ Select" in edited.columns and "Fish code" in edited.columns:
        sel_set = set(edited.loc[edited["✓ Select"], "Fish code"].astype(str).tolist())
    st.session_state["_picker_sel"] = list(sel_set)

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
# Step 2 — Genotype inheritance
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
    with _eng().begin() as cx:
        df = pd.read_sql(text("""
            select
              fish_code,
              name,
              nickname,
              genotype,
              genetic_background,
              null::text as stage,
              date_birth as date_birth,
              created_at
            from public.v_fish
            where fish_code = any(:codes)
        """), cx, params={"codes": codes})
        pretty = df[["fish_code","genotype"]].rename(columns={"genotype":"transgene_pretty_name"})
    return df.merge(pretty, on="fish_code", how="left")

def _split_genotype(g: str) -> list[str]:
    if not g:
        return []
    parts = [p.strip() for p in re.split(r"[;,|]+", str(g)) if p and p.strip()]
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p); out.append(p)
    return out

# ————————— parent genotype pickers —————————
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
# Step 3 — Create a tank_pair (and optionally a run)
# ─────────────────────────────────────────────────────────────────────────────
st.header("Step 3 — Create tank pair (and optionally schedule run)")

def _tanks_for_fish(fish_code: str) -> pd.DataFrame:
    if not fish_code:
        return pd.DataFrame(columns=["tank_id","tank_code","status","tank_created_at"])
    sql = text("""
      select tank_id::uuid, tank_code, status, tank_created_at
      from public.v_tanks
      where fish_code = :code and status in ('active','new_tank')
      order by tank_created_at desc nulls last, tank_code
    """)
    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params={"code": fish_code})

mom_code = st.session_state.get("mom_fish_code") or ""
dad_code = st.session_state.get("dad_fish_code") or ""

mtanks = _tanks_for_fish(mom_code)
dtanks = _tanks_for_fish(dad_code)

cmt, cdt = st.columns(2)
with cmt:
    st.caption("Mother tank")
    mom_tank_code = st.selectbox(
        "Pick mother tank", options=([""] + mtanks["tank_code"].astype(str).tolist()),
        index=0, key="pick_mom_tank"
    )
with cdt:
    st.caption("Father tank")
    dad_tank_code = st.selectbox(
        "Pick father tank", options=([""] + dtanks["tank_code"].astype(str).tolist()),
        index=0, key="pick_dad_tank"
    )

def _tank_id_by_code(df: pd.DataFrame, code: str) -> Optional[str]:
    if not code or df.empty: return None
    row = df.loc[df["tank_code"] == code]
    return (row["tank_id"].astype(str).iloc[0] if not row.empty else None)

mom_tank_id = _tank_id_by_code(mtanks, mom_tank_code)
dad_tank_id = _tank_id_by_code(dtanks, dad_tank_code)

colA, colB = st.columns([1,1])
with colA:
    auto_schedule = st.checkbox("Schedule run now", value=True)
with colB:
    run_note = st.text_input("Run note (optional)", "")

def _create_tank_pair_and_maybe_run(mom_tid: str, dad_tid: str, created_by: str, auto_run: bool, run_note: str, run_date) -> Tuple[str, Optional[str]]:
    """
    Returns (tank_pair_code, cross_run_code|None)
    """
    sql = text("""
      with next_tp as (
        select
          'TP-'||to_char(extract(year from now())::int % 100,'FM00')||
          lpad( (select coalesce(max( (regexp_match(coalesce(tank_pair_code,''),'^TP-\\d{2}(\\d{4})$'))[1]::int ),0) + 1
                 from public.tank_pairs
                 where tank_pair_code like 'TP-'||to_char(extract(year from now())::int % 100,'FM00')||'%'
               )::text, 4, '0') as tp_code
      ),
      ins_tp as (
        insert into public.tank_pairs (mother_tank_id, father_tank_id, tank_pair_code, status, created_by)
        select cast(:mom_tid as uuid), cast(:dad_tid as uuid), (select tp_code from next_tp), 'selected', :by
        returning id, tank_pair_code
      )
      select id::uuid as tp_id, tank_pair_code from ins_tp
    """)
    cr_sql = text("""
      with next_cr as (
        select
          'CR-'||to_char(extract(year from now())::int % 100,'FM00')||
          lpad( (select coalesce(max( (regexp_match(coalesce(cross_run_code,''),'^CR-\\d{2}(\\d{3})$'))[1]::int ),0) + 1
                 from public.cross_instances
                 where cross_run_code like 'CR-'||to_char(extract(year from now())::int % 100,'FM00')||'%'
               )::text, 3, '0') as cr_code
      ),
      ins_cr as (
        insert into public.cross_instances (tank_pair_id, cross_run_code, cross_date, note, created_by)
        select cast(:tp_id as uuid), (select cr_code from next_cr), :rundate, nullif(:note,''), :by
        returning cross_run_code
      )
      select cross_run_code from ins_cr
    """)
    with _eng().begin() as cx:
        rec = cx.execute(sql, {"mom_tid": mom_tid, "dad_tid": dad_tid, "by": created_by}).mappings().one()
        tp_id = str(rec["tp_id"]); tp_code = str(rec["tank_pair_code"])
        cr_code = None
        if auto_run:
            cr_code = cx.execute(cr_sql, {
                "tp_id": tp_id,
                "rundate": pd.to_datetime(run_date).date(),
                "note": run_note or "",
                "by": created_by
            }).scalar()
    return tp_code, (str(cr_code) if cr_code else None)

can_make = bool(mom_code and dad_code and mom_tank_id and dad_tank_id)
if not (mom_code and dad_code):
    st.info("Pick Mom and Dad first.")
elif not (mom_tank_id and dad_tank_id):
    st.info("Pick a mother tank and a father tank.")
else:
    creator = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
    if st.button("💾 Create tank pair" + (" + schedule run" if auto_schedule else ""), type="primary", use_container_width=True):
        try:
            tp_code, cr_code = _create_tank_pair_and_maybe_run(
                mom_tank_id, dad_tank_id, creator, auto_schedule, run_note, cross_date
            )
            if cr_code:
                st.success(f"Created tank_pair **{tp_code}** and scheduled run **{cr_code}**.")
            else:
                st.success(f"Created tank_pair **{tp_code}**.")
        except Exception as e:
            st.error(f"Create failed: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Planned clutches (recent) — read from v_clutches
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("Recent clutches / runs (from v_clutches)")
try:
    lim = 50
    with _eng().begin() as cx:
        out = pd.read_sql(text("""
          select clutch_code, cross_run_code, mom_code, dad_code, clutch_birthday, created_at
          from public.v_clutches
          order by created_at desc nulls last
          limit :lim
        """), cx, params={"lim": lim})
    if out.empty:
        st.info("No clutches or runs yet.")
    else:
        st.dataframe(out, use_container_width=True, hide_index=True)
except Exception as e:
    st.info("v_clutches not present or empty.")