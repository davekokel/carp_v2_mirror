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
from sqlalchemy import text as _sql
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
# HELPERS
# =============================================================================

def _colset(schema: str, rel: str) -> set[str]:
    with _eng().begin() as cx:
        rows = cx.execute(_sql("""
          select column_name
          from information_schema.columns
          where table_schema=:s and table_name=:r
        """), {"s": schema, "r": rel}).fetchall()
    return {r[0] for r in rows}

def _vf(cols: set[str], base: str) -> str:
    # prefer prefixed v_* columns if present, else plain
    return f"f.v_{base}" if f"v_{base}" in cols else f"f.{base}"

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
    try:
        with _eng().begin() as cx:
            df = pd.read_sql(text("""
              with src as (
                select fish_code, null::text as genotype, transgene_pretty_name
                from public.v_fish_overview_rich where fish_code = any(:codes)
              )
              select fish_code,
                     coalesce(genotype, transgene_pretty_name) as g
              from src
            """), cx, params={"codes": [c for c in [mom_code, dad_code] if c]})
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
    where = []
    params: Dict[str, Any] = {"lim": int(limit)}
    if q and q.strip():
        params["qq"] = f"%{q.strip()}%"
        hay = " || ' ' || ".join([
            "coalesce(b.fish_code,'')",
            "coalesce(b.fish_name,'')",
            "coalesce(b.fish_nickname,'')",
            "coalesce(b.genetic_background,'')",
            "coalesce(b.transgene_pretty_name,'')",
            "coalesce(b.genotype_rollup,'')",
        ])
        where.append(f"({hay}) ilike :qq")
    where_sql = (" where " + " and ".join(where)) if where else ""

    sql = text(f"""
      select
        b.fish_code                                  as fish_code,
        b.fish_name                                  as name,
        b.fish_nickname                              as nickname,
        b.genetic_background                         as genetic_background,
        b.transgene_pretty_name                      as genotype,
        b.line_building_stage                        as line_building_stage,
        b.date_birth                                  as birthday,
        b.created_at                                  as created_at,
        b.created_by                                  as created_by,
        b.transgene_base_code                        as transgene_base_code,
        ''                                            as allele_number,
        ''                                            as allele_name,
        ''                                            as allele_nickname,
        b.transgene_pretty_name                       as transgene_pretty_name,
        b.transgene_pretty_name                       as transgene_pretty_nickname,
        b.genotype_rollup                             as genotype_rollup_clean,
        b.n_living_tanks                              as n_living_tanks
      from public.v_fish_overview_rich b
      {where_sql}
      order by b.created_at desc nulls last, b.fish_code
      limit :lim
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    for c in [
        "fish_code","name","nickname","genetic_background","genotype",
        "line_building_stage","created_by","transgene_base_code","allele_name",
        "allele_nickname","transgene_pretty_nickname","transgene_pretty_name",
        "genotype_rollup_clean"
    ]:
        if c in df.columns:
            df[c] = df[c].astype("string").fillna("")
    df["n_living_tanks"] = pd.to_numeric(df.get("n_living_tanks", 0), errors="coerce").fillna(0).astype(int)
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
    # ── REPLACE everything from your current `cols = [` down through the `st.data_editor(...)` call with this block ──
    cols = [
        "fish_code","name","nickname","genetic_background",
        "transgene_base_code","allele_number","allele_name","allele_nickname",
        "transgene_pretty_nickname","transgene_pretty_name",
        "genotype","genotype_rollup_clean",
        "n_living_tanks","birthday","line_building_stage","created_at","created_by",
    ]
    for c in cols:
        if c not in src.columns:
            src[c] = "" if c != "n_living_tanks" else 0

    nonempty_cols = []
    for c in cols:
        s = src[c]
        if c == "n_living_tanks":
            if pd.to_numeric(s, errors="coerce").fillna(0).astype(int).sum() != 0 or s.notna().any():
                nonempty_cols.append(c)
        else:
            if s.astype(str).replace({"": None, "nan": None}).notna().any():
                nonempty_cols.append(c)

    ordered = ["fish_code"] + [c for c in nonempty_cols if c != "fish_code"]
    view = src[ordered].copy()
    view.insert(0, "✓ Select", view["fish_code"].astype(str).isin(sel_set))

    name_map = {
        "fish_code":"Fish code",
        "name":"Fish name",
        "nickname":"Fish nickname",
        "genetic_background":"Genetic background",
        "transgene_base_code":"Transgene base code",
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
    }
    view = view.rename(columns={k: v for k, v in name_map.items() if k in view.columns})

    cfg = {
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
    }
    cfg = {k: v for k, v in cfg.items() if k in view.columns}

    edited = st.data_editor(
        view,
        width="stretch",
        hide_index=True,
        column_config=cfg,
        key="cross_picker_editor",
    )

    if not edited.empty and "✓ Select" in edited.columns and "Fish code" in edited.columns:
        sel_set = set(edited.loc[edited["✓ Select"], "Fish code"].astype(str).tolist())
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
        return pd.DataFrame(columns=[
            "fish_code","name","nickname","genotype","genetic_background","stage","date_birth","created_at",
            "transgene_pretty_name"
        ])
    sql = text("""
      select
        b.fish_code                         as fish_code,
        b.fish_name                         as name,
        b.fish_nickname                     as nickname,
        b.transgene_pretty_name             as genotype,
        b.genetic_background                as genetic_background,
        b.line_building_stage               as stage,
        b.date_birth                         as date_birth,
        b.created_at                         as created_at
      from public.v_fish_overview_rich b
      where b.fish_code = any(:codes)
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    pretty = df[["fish_code","genotype"]].rename(columns={"genotype":"transgene_pretty_name"})
    return df.merge(pretty, on="fish_code", how="left")

if not (mom_code or dad_code):
    st.info("Pick two parents above to preview and select genotype elements.")
else:
    parents = _fetch_parent_rows([c for c in [mom_code, dad_code] if c])
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

# Compute expected genotype silently (not shown as a field)
computed_geno = _default_expected_genotype(
    locals().get("combined", pd.DataFrame(columns=["element"])),
    mom_code, dad_code
)

# Guard: need both parents and at least one selected element
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
    # Pretty column names expected by your renderer
    df = df.rename(columns={
        "fish_pair_code": "Fish pair",
        "mom": "Parent 1",
        "dad": "Parent 2",
        "created_at": "Created",
    })
    # Derive display clutch column (none yet)
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