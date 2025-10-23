# =============================================================================
# 🐟 Select fish pairs — conceptual (no tank_pairs or runs on this page)
#      Links conceptual fish pairs → conceptual clutches explicitly
# =============================================================================
from __future__ import annotations
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

# ── Auth gates ────────────────────────────────────────────────────────────────
from carp_app.ui.auth_gate import require_auth
sb, session, user = require_auth()

from carp_app.ui.email_otp_gate import require_email_otp
require_email_otp()

try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

# ── Std/3p imports ───────────────────────────────────────────────────────────
import os, re, hashlib, pathlib as _pl
from typing import List, Dict, Any, Set, Optional
import pandas as pd
import streamlit as st
from sqlalchemy import text
from carp_app.ui.lib.app_ctx import get_engine

# ── Page config / header ─────────────────────────────────────────────────────
st.set_page_config(page_title="🐟 Select fish pairs", page_icon="🐟", layout="wide")
st.title("🐟 Select fish pairs")

_srcp = _pl.Path(__file__).resolve()
st.caption("SRC=" + str(_srcp.name) + " • SHA256=" + hashlib.sha256(_srcp.read_bytes()).hexdigest()[:12])

# ── Engine factory (no URL key in cache; DB_URL guard) ───────────────────────
@st.cache_resource(show_spinner=False)
def _cached_engine():
    return get_engine()

def _eng():
    if not os.getenv("DB_URL"):
        st.error("DB_URL not set"); st.stop()
    return _cached_engine()

# Db fingerprint for sanity
with _eng().begin() as cx:
    dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

# =============================================================================
# HELPERS
# =============================================================================
def _default_expected_genotype(combined_df: pd.DataFrame, mom_code: str, dad_code: str) -> str:
    # 1) current selection from the grid (most immediate)
    if isinstance(combined_df, pd.DataFrame) and not combined_df.empty and "element" in combined_df.columns:
        return "; ".join(combined_df["element"].astype(str).tolist())

    # 2) anything previously saved to session?
    saved = st.session_state.get("planned_genotype_elements") or []
    if saved:
        return "; ".join([str(x) for x in saved])

    # 3) fallback: union tokens from parents' v_fish.genotype
    try:
        with _eng().begin() as cx:
            gf = pd.read_sql(
                text("select fish_code, genotype from public.v_fish where fish_code = any(:codes)"),
                cx, params={"codes": [c for c in [mom_code, dad_code] if c]}
            )
        toks = set()
        for g in gf["genotype"].dropna():
            for t in re.split(r"[;,|]+", str(g)):
                t = t.strip()
                if t:
                    toks.add(t)
        return "; ".join(sorted(toks))
    except Exception:
        return ""

def _split_genotype(g: str) -> list[str]:
    if not g:
        return []
    parts = [p.strip() for p in re.split(r"[;,|]+", str(g)) if p and p.strip()]
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p); out.append(p)
    return out

# =============================================================================
# STEP 1 — FISH SEARCH + ROW CHECKBOX SELECTION (MOM / DAD)
# =============================================================================
created_by_default = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
created_by = st.text_input("Created by", value=created_by_default)

@st.cache_data(show_spinner=False)
def _search_fish_enriched(q: Optional[str], limit: int) -> pd.DataFrame:
    where = []
    params: Dict[str, Any] = {"lim": int(limit)}
    if q and q.strip():
        params["qq"] = f"%{q.strip()}%"
        where.append("""
          (f.fish_code ilike :qq
           or f.name ilike :qq
           or f.nickname ilike :qq
           or f.genetic_background ilike :qq
           or f.transgene_base_code ilike :qq
           or f.allele_code ilike :qq
           or f.genotype ilike :qq)
        """)
    where_sql = (" where " + " and ".join(where)) if where else ""

    sql = text(f"""
      select
        f.fish_code,
        f.name,
        f.nickname,
        f.genetic_background,
        f.genotype,
        f.stage as line_building_stage,
        f.date_birth as birthday,
        f.created_at,
        f.created_by,
        f.transgene_base_code,
        f.allele_code as allele_number,
        f.allele_code as allele_name,
        f.allele_code as allele_nickname,
        f.genotype as transgene_pretty_name,
        f.genotype as transgene_pretty_nickname,
        f.genotype as genotype_rollup_clean,
        coalesce(f.n_living_tanks,0)::int as n_living_tanks
      from public.v_fish f
      {where_sql}
      order by f.created_at desc nulls last, f.fish_code
      limit :lim
    """)
    with _eng().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    # Hygiene
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

# ── Search form ──────────────────────────────────────────────────────────────
st.header("Step 1 — Select parents (fish)")
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

# Version token to invalidate cache when fish table changes
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

# ── Data grid with a “✓ Select” checkbox column ─────────────────────────────
sel_set: Set[str] = set(st.session_state.get("_picker_sel", []))

if src.empty:
    st.info("No fish match your filters.")
else:
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

    view = src[cols].copy()
    view.insert(0, "✓ Select", view["fish_code"].astype(str).isin(sel_set))

    view = view.rename(columns={
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
    })

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

    # Decide mom/dad from selection (first = mom; second = dad)
    def _clear_parents():
        for k in ("mom_fish_code","dad_fish_code"):
            st.session_state.pop(k, None)

    def _assign_parents_from_selection():
        if len(selected_codes) == 0:
            _clear_parents()
        elif len(selected_codes) == 1:
            st.session_state["mom_fish_code"] = selected_codes[0]
            st.session_state.pop("dad_fish_code", None)
        else:
            st.session_state["mom_fish_code"] = selected_codes[0]
            st.session_state["dad_fish_code"] = selected_codes[1]

    _assign_parents_from_selection()

    # Small parent helpers
    c1, c2 = st.columns(2)
    with c1:
        swap_disabled = not (st.session_state.get("mom_fish_code") and st.session_state.get("dad_fish_code"))
        if st.button("Swap Mom/Dad", use_container_width=True, disabled=swap_disabled):
            st.session_state["mom_fish_code"], st.session_state["dad_fish_code"] = (
                st.session_state.get("dad_fish_code"),
                st.session_state.get("mom_fish_code"),
            )
    with c2:
        if st.button("Clear Mom/Dad", use_container_width=True):
            _clear_parents()

    st.write(f"**Mom (A):** {st.session_state.get('mom_fish_code','—')}")
    st.write(f"**Dad (B):** {st.session_state.get('dad_fish_code','—')}")

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
    with _eng().begin() as cx:
        df = pd.read_sql(text("""
            select
              fish_code, name, nickname, genotype, genetic_background,
              stage, date_birth, created_at
            from public.v_fish
            where fish_code = any(:codes)
        """), cx, params={"codes": codes})
    pretty = df[["fish_code","genotype"]].rename(columns={"genotype":"transgene_pretty_name"})
    return df.merge(pretty, on="fish_code", how="left")

if not (mom_code or dad_code):
    st.info("Pick parent fish above to preview and select genotype elements.")
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

# =============================================================================
# STEP 3 — ONE CLICK: SAVE FISH PAIR + LINK CONCEPTUAL CLUTCH
# =============================================================================
st.subheader("Save pair + clutch")

# Keep the default suggested clutch fields near the button
def _suggest_next_clutch_code() -> str:
    with _eng().begin() as cx:
        n = pd.read_sql(text("""
          select coalesce(max((regexp_match(coalesce(clutch_code,''),
                 '^CL-\\d{2}(\\d{3})$'))[1]::int),0) + 1 as k
          from public.clutches
          where clutch_code like 'CL-'||to_char(extract(year from now())::int % 100,'FM00')||'%'
        """), cx)["k"].iloc[0]
    yy = f"{(pd.Timestamp.utcnow().year) % 100:02d}"
    return f"CL-{yy}{int(n):03d}"

default_clutch_code  = _suggest_next_clutch_code()
# ⭐ Use the live selection first, then session, then parents' genotypes
default_expected_geno = _default_expected_genotype(
    locals().get("combined", pd.DataFrame(columns=["element"])),
    mom_code, dad_code
)

c1, c2 = st.columns([2,3])
with c1:
    clutch_code = st.text_input("Clutch code (CL-YYNNN)", value=default_clutch_code, key="concept_clutch_code")

with c2:
    # Dynamically recompute the genotype string each rerun, and override the widget state
    prefill_geno = _default_expected_genotype(
        locals().get("combined", pd.DataFrame(columns=["element"])),
        mom_code, dad_code
    )

    # Force a reset if parents or selection changed
    sig = f"{mom_code}|{dad_code}|{prefill_geno}"
    if st.session_state.get("_last_geno_sig") != sig:
        st.session_state["_last_geno_sig"] = sig
        st.session_state["concept_clutch_geno"] = prefill_geno

    clutch_expected_input = st.text_input(
        "Clutch genotype (conceptual)",
        key="concept_clutch_geno",
        placeholder="e.g., Tg(pDQMM005); gu1"
    )

# Guard: need both parents and at least one element (your rule today)
combined = locals().get("combined", pd.DataFrame(columns=["element","source"]))
can_save_both = (
    bool(mom_code) and bool(dad_code) and
    isinstance(combined, pd.DataFrame) and not combined.empty and
    bool(clutch_code.strip())
)

if st.button("💾 Save fish pair + clutch", type="primary", use_container_width=True, disabled=not can_save_both):
    try:
        with _eng().begin() as cx:
            # 1) Upsert fish pair with FP-YYNNNN
            cx.execute(text("""
              with next_fp as (
                select
                  'FP-'||to_char(extract(year from now())::int % 100,'FM00')||
                  lpad((
                    select coalesce(max((regexp_match(coalesce(fish_pair_code,''),
                         '^FP-\\d{2}(\\d{4})$'))[1]::int),0) + 1
                    from public.fish_pairs
                    where fish_pair_code like 'FP-'||to_char(extract(year from now())::int % 100,'FM00')||'%'
                  )::text, 4, '0') as fp_code
              )
              insert into public.fish_pairs
                (fish_pair_code, mom_fish_code, dad_fish_code, genotype_elems, created_by)
              values
                ((select fp_code from next_fp), :mom, :dad, :elts, :by)
              on conflict (mom_fish_code, dad_fish_code) do update
                set genotype_elems = excluded.genotype_elems,
                    created_by     = excluded.created_by,
                    created_at     = now()
            """), {
                "mom": mom_code,
                "dad": dad_code,
                "elts": combined["element"].astype(str).tolist(),
                "by":   (os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"),
            })

            fp_row = pd.read_sql(
                text("""select fish_pair_id, fish_pair_code
                          from public.fish_pairs
                         where mom_fish_code=:mom and dad_fish_code=:dad
                         order by created_at desc limit 1"""),
                cx, params={"mom": mom_code, "dad": dad_code}
            )
            fish_pair_id   = str(fp_row["fish_pair_id"].iloc[0])
            fish_pair_code = fp_row["fish_pair_code"].iloc[0]

            # ⭐ Final genotype: prefer user input; if blank, fallback
            final_geno = (clutch_expected_input or "").strip()
            if not final_geno:
                final_geno = _default_expected_genotype(combined, mom_code, dad_code)

            # 2) Upsert conceptual clutch linked to fish pair (no cross_id needed)
            cx.execute(text("""
              insert into public.clutches
                (id, clutch_code, expected_genotype, fish_pair_id, fish_pair_code, created_by, created_at)
              values
                (gen_random_uuid(), :cc, :geno, :fpid, :fpcode, :by, now())
              on conflict (clutch_code) do update
                set expected_genotype = excluded.expected_genotype,
                    fish_pair_id      = coalesce(public.clutches.fish_pair_id, excluded.fish_pair_id),
                    fish_pair_code    = coalesce(public.clutches.fish_pair_code, excluded.fish_pair_code)
            """), {
                "cc": clutch_code.strip(),
                "geno": final_geno,   # <-- never empty now
                "fpid": fish_pair_id,
                "fpcode": fish_pair_code,
                "by":   (os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"),
            })

        st.success(f"Saved fish pair {fish_pair_code} and linked clutch {clutch_code}.")
        st.cache_data.clear()  # ensure the recent table refreshes
    except Exception as e:
        st.error(f"Save failed: {type(e).__name__}: {e}")

# =============================================================================
# RECENT FISH PAIRS (fish_pair_code + conceptual clutch_code + clutch_genotype)
#   - conceptual clutch via fish_pair_id/code (no tank_pairs required)
#   - clutch genotype falls back to fish_pairs.genotype_elems if empty
# =============================================================================
st.subheader("Recent fish pairs")

@st.cache_data(show_spinner=False)
def _recent_fish_pairs(limit: int = 20) -> pd.DataFrame:
    sql = text("""
      with pairs as (
        select fish_pair_id, fish_pair_code, mom_fish_code as mom, dad_fish_code as dad,
               genotype_elems, created_at
        from public.fish_pairs
      ),
      clutch_latest as (
        select distinct on (coalesce(c.fish_pair_id::text, c.fish_pair_code))
               coalesce(c.fish_pair_id::text, c.fish_pair_code) as key,
               c.clutch_code,
               coalesce(c.expected_genotype,'') as clutch_genotype,
               c.created_at as clutch_created_at
        from public.clutches c
        order by coalesce(c.fish_pair_id::text, c.fish_pair_code), c.created_at desc nulls last
      )
      select
        p.fish_pair_code,
        p.mom,
        p.dad,
        cl.clutch_code,
        -- fallback: if clutch.expected_genotype is empty, show elements from fish_pairs
        case
          when coalesce(cl.clutch_genotype,'') <> '' then cl.clutch_genotype
          when p.genotype_elems is not null         then array_to_string(p.genotype_elems, '; ')
          else '' 
        end as clutch_genotype,
        p.created_at
      from pairs p
      left join clutch_latest cl
        on cl.key = p.fish_pair_id::text or cl.key = p.fish_pair_code
      order by p.created_at desc nulls last
      limit :lim
    """)
    with _eng().begin() as cx:
        return pd.read_sql(sql, cx, params={"lim": int(limit)})

# Optional: manual refresh clears cache
if st.button("↻ Refresh recent pairs", type="secondary", use_container_width=False):
    st.cache_data.clear()

# Quick diagnostic (handy while iterating)
with _eng().begin() as cx:
    _cnt = pd.read_sql(text("select count(*)::int as n from public.fish_pairs"), cx)["n"][0]
st.caption(f"(fish_pairs rows in DB: {_cnt})")

fp = _recent_fish_pairs(20)

if fp.empty:
    st.info("No **fish pairs** saved yet. Use the checkboxes above and **Save fish pair + clutch**.")
else:
    show = fp.rename(columns={
        "fish_pair_code": "Fish pair",
        "mom":"Mom", "dad":"Dad",
        "clutch_code":"Clutch",
        "clutch_genotype":"Clutch genotype",
        "created_at":"Created"
    })
    st.dataframe(
        show[["Fish pair","Mom","Dad","Clutch","Clutch genotype","Created"]],
        use_container_width=True, hide_index=True
    )