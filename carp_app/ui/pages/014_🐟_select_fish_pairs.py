# =============================================================================
# 🐟 Select fish pairs — conceptual (no tank_pairs or runs on this page)
#      Unordered conceptual pair; links to conceptual clutches explicitly
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()

from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

import os, re, hashlib, pathlib as _pl
from typing import List, Dict, Any, Set, Optional
import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.ui.lib.app_ctx import get_engine

st.set_page_config(page_title="🐟 Select fish pairs", page_icon="🐟", layout="wide")
st.title("🐟 Select fish pairs")

_srcp = _pl.Path(__file__).resolve()
st.caption("SRC=" + str(_srcp.name) + " • SHA256=" + hashlib.sha256(_srcp.read_bytes()).hexdigest()[:12])

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

# =============================================================================
# Helpers
# =============================================================================

@st.cache_data(show_spinner=False)

def _pick_fish_view() -> str:
    with _eng().begin() as cx:
        rows = pd.read_sql(
            text("""select table_name
                    from information_schema.views
                    where table_schema='public'
                      and table_name in ('v_fish_rich','v_fish')"""),
            cx
        )
    names = set(rows["table_name"].tolist())
    return "public.v_fish_richrich" if "v_fish_rich" in names else "public.v_fish"

@st.cache_data(show_spinner=False)
def _fish_cols(view: str) -> list[str]:
    schema, tbl = view.split(".", 1)
    with _eng().begin() as cx:
        df = pd.read_sql(
            text("""select column_name
                    from information_schema.columns
                    where table_schema=:s and table_name=:t
                    order by ordinal_position"""),
            cx,
            params={"s": schema, "t": tbl}
        )
    return df["column_name"].tolist()

def _has(col: str, cols: list[str]) -> bool:
    return col in cols

def _split_genotype(g: str) -> list[str]:
    if not g:
        return []
    parts = [p.strip() for p in re.split(r"[;,|]+", str(g)) if p and p.strip()]
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p); out.append(p)
    return out

def _default_expected_genotype(combined_df: pd.DataFrame, mom_code: str, dad_code: str) -> str:
    if isinstance(combined_df, pd.DataFrame) and not combined_df.empty and "element" in combined_df.columns:
        return "; ".join(combined_df["element"].astype(str).tolist())
    saved = st.session_state.get("planned_genotype_elements") or []
    if saved:
        return "; ".join([str(x) for x in saved])
    view = _pick_fish_view()
    cols = _fish_cols(view)
    pick = "transgene_pretty_name" if _has("transgene_pretty_name", cols) else ("genotype_rollup" if _has("genotype_rollup", cols) else None)
    if not pick:
        return ""
    try:
        with _eng().begin() as cx:
            df = pd.read_sql(
                text(f"select fish_code, {pick} as g from {view} where fish_code = any(:codes)"),
                cx,
                params={"codes": [c for c in (mom_code, dad_code) if c]}
            )
        toks = set()
        for g in df["g"].dropna():
            for t in re.split(r"[;,|]+", str(g)):
                t = t.strip()
                if t:
                    toks.add(t)
        return "; ".join(sorted(toks))
    except Exception:
        return ""

# =============================================================================
# STEP 1 — FISH SEARCH + ROW CHECKBOX SELECTION (UNORDERED PAIR)
# =============================================================================
created_by_default = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
created_by = st.text_input("Created by", value=created_by_default)

@st.cache_data(show_spinner=False)
def _search_fish_enriched(q: Optional[str], limit: int) -> pd.DataFrame:
    view = _pick_fish_view()
    cols = _fish_cols(view)
    where, params = [], {"lim": int(limit)}
    if q and q.strip():
        params["ql"] = f"%{q.strip()}%"
        hay_parts = ["coalesce(b.fish_code,'')"]
        for c in ("fish_name","fish_nickname","genetic_background","transgene_base_code","transgene_pretty_name","genotype_rollup"):
            if _has(c, cols):
                hay_parts.append(f"coalesce(b.{c},'')")
        hay = " || ' ' || ".join(hay_parts)
        where.append(f"({hay}) ilike :ql")
    where_sql = (" where " + " and ".join(where)) if where else ""
    sql = text(f"""
        select *
        from {view} b
        {where_sql}
        order by coalesce(b.created_at, now()) desc, b.fish_code
        limit :lim
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    if "fish_code" not in df.columns:
        df["fish_code"] = ""
    for c in df.select_dtypes(include=["object","string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

st.header("Step 1 — Select parents (unordered fish pair)")
with st.form("fish_filters"):
    c1, c2 = st.columns([3,1])
    with c1:
        q = st.text_input("Filter fish (code/name/nickname/genotype/background)", "")
    with c2:
        limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
    submitted = st.form_submit_button("Run")

if submitted:
    st.cache_data.clear()
    st.session_state.pop("_picker_sig", None)
    st.session_state.pop("_picker_src", None)

with _eng().begin() as cx:
    ver = pd.read_sql(text("select count(*)::int as n, coalesce(max(created_at)::text,'') as mx from public.fish"), cx).iloc[0]
version_token = f"{ver['n']}|{ver['mx']}"
sig_now = f"{q}|{limit}|{version_token}"

if submitted or st.session_state.get("_picker_sig") != sig_now or "_picker_src" not in st.session_state:
    src = _search_fish_enriched(q, limit)
    st.session_state["_picker_sig"] = sig_now
    st.session_state["_picker_src"] = src
else:
    src = st.session_state["_picker_src"]

sel_set: Set[str] = set(st.session_state.get("_picker_sel", []))

if src.empty:
    st.info("No fish match your filters.")
else:
    cols_all = list(src.columns)
    ordered = ["fish_code"] + [c for c in cols_all if c != "fish_code"] if "fish_code" in cols_all else cols_all[:]
    view_df = src[ordered].copy()
    view_df.insert(0, "✓ Select", view_df.get("fish_code", pd.Series("", index=view_df.index)).astype(str).isin(sel_set))

    cfg: dict[str, st.column_config.Column] = {
        "✓ Select": st.column_config.CheckboxColumn("✓", default=False)
    }
    for c in view_df.columns:
        lc = c.lower()
        if lc.endswith("_at") or lc.endswith("_time") or lc in {"created_at","updated_at"}:
            cfg[c] = st.column_config.DatetimeColumn(c, disabled=True, format="YYYY-MM-DD HH:mm:ss")
        elif lc.startswith("date_") or lc.endswith("_date"):
            cfg[c] = st.column_config.DateColumn(c, disabled=True, format="YYYY-MM-DD")
        elif c == "fish_code":
            cfg[c] = st.column_config.TextColumn("Fish code", disabled=True)

    edited = st.data_editor(
        view_df,
        width="stretch",
        hide_index=True,
        column_config=cfg,
        key="cross_picker_editor",
    )

    if not edited.empty and "✓ Select" in edited.columns and "Fish code" in edited.columns:
        sel_set = set(edited.loc[edited["✓ Select"], "Fish code"].astype(str).tolist())
    else:
        sel_set = set()
    st.session_state["_picker_sel"] = list(sel_set)

    selected_codes = sorted(list(sel_set))

    def _clear_parents():
        for k in ("parent_a_code","parent_b_code","mom_fish_code","dad_fish_code"):
            st.session_state.pop(k, None)

    def _assign_parents_unordered():
        if len(selected_codes) == 0:
            _clear_parents(); return
        st.session_state["parent_a_code"] = selected_codes[0]
        st.session_state["parent_b_code"] = selected_codes[1] if len(selected_codes) > 1 else None
        a = st.session_state["parent_a_code"]
        b = st.session_state.get("parent_b_code")
        if b:
            mom, dad = (a, b) if a <= b else (b, a)
            st.session_state["mom_fish_code"] = mom
            st.session_state["dad_fish_code"] = dad
        else:
            st.session_state["mom_fish_code"] = a
            st.session_state.pop("dad_fish_code", None)

    _assign_parents_unordered()

    pa = st.session_state.get("parent_a_code") or "—"
    pb = st.session_state.get("parent_b_code") or "—"
    st.write(f"**Parent A:** {pa}")
    st.write(f"**Parent B:** {pb}")
    st.caption("Parents are treated as an unordered pair here. Roles (mother/father) are applied when choosing tanks.")

# =============================================================================
# STEP 2 — GENOTYPE INHERITANCE (PICK ELEMENTS)
# =============================================================================
st.header("Step 2 — Genotype inheritance")

mom_code = st.session_state.get("mom_fish_code")
dad_code = st.session_state.get("dad_fish_code")

@st.cache_data(show_spinner=False)
def _fetch_parent_rows(codes: list[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=["fish_code","genotype","created_at","transgene_pretty_name"])
    view = _pick_fish_view()
    cols = _fish_cols(view)
    pick = "transgene_pretty_name" if _has("transgene_pretty_name", cols) else ("genotype_rollup" if _has("genotype_rollup", cols) else None)
    base_select = ["b.fish_code as fish_code"]
    if pick: base_select.append(f"b.{pick} as genotype")
    if _has("created_at", cols): base_select.append("b.created_at as created_at")
    sql = text(f"""
      select {", ".join(base_select)}
      from {view} b
      where b.fish_code = any(:codes)
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    if pick:
        pretty = df[["fish_code","genotype"]].rename(columns={"genotype":"transgene_pretty_name"})
        df = df.merge(pretty, on="fish_code", how="left")
    return df

if not (mom_code or dad_code):
    st.info("Pick two parents above to preview and select genotype elements.")
else:
    parents = _fetch_parent_rows([c for c in (mom_code, dad_code) if c])
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
            st.markdown(f"**{code}**")
            tpn = (row.get("transgene_pretty_name") or "").strip() if "transgene_pretty_name" in parents.columns else ""
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
                st.session_state[state_key] = base
                st.session_state[state_sig] = sig
            df_edit = st.session_state[state_key].copy()
            ca, cb = st.columns([1,1])
            with ca:
                if st.button(f"Select all ({label})", width="stretch"):
                    df_edit["inherit?"] = True
            with cb:
                if st.button(f"Clear all ({label})", width="stretch"):
                    df_edit["inherit?"] = False
            df_edit = st.data_editor(
                df_edit,
                width="stretch",
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
        mom_df = _parent_block("Parent A", mom_code, "mom")
    with c2:
        dad_df = _parent_block("Parent B", dad_code, "dad")

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
        st.dataframe(combined.reset_index(drop=True), width="stretch", hide_index=True)

# =============================================================================
# STEP 3 — ONE CLICK: SAVE FISH PAIR + LINK CONCEPTUAL CLUTCH
# =============================================================================
st.subheader("Save pair + clutch")

computed_geno = _default_expected_genotype(
    locals().get("combined", pd.DataFrame(columns=["element"])),
    mom_code, dad_code
)

combined = locals().get("combined", pd.DataFrame(columns=["element","source"]))
can_save_both = bool(mom_code) and bool(dad_code) and isinstance(combined, pd.DataFrame) and not combined.empty

if st.button("💾 Save fish pair + clutch", type="primary", width="stretch", disabled=not can_save_both):
    try:
        with _eng().begin() as cx:
            sql = text("""
              with canon as (
                select least(:mom_code, :dad_code) as a, greatest(:mom_code, :dad_code) as b
              ),
              ids as (
                select
                  (select id from public.fish where fish_code = (select a from canon) limit 1) as mom_id,
                  (select id from public.fish where fish_code = (select b from canon) limit 1) as dad_id
              ),
              existing as (
                select id, fish_pair_code
                from public.fish_pairs
                where mom_fish_id = (select mom_id from ids)
                  and dad_fish_id = (select dad_id from ids)
              ),
              up as (
                update public.fish_pairs
                   set genotype_elems = :elts,
                       created_by     = :by,
                       created_at     = now()
                 where id in (select id from existing)
                returning fish_pair_code
              ),
              ins as (
                insert into public.fish_pairs (mom_fish_id, dad_fish_id, genotype_elems, created_by)
                select (select mom_id from ids), (select dad_id from ids), :elts, :by
                where not exists (select 1 from existing)
                returning fish_pair_code
              )
              select coalesce((select fish_pair_code from up), (select fish_pair_code from ins)) as fish_pair_code
            """)
            got = cx.execute(sql, {
                "mom_code": mom_code,
                "dad_code": dad_code,
                "elts": combined["element"].astype(str).tolist(),
                "by":   (os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"),
            }).mappings().first()
            fish_pair_code = got["fish_pair_code"]
        st.success(f"Saved fish pair {fish_pair_code}.")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Save failed: {type(e).__name__}: {e}")

# =============================================================================
# RECENT FISH PAIRS
# =============================================================================
st.subheader("Recent fish pairs")

@st.cache_data(show_spinner=False)
def _recent_fish_pairs(limit: int = 20) -> pd.DataFrame:
    sql = text("""
      select
        fp.fish_pair_code,
        mom.fish_code as mom,
        dad.fish_code as dad,
        fp.genotype_elems,
        fp.created_at
      from public.fish_pairs fp
      left join public.fish mom on mom.id = fp.mom_fish_id
      left join public.fish dad on dad.id = fp.dad_fish_id
      order by fp.created_at desc nulls last
      limit :lim
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"lim": int(limit)})
    df = df.rename(columns={
        "fish_pair_code": "Fish pair",
        "mom": "Parent 1",
        "dad": "Parent 2",
        "created_at": "Created",
    })
    df["Clutch"] = ""
    df["Clutch genotype"] = df.get("genotype_elems").apply(
        lambda a: "; ".join(a) if isinstance(a, list) else ""
    )
    return df[["Fish pair", "Parent 1", "Parent 2", "Clutch", "Clutch genotype", "Created"]]

if st.button("↻ Refresh recent pairs", type="secondary", width="content"):
    st.cache_data.clear()

with _eng().begin() as cx:
    _cnt = pd.read_sql(text("select count(*)::int as n from public.fish_pairs"), cx)["n"][0]
st.caption(f"(fish_pairs rows in DB: {_cnt})")

fp = _recent_fish_pairs(20)

if fp.empty:
    st.info("No **fish pairs** saved yet. Use the checkboxes above and **Save fish pair + clutch**.")
else:
    st.dataframe(fp, width="stretch", hide_index=True)