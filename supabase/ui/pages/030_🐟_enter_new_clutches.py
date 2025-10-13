from __future__ import annotations
from supabase.ui.auth_gate import require_auth
sb, session, user = require_auth()
from supabase.ui.email_otp_gate import require_email_otp
require_email_otp()

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os, re
from typing import List, Dict, Any
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ---- page config FIRST ----
st.set_page_config(page_title="🧬 Plan crosses and treatments", page_icon="🧬", layout="wide")

# ---- optional unlock ----
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

# ---- queries backend (multi-term + field filters) ----
import importlib
import supabase.queries as Q
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
# Step 3 — Optional treatments (Tabs: Plasmids / RNAs)
# --------------------------------
st.header("Step 3 — Optional treatments")

# --- helpers: tiny search builders (field filters + AND semantics)
def _plasmids_sql(q: str) -> tuple[str, Dict[str, Any]]:
    import shlex
    field_map = {
        "code": "v.code",
        "name": "v.name",
        "nickname": "v.nickname",
        "fluors": "v.fluors",
        "resistance": "v.resistance",
    }
    haystack = ("concat_ws(' ', coalesce(v.code,''),coalesce(v.name,''),coalesce(v.nickname,''),"
                "coalesce(v.fluors,''),coalesce(v.resistance,''),coalesce(v.notes,''))")
    where, params = [], {}
    toks = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]
    for i,t in enumerate(toks):
        neg = t.startswith("-"); core = t[1:] if neg else t
        if ":" in core:
            k,vv = core.split(":",1); k=k.strip().lower(); vv=vv.strip().strip('"')
            if k in field_map and vv:
                params[f"t{i}"]=f"%{vv}%"
                where.append(( "NOT " if neg else "" ) + f"({field_map[k]} ILIKE :t{i})")
                continue
        params[f"t{i}"]=f"%{core}%"
        where.append(( "NOT " if neg else "" ) + f"({haystack} ILIKE :t{i})")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
      select
        v.id_uuid,
        v.code,
        v.name,
        v.nickname,
        v.fluors,
        v.resistance,
        v.supports_invitro_rna,
        v.created_by,
        v.created_at
      from public.vw_plasmids_overview v
      {where_sql}
      order by v.code
      limit 1000
    """
    return sql, params

def _rnas_sql(q: str) -> tuple[str, Dict[str, Any]]:
    import shlex
    field_map = {
        "code": "r.code",
        "name": "r.name",
        "source": "p.code",
    }
    haystack = ("concat_ws(' ', coalesce(r.code,''),coalesce(r.name,''),coalesce(p.code,''),coalesce(p.name,''))")
    where, params = [], {}
    toks = [t for t in shlex.split(q or "") if t and t.upper() != "AND"]
    for i,t in enumerate(toks):
        neg = t.startswith("-"); core = t[1:] if neg else t
        if ":" in core:
            k,vv = core.split(":",1); k=k.strip().lower(); vv=vv.strip().strip('"')
            if k in field_map and vv:
                params[f"t{i}"]=f"%{vv}%"
                where.append(( "NOT " if neg else "" ) + f"({field_map[k]} ILIKE :t{i})")
                continue
        params[f"t{i}"]=f"%{core}%"
        where.append(( "NOT " if neg else "" ) + f"({haystack} ILIKE :t{i})")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
      select
        r.id_uuid,
        r.code,
        r.name,
        p.code   as source_plasmid_code,
        r.created_by,
        r.created_at
      from public.rnas r
      left join public.plasmids p on p.id_uuid = r.source_plasmid_id
      {where_sql}
      order by r.code
      limit 1000
    """
    return sql, params

# --- treatment row builder (common schema)
def _mk_treatment_rows(df: pd.DataFrame, kind: str, dose=None, units="", at_hpf=None, notes="") -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "material_type": kind,                         # 'plasmid' or 'rna'
            "material_code": r["code"],
            "material_name": r.get("name") or r["code"],
            "dose": dose, "units": units, "at_hpf": at_hpf, "notes": notes,
        })
    return rows

tab_p, tab_r = st.tabs(["🧪 Plasmids", "🧬 RNAs"])

# =========================
# Plasmids tab
# =========================
with tab_p:
    c1, c2 = st.columns([3,1])
    with c1:
        qp = st.text_input("Search plasmids (code:, name:, nickname:, fluors:, resistance:)", "")
    with c2:
        st.write("")  # spacing
        apply_p = st.button("Apply (plasmids)")

    # load plasmids
    sql_p, params_p = _plasmids_sql(qp)
    with _get_engine().begin() as cx:
        dfp = pd.read_sql(text(sql_p), cx, params=params_p)

    # render selectable table with treatment fields
    if dfp.empty:
        st.info("No plasmids match.")
    else:
        dfp_view = dfp.copy()
        dfp_view.insert(0, "✓ Select", False)
        # default editable treatment columns
        if "dose" not in dfp_view:   dfp_view["dose"] = None
        if "units" not in dfp_view:  dfp_view["units"] = ""
        if "at_hpf" not in dfp_view: dfp_view["at_hpf"] = None
        if "notes" not in dfp_view:  dfp_view["notes"] = ""
        order_p = ["✓ Select","code","name","nickname","fluors","resistance","supports_invitro_rna","dose","units","at_hpf","notes","created_by","created_at"]
        edited_p = st.data_editor(
            dfp_view,
            use_container_width=True, hide_index=True, column_order=order_p,
            column_config={
                "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
                "code":     st.column_config.TextColumn("code", disabled=True),
                "name":     st.column_config.TextColumn("name", disabled=True),
                "nickname": st.column_config.TextColumn("nickname", disabled=True),
                "fluors":   st.column_config.TextColumn("fluors", disabled=True),
                "resistance": st.column_config.TextColumn("resistance", disabled=True),
                "supports_invitro_rna": st.column_config.CheckboxColumn("supports_invitro_rna", disabled=True),
                "dose":     st.column_config.NumberColumn("dose"),
                "units":    st.column_config.TextColumn("units"),
                "at_hpf":   st.column_config.NumberColumn("at_hpf", help="Time (hours post-fertilization)"),
                "notes":    st.column_config.TextColumn("notes"),
                "created_by": st.column_config.TextColumn("created_by", disabled=True),
                "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
            },
            key="treat_plasmids_editor",
        )

        cA, cB = st.columns([1,1])
        with cA:
            add_p = st.button("Add selected plasmids to plan", use_container_width=True)
        with cB:
            clr_p = st.button("Clear plasmid selections", use_container_width=True)

        if add_p:
            picked = edited_p[edited_p["✓ Select"]].copy()
            if not picked.empty:
                rows = _mk_treatment_rows(
                    picked.rename(columns={"code":"code","name":"name"}),
                    kind="plasmid",
                )
                # carry edited dose/units/at_hpf/notes from table
                for i, (_, rr) in enumerate(picked.iterrows()):
                    rows[i]["dose"]  = rr.get("dose")
                    rows[i]["units"] = rr.get("units")
                    rows[i]["at_hpf"]= rr.get("at_hpf")
                    rows[i]["notes"] = rr.get("notes")
                plan = st.session_state.get("clutch_treatments", [])
                plan.extend(rows)
                st.session_state["clutch_treatments"] = plan
                st.success(f"Added {len(rows)} plasmid treatment(s) to plan.")
        if clr_p:
            st.session_state.pop("treat_plasmids_editor", None)
            st.experimental_rerun()

# =========================
# RNAs tab
# =========================
with tab_r:
    c1, c2 = st.columns([3,1])
    with c1:
        qr = st.text_input("Search RNAs (code:, name:, source:)", "")
    with c2:
        st.write("")
        apply_r = st.button("Apply (RNAs)")

    sql_r, params_r = _rnas_sql(qr)
    with _get_engine().begin() as cx:
        dfr = pd.read_sql(text(sql_r), cx, params=params_r)

    if dfr.empty:
        st.info("No RNAs match.")
    else:
        dfr_view = dfr.rename(columns={"source_plasmid_code":"source"}).copy()
        dfr_view.insert(0, "✓ Select", False)
        for col in ("dose","units","at_hpf","notes"):
            if col not in dfr_view: dfr_view[col] = None if col in ("dose","at_hpf") else ""
        order_r = ["✓ Select","code","name","source","dose","units","at_hpf","notes","created_by","created_at"]
        edited_r = st.data_editor(
            dfr_view,
            use_container_width=True, hide_index=True, column_order=order_r,
            column_config={
                "✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False),
                "code":     st.column_config.TextColumn("code", disabled=True),
                "name":     st.column_config.TextColumn("name", disabled=True),
                "source":   st.column_config.TextColumn("source", disabled=True),
                "dose":     st.column_config.NumberColumn("dose"),
                "units":    st.column_config.TextColumn("units"),
                "at_hpf":   st.column_config.NumberColumn("at_hpf", help="Time (hours post-fertilization)"),
                "notes":    st.column_config.TextColumn("notes"),
                "created_by": st.column_config.TextColumn("created_by", disabled=True),
                "created_at": st.column_config.DatetimeColumn("created_at", disabled=True),
            },
            key="treat_rnas_editor",
        )

        cA, cB = st.columns([1,1])
        with cA:
            add_r = st.button("Add selected RNAs to plan", use_container_width=True)
        with cB:
            clr_r = st.button("Clear RNA selections", use_container_width=True)

        if add_r:
            picked = edited_r[edited_r["✓ Select"]].copy()
            if not picked.empty:
                rows = _mk_treatment_rows(
                    picked.rename(columns={"code":"code","name":"name"}),
                    kind="rna",
                )
                for i, (_, rr) in enumerate(picked.iterrows()):
                    rows[i]["dose"]  = rr.get("dose")
                    rows[i]["units"] = rr.get("units")
                    rows[i]["at_hpf"]= rr.get("at_hpf")
                    rows[i]["notes"] = rr.get("notes")
                plan = st.session_state.get("clutch_treatments", [])
                plan.extend(rows)
                st.session_state["clutch_treatments"] = plan
                st.success(f"Added {len(rows)} RNA treatment(s) to plan.")
        if clr_r:
            st.session_state.pop("treat_rnas_editor", None)
            st.experimental_rerun()

# --- Preview the combined plan (from either tab)
plan = st.session_state.get("clutch_treatments", [])
st.subheader("Selected elements for clutch — treatments")
if plan:
    st.dataframe(pd.DataFrame(plan), use_container_width=True, hide_index=True)
else:
    st.info("No treatments selected yet.")

# --------------------------------
# Step 4 — Save clutch plan
# --------------------------------
st.header("Step 4 — Save clutch")

# parents + plan
mom_code = st.session_state.get("mom_fish_code")
dad_code = st.session_state.get("dad_fish_code")
plan = st.session_state.get("clutch_treatments", [])

def _selected_genotype_elements() -> list[str]:
    elems = []
    for key in ("mom_inherit_df", "dad_inherit_df"):
        df = st.session_state.get(key)
        if isinstance(df, pd.DataFrame) and {"inherit?","element"}.issubset(df.columns):
            elems.extend(df[df["inherit?"]]["element"].astype(str).tolist())
    # unique, preserve order
    seen, out = set(), []
    for e in elems:
        if e not in seen:
            seen.add(e); out.append(e)
    return out

def _format_genotype_elements(elems: list[str]) -> str:
    """
    Turn pDQM005-301 / pDQM005^301 → Tg(pDQM005)301
    Leave any non-matching element as-is.
    Join with '; '.
    """
    out = []
    for e in elems:
        e = (e or "").strip()
        m = re.match(r"^\s*([A-Za-z0-9\-]+)\s*(?:[\-\^])\s*(\d+)\s*$", e)
        if m:
            base, num = m.group(1), m.group(2)
            out.append(f"Tg({base}){num}")
        else:
            out.append(e)
    return "; ".join(out)

def _auto_clutch_name_from_state() -> str:
    # Left side: RNAs then plasmids (comma-separated)
    p = st.session_state.get("clutch_treatments", []) or []
    rnas     = [str(r["material_code"]) for r in p if r.get("material_type") == "rna" and r.get("material_code")]
    plasmids = [str(r["material_code"]) for r in p if r.get("material_type") == "plasmid" and r.get("material_code")]

    left_parts = []
    if rnas:     left_parts.append(", ".join(rnas))
    if plasmids: left_parts.append(", ".join(plasmids))
    left = ", ".join(left_parts)

    # Right side: formatted genotype elements
    right = _format_genotype_elements(_selected_genotype_elements())

    if left and right:
        return f"{left} > {right}"
    if right:
        return right
    if left:
        return left
    return "planned-clutch"

if not (mom_code and dad_code):
    st.info("Pick Mom and Dad in Step 1 to enable saving.")
elif not plan:
    st.info("Add at least one treatment in Step 3 to enable saving.")
else:
    # Auto-generated name (read-only) + editable nickname
    auto_name = _auto_clutch_name_from_state()
    colA, colB = st.columns(2)
    with colA:
        st.text_input("planned_clutch_name", value=auto_name, disabled=True)
    with colB:
        planned_clutch_nickname = st.text_input("planned_clutch_nickname (optional)", value=auto_name)

    save_note = st.text_input("Optional clutch note", "")
    save_btn = st.button("💾 Save clutch plan", type="primary", use_container_width=True)

    # treatments insert (shared)
    ins_t = text("""
      insert into public.clutch_plan_treatments
        (clutch_id, material_type, material_code, material_name, dose, units, at_hpf, notes)
      values
        (:cid, :typ, :code, :name, :dose, :units, :at_hpf, :notes)
    """)

    if save_btn:
        ins_hdr = text("""
          insert into public.clutch_plans
            (mom_code, dad_code, cross_date, note, created_by, planned_name, planned_nickname)
          values
            (:mom, :dad, :xdate, :note, :by, :pname, :pnick)
          returning id_uuid
        """)

        cid = None
        with _get_engine().begin() as cx:
            cid = cx.execute(ins_hdr, {
                "mom": mom_code,
                "dad": dad_code,
                "xdate": pd.to_datetime(cross_date).date(),   # use the picked cross_date
                "note": save_note,
                "by": (created_by or "").strip() or (os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"),
                "pname": auto_name,                                           # always generated
                "pnick": planned_clutch_nickname.strip() or auto_name,        # user-editable
            }).scalar()

            # treatments
            for row in plan:
                cx.execute(ins_t, {
                    "cid":   cid,
                    "typ":   row.get("material_type"),
                    "code":  row.get("material_code"),
                    "name":  row.get("material_name"),
                    "dose":  row.get("dose"),
                    "units": row.get("units"),
                    "at_hpf":row.get("at_hpf"),
                    "notes": row.get("notes"),
                })

        # Post-save banner + clear in-memory plan
        st.success(f"Saved clutch plan with {len(plan)} treatment(s).")
        st.session_state["last_clutch_plan_id"] = str(cid)
        with _get_engine().begin() as cx:
            row = cx.execute(
                text("select clutch_code, planned_name from public.clutch_plans where id_uuid = :cid"),
                {"cid": cid}
            ).mappings().first()
        if row:
            st.success(f"Clutch saved as **{row['clutch_code']}** — {row['planned_name']}")
        st.session_state.pop("clutch_treatments", None)

    # Recent planned clutches (overview-style)
    with _get_engine().begin() as cx:
        df_recent = pd.read_sql(text("""
          with tx_counts as (
            select clutch_id, count(*) as n_treatments
            from public.clutch_plan_treatments
            group by clutch_id
          )
          select
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
          order by p.created_at desc
          limit 100
        """), cx)

    st.subheader("Planned clutches (recent)")
    if df_recent.empty:
        st.info("No planned clutches yet.")
    else:
        cols = ["clutch_code","name","nickname","mom_code","dad_code","n_treatments","created_by","created_at"]
        st.dataframe(df_recent[cols], use_container_width=True, hide_index=True)
