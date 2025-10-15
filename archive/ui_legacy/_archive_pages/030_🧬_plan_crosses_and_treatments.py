from __future__ import annotations

import os, re
from typing import List, Dict, Any
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ---- page config FIRST ----
st.set_page_config(page_title="🧬 Define Cross — Fish, Genotype, Treatments", page_icon="🧬", layout="wide")

# ---- optional unlock ----
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

# ---- queries backend (multi-term + field filters) ----
import importlib
from carp_app.lib import queries as Q
importlib.reload(Q)

# ---- engine ----
_ENGINE = None
def _get_engine():
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    url = os.getenv("DB_URL")
    if not url:
        raise RuntimeError("DB_URL not set")
    _ENGINE = create_engine(url, future=True)
    return _ENGINE

# ---- helpers ----
def _stage_choices() -> List[str]:
    sql = """
      select distinct upper(stage) as s
      from public.vw_fish_standard
      where stage is not null and stage <> ''
      order by 1
    """
    with _get_engine().begin() as cx:
        df = pd.read_sql(text(sql), cx)
    return [s for s in df["s"].astype(str).tolist() if s]

def _load_standard_for_codes(codes: List[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame()
    sql = """
      select *
      from public.vw_fish_standard
      where fish_code = ANY(:codes)
    """
    with _get_engine().begin() as cx:
        df = pd.read_sql(text(sql), cx, params={"codes": codes})
    order = {c:i for i,c in enumerate(codes)}
    df["__ord"] = df["fish_code"].map(order).fillna(len(order)).astype(int)
    df = df.sort_values("__ord").drop(columns="__ord")
    return df

def _map_codes_to_ids(codes: List[str]) -> Dict[str, str]:
    if not codes:
        return {}
    with _get_engine().begin() as cx:
        ids = pd.read_sql(
            text("select id, fish_code from public.fish where fish_code = any(:codes)"),
            cx,
            params={"codes": codes},
        )
    return dict(zip(ids["fish_code"].astype(str), ids["id"].astype(str)))

def _build_picker_table(q: str, stages: List[str], limit: int) -> pd.DataFrame:
    rows = Q.load_fish_overview(_get_engine(), q=q, stages=stages, limit=limit)
    if not rows:
        return pd.DataFrame()
    match_df = pd.DataFrame(rows)
    codes = match_df["fish_code"].astype(str).tolist()

    std = _load_standard_for_codes(codes)
    id_map = _map_codes_to_ids(codes)
    std["id"] = std["fish_code"].map(id_map)
    std = std.dropna(subset=["id"]).copy()
    std["id"] = std["id"].astype(str)

    cols = [
        "id","fish_code","name","nickname","genotype","genetic_background","stage",
        "date_birth","age_days","created_at"
    ]
    for c in cols:
        if c not in std.columns:
            std[c] = None

    view = std[cols].copy()
    view.insert(0, "✓ Select", False)
    return view

# ---- state ----
st.title("🧬 Define Cross — Fish, Genotype, Treatments")

created_by_default = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
created_by = st.text_input("Created by", value=created_by_default)
cross_date = st.date_input("Cross date")

# --------------------------------
# Step 1 — Select parents (fish)
# --------------------------------
st.header("Step 1 — Select parents (fish)")
with st.form("fish_filters"):
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        q = st.text_input("Filter fish (code/name/nickname/genotype/background)", "")
    with c2:
        try:
            stage_vals = st.multiselect("Stage", _stage_choices(), default=[])
        except Exception:
            stage_vals = []
    with c3:
        limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
    submitted = st.form_submit_button("Apply")

# first load (or reload on Apply)
if submitted or "_picker_sig" not in st.session_state:
    table = _build_picker_table(q, stage_vals, limit)
    st.session_state["_picker_sig"] = f"{q}|{','.join(stage_vals)}|{limit}"
    st.session_state["_picker_df"] = table.copy()
else:
    table = st.session_state.get("_picker_df", pd.DataFrame())

if table.empty:
    st.info("No fish match your filters.")
else:
    csa, csb = st.columns([1,1])
    with csa:
        if st.button("Select all"):
            st.session_state["_picker_df"].loc[:, "✓ Select"] = True
    with csb:
        if st.button("Clear all"):
            st.session_state["_picker_df"].loc[:, "✓ Select"] = False

    # -- after rendering the table --
    picker_cols = [
        "✓ Select",
        "fish_code","name","nickname","genotype","genetic_background",
        "stage","date_birth","age_days","created_at",
    ]  # id intentionally omitted

    edited = st.data_editor(
        st.session_state["_picker_df"],
        use_container_width=True,
        hide_index=True,
        column_order=picker_cols,
        column_config={
            "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
            "fish_code": st.column_config.TextColumn("fish_code", disabled=True),
            "name": st.column_config.TextColumn("name", disabled=True),
            "nickname": st.column_config.TextColumn("nickname", disabled=True),
            "genotype": st.column_config.TextColumn("genotype", disabled=True),
            "genetic_background": st.column_config.TextColumn("genetic_background", disabled=True),
            "stage": st.column_config.TextColumn("stage", disabled=True),
            "date_birth": st.column_config.DateColumn("date_birth", disabled=True, format="YYYY-MM-DD"),
            "age_days": st.column_config.NumberColumn("age_days", disabled=True),
            "created_at": st.column_config.DatetimeColumn("created_at", disabled=True, format="YYYY-MM-DD HH:mm:ss"),
        },
        key="cross_picker_editor",
    )
    st.session_state["_picker_df"] = edited.copy()

    # --- Auto-assign parents based on the first two checked rows ---
    sel = edited[edited["✓ Select"]].copy().reset_index(drop=True)
    codes = sel["fish_code"].astype(str).tolist() if "fish_code" in sel.columns else []
    id_map = _map_codes_to_ids(codes)
    ids = [id_map.get(c) for c in codes]

    def _clear_parents():
        for k in ("mom_fish_code","mom_fish_id","dad_fish_code","dad_fish_id"):
            st.session_state.pop(k, None)

    def _assign_parents_from_selection():
        if len(codes) == 0:
            _clear_parents()
        elif len(codes) == 1:
            st.session_state["mom_fish_code"] = codes[0]
            st.session_state["mom_fish_id"]   = ids[0]
            st.session_state.pop("dad_fish_code", None)
            st.session_state.pop("dad_fish_id", None)
        else:
            st.session_state["mom_fish_code"] = codes[0]
            st.session_state["mom_fish_id"]   = ids[0]
            st.session_state["dad_fish_code"] = codes[1]
            st.session_state["dad_fish_id"]   = ids[1]

    _assign_parents_from_selection()

    c1, c2 = st.columns([1,1])
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

# --------------------------------
# Step 2 — Genotype inheritance
# --------------------------------
st.header("Step 2 — Genotype inheritance")

mom_code = st.session_state.get("mom_fish_code")
dad_code = st.session_state.get("dad_fish_code")

def _fetch_parent_rows(codes: list[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=["fish_code","name","nickname","genotype","genetic_background","stage","date_birth","created_at"])
    sql = text("""
      select fish_code, name, nickname, genotype, genetic_background, stage, date_birth, created_at
      from public.vw_fish_standard
      where fish_code = any(:codes)
    """)
    with _get_engine().begin() as cx:
        try:
            df = pd.read_sql(sql, cx, params={"codes": codes})
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
    return df

def _split_genotype(g: str) -> list[str]:
    if not g:
        return []
    parts = [p.strip() for p in re.split(r"[;,|]+", str(g)) if p and p.strip()]
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
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
                st.warning(f"{code}: not found in view")
                return pd.DataFrame(columns=["element","inherit?","source"])

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

            elems = _split_genotype((row.get("genotype") or "").strip())
            if not elems:
                st.info("No genotype text available for this fish.")
                return pd.DataFrame(columns=["element","inherit?","source"])

            # Build or refresh the editable table with persistence
            state_key = f"{key_prefix}_inherit_df"
            state_sig = f"{key_prefix}_sig"
            sig = "|".join(elems)

            # Initialize or refresh while preserving existing choices by 'element'
            if st.session_state.get(state_sig) != sig:
                base = pd.DataFrame({"element": elems})
                base["inherit?"] = True        # default selected
                base["source"] = label.split(" ")[0]  # "Mom" or "Dad"

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
                column_order=["inherit?","element","source"],  # checkbox first
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

    # Combined selection preview (unique elements, keep source tag from first occurrence)
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

# --------------------------------
# Step 3 — Optional treatments
# --------------------------------
st.header("Step 3 — Optional treatments")

# Build a unified catalog: plasmids (+ linked RNA if present)
with _get_engine().begin() as cx:
    dfp = pd.read_sql(text("""
        select
          p.id_uuid      as plasmid_id,
          p.code         as plasmid_code,
          coalesce(p.name,p.code) as plasmid_name,
          p.supports_invitro_rna
        from public.plasmids p
        order by p.code
    """), cx)
    dfr = pd.read_sql(text("""
        select
          r.id_uuid      as rna_id,
          r.code         as rna_code,
          coalesce(r.name,r.code) as rna_name,
          r.source_plasmid_id
        from public.rnas r
        order by r.code
    """), cx)

# join for convenience
dfr_map = dfr.set_index("source_plasmid_id") if not dfr.empty else pd.DataFrame()
dfp["rna_code"] = dfp["plasmid_id"].map(lambda pid: dfr_map.loc[pid, "rna_code"] if pid in dfr_map.index else None)
dfp["rna_name"] = dfp["plasmid_id"].map(lambda pid: dfr_map.loc[pid, "rna_name"] if pid in dfr_map.index else None)

# filter & choice controls
c1, c2 = st.columns([2, 3])
with c1:
    material_scope = st.radio(
        "Material scope",
        ["All", "Plasmids only", "RNAs only", "Supported only (auto RNA)"],
        horizontal=True,
    )
with c2:
    search_mat = st.text_input("Filter by code/name (materials list)", "")

# Build choices list according to scope
choices = []
if not dfp.empty:
    for _, row in dfp.iterrows():
        p_code = str(row["plasmid_code"])
        p_name = str(row["plasmid_name"])
        p_ok = True
        r_code = row.get("rna_code")
        r_name = row.get("rna_name")

        if material_scope in {"All", "Plasmids only", "Supported only (auto RNA)"}:
            if material_scope == "Supported only (auto RNA)" and not row.get("supports_invitro_rna", False):
                p_ok = False
            if p_ok:
                choices.append(("plasmid", p_code, p_name))

        if material_scope in {"All", "RNAs only"} and pd.notna(r_code):
            choices.append(("rna", str(r_code), str(r_name)))

# apply text filter
if search_mat.strip():
    ql = search_mat.strip().lower()
    choices = [c for c in choices if (ql in c[1].lower() or ql in (c[2] or "").lower())]

# Present multiselect of materials
pretty = [f"{kind.upper()}: {code} — {name}" for kind, code, name in choices]
sel = st.multiselect("Select materials for this clutch", pretty, default=[])

# Translate back to (kind, code, name)
selected_rows = []
lookup = dict(zip(pretty, choices))
for key in sel:
    selected_rows.append(lookup[key])

# Seed/edit a treatments table
if "_treatments_editor" not in st.session_state or st.session_state.get("_treatments_sig") != "|".join([f"{k}:{c}" for k,c,_ in selected_rows]):
    base = pd.DataFrame(
        [{"material_type": k, "material_code": c, "material_name": n, "dose": None, "units": "", "at_hpf": None, "notes": ""} for k,c,n in selected_rows]
    )
    st.session_state["_treatments_editor"] = base
    st.session_state["_treatments_sig"] = "|".join([f"{k}:{c}" for k,c,_ in selected_rows])

edit_df = st.session_state.get("_treatments_editor", pd.DataFrame()).copy()

# Show editor
edit_df = st.data_editor(
    edit_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "material_type": st.column_config.SelectboxColumn("material_type", options=["plasmid","rna"], disabled=True),
        "material_code": st.column_config.TextColumn("material_code", disabled=True),
        "material_name": st.column_config.TextColumn("material_name", disabled=True),
        "dose":         st.column_config.NumberColumn("dose"),
        "units":        st.column_config.TextColumn("units"),
        "at_hpf":       st.column_config.NumberColumn("at_hpf", help="Time to treat (hours post-fertilization)"),
        "notes":        st.column_config.TextColumn("notes"),
    },
    key="treatments_editor",
)

st.session_state["_treatments_editor"] = edit_df

# Persist plan to session (for Step 4 / save)
cA, cB = st.columns([1,1])
with cA:
    if st.button("Save treatment plan to session", use_container_width=True):
        # keep only rows with a material selected
        df_plan = edit_df.copy()
        st.session_state["clutch_treatments"] = df_plan.to_dict(orient="records")
        st.success(f"Saved {len(df_plan)} treatment row(s) for this clutch.")

with cB:
    if st.button("Clear treatment plan", use_container_width=True):
        st.session_state.pop("clutch_treatments", None)
        st.session_state.pop("_treatments_editor", None)
        st.session_state.pop("_treatments_sig", None)
        st.experimental_rerun()

# Preview saved plan
if st.session_state.get("clutch_treatments"):
    st.subheader("Selected elements for clutch — treatments")
    st.dataframe(pd.DataFrame(st.session_state["clutch_treatments"]), use_container_width=True, hide_index=True)