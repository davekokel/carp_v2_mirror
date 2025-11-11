# carp_app/ui/pages/100_🐟_overview_plasmids.py
from __future__ import annotations
import os, pathlib, sys
from typing import List, Dict, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# repo root on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.app_ctx import get_engine as _create_engine
from carp_app.lib.time import utc_now

# ───────────── auth & page ─────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Plasmids Overview", page_icon="🧪", layout="wide")
st.title("🧪 Plasmids Overview")

# ───────────── engine cache ────────────
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _get_engine() -> Engine:
    return _cached_engine()

# ───────────── data loaders ────────────
def _coerce_strings(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _load_plasmids_overview(q: Optional[str], limit: int) -> pd.DataFrame:
    sql = text("""
      select
        code, name, nickname, resistance,
        fluors, tag_codes, fusions, n_fusions, created_at
      from public.v_plasmids_overview v
      where (:q is null)
         or (
              v.code        ilike :q
           or v.name        ilike :q
           or v.nickname    ilike :q
           or v.resistance  ilike :q
           or v.fluors      ilike :q
           or v.tag_codes   ilike :q
           or v.fusions     ilike :q
         )
      order by v.created_at desc nulls last, v.code
      limit :lim
    """)
    params = {"q": (f"%{q.strip()}%" if q and q.strip() else None), "lim": int(limit)}
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)
    return _coerce_strings(df)

# ───────── reference & insert/link helpers for payload ─────────
def _load_refdata():
    with _get_engine().begin() as cx:
        fluors = [r["fluor_code"] for r in cx.execute(
            text("select fluor_code from public.fluors order by 1")
        ).mappings().all()]
        tags = [r["tag_code"] for r in cx.execute(
            text("select tag_code from public.tags order by 1")
        ).mappings().all()]
    tag_positions = ["", "N", "C", "N-term", "C-term", "internal"]
    return fluors, tags, tag_positions

def _ensure_fusion_and_link(cx, plasmid_id: str, fluor_code: str | None,
                            tag_code: str | None, tag_pos: str | None,
                            fusion_name: str | None):
    if not fluor_code and not tag_code:
        return None
    fid = cx.execute(text("select id from public.fluors where fluor_code=:c limit 1"),
                     {"c": (fluor_code or None)}).scalar() if fluor_code else None
    tid = cx.execute(text("select id from public.tags where tag_code=:c limit 1"),
                     {"c": (tag_code or None)}).scalar() if tag_code else None
    if fluor_code and not fid:
        raise ValueError(f"Unknown fluor_code '{fluor_code}'")
    if tag_code and not tid:
        raise ValueError(f"Unknown tag_code '{tag_code}'")
    fusion_id = cx.execute(text("""
        with ins as (
          insert into public.fusions (fluor_id, tag_id, tag_pos, name)
          values (:fid, :tid, nullif(:pos,''), nullif(:fname,''))
          on conflict do nothing
          returning id
        )
        select id from ins
        union all
        select id from public.fusions
         where (fluor_id is not distinct from :fid)
           and (tag_id  is not distinct from :tid)
           and coalesce(tag_pos,'') = coalesce(:pos,'')
        limit 1
    """), {"fid": fid, "tid": tid, "pos": (tag_pos or ""), "fname": (fusion_name or None)}).scalar()
    if not fusion_id:
        raise RuntimeError("Could not create or find fusion")
    cx.execute(text("""
        insert into public.join_plasmid_fusions (plasmid_id, fusion_id)
        values (:pid, :fid)
        on conflict do nothing
    """), {"pid": plasmid_id, "fid": fusion_id})
    return fusion_id

def _insert_plasmid_with_fusions(code: str, nickname: str,
                                 resistance: str | None,
                                 notes: str | None,
                                 fusion_rows: list[dict]):
    if not code or not nickname:
        raise ValueError("code and nickname are required")
    with _get_engine().begin() as cx:
        row = cx.execute(text("""
          insert into public.plasmids (code, name, nickname, resistance, created_at)
          values (:code, :name, :nick, nullif(:res,''), now())
          on conflict (code) do update
            set name=excluded.name,
                nickname=excluded.nickname,
                resistance=excluded.resistance
          returning id, code
        """), {"code": code.strip(),
               "name": nickname.strip(),
               "nick": nickname.strip(),
               "res": (resistance or "").strip()}).mappings().first()
        pid = row["id"]
        created = 0
        for fr in fusion_rows:
            fcode = (fr.get("fluor_code") or "").strip() or None
            tcode = (fr.get("tag_code") or "").strip() or None
            tpos  = (fr.get("tag_pos") or "").strip()
            fname = (fr.get("fusion_name") or "").strip() or None
            if not fcode and not tcode:
                continue
            _ensure_fusion_and_link(cx, pid, fcode, tcode, tpos, fname)
            created += 1
    return {"plasmid_code": code, "linked_fusions": created}

# ─────────────────────────── page ───────────────────────────
def main():
    st.caption(f"DB_URL = {os.getenv('DB_URL','')}")

    with st.form("plasmid_filters", clear_on_submit=False):
        c1, c2 = st.columns([3,1])
        with c1:
            q = st.text_input("Search (code/nickname/name/fluors/tags/fusions)", "")
        with c2:
            limit = int(st.number_input("Limit", min_value=10, max_value=2000, value=500, step=50))
        _ = st.form_submit_button("Search")

    df = _load_plasmids_overview(q, limit)
    if df.empty:
        st.info("No plasmids match your filters.")
    else:
        st.subheader(f"Plasmids ({len(df)} rows)")
        table_cols = ["code","name","nickname","resistance","fluors","tag_codes","fusions","n_fusions","created_at"]
        table = df[table_cols]
        table_view = st.dataframe(table, width="stretch", hide_index=True)

        st.divider()
        st.subheader("Edit selection")
        editable_map = {
            "name": "Name",
            "nickname": "Nickname",
            "resistance": "Resistance",
        }
        edit_choice = st.multiselect("Choose which columns are editable", list(editable_map.keys()), [])
        selected = st.data_editor(
            table.assign(**{k: table[k] for k in table.columns}),
            width="stretch",
            hide_index=True,
            column_config=None,
            disabled=[c for c in table.columns if c not in edit_choice],
            key="plasmids_editor_v1",
        )
        if st.button("Save edits", type="primary"):
            changed = selected[[c for c in edit_choice] + ["code"]]
            changed = changed[changed["code"].notna()]
            if not changed.empty and edit_choice:
                with _get_engine().begin() as cx:
                    for _, row in changed.drop_duplicates(subset=["code"])[["code"] + list(edit_choice)].iterrows():
                        cx.execute(text(f"""
                          update public.plasmids
                          set {", ".join([f"{c} = :{c}" for c in edit_choice])}
                          where code = :code
                        """), {**{c: (row[c] if pd.notna(row[c]) else None) for c in edit_choice},
                               "code": row["code"]})
                st.success("Edits saved.")

    st.divider()
    st.subheader("Add new plasmid")

    fluors, tags, tag_positions = _load_refdata()
    c1, c2 = st.columns([2, 2])
    with c1:
        new_code = st.text_input("code (required)")
        new_nick = st.text_input("nickname (required)")
    with c2:
        new_res  = st.text_input("resistance")
        new_note = st.text_area("notes", height=80)

    st.markdown("**Fusions (add as many as you need)**")
    if "plasmid_fusion_rows" not in st.session_state:
        st.session_state.plasmid_fusion_rows = pd.DataFrame(
            [{"fluor_code": "", "tag_code": "", "tag_pos": "", "fusion_name": ""}]
        )

    fusion_df = st.data_editor(
        st.session_state.plasmid_fusion_rows,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "fluor_code": st.column_config.SelectboxColumn("Fluor", options=fluors, required=False),
            "tag_code":   st.column_config.SelectboxColumn("Tag",   options=tags,   required=False),
            "tag_pos":    st.column_config.SelectboxColumn("Tag position", options=tag_positions, required=False),
            "fusion_name": st.column_config.TextColumn("Fusion name (optional)", width="medium"),
        },
        key="plasmid_fusion_editor",
    )

    if st.button("Insert", type="primary"):
        rows = []
        for _, r in fusion_df.fillna("").iterrows():
            rows.append({
                "fluor_code": (r.get("fluor_code") or "").strip(),
                "tag_code":   (r.get("tag_code") or "").strip(),
                "tag_pos":    (r.get("tag_pos") or "").strip(),
                "fusion_name": (r.get("fusion_name") or "").strip(),
            })
        try:
            res = _insert_plasmid_with_fusions(new_code.strip(), new_nick.strip(), new_res, new_note, rows)
            st.success(f"Inserted/updated {res['plasmid_code']} • linked {res['linked_fusions']} fusion(s).")
            st.session_state.plasmid_fusion_rows = pd.DataFrame(
                [{"fluor_code": "", "tag_code": "", "tag_pos": "", "fusion_name": ""}]
            )
        except Exception as e:
            st.error(f"Insert failed: {e}")

    with st.expander("Reference: available fluors & tags", expanded=False):
        colA, colB = st.columns(2)
        with colA:
            st.caption("Fluors")
            st.dataframe(pd.DataFrame({"fluor_code": fluors}), width="stretch", hide_index=True)
        with colB:
            st.caption("Tags")
            st.dataframe(pd.DataFrame({"tag_code": tags}), width="stretch", hide_index=True)

if __name__ == "__main__":
    main()