# carp_app/ui/pages/300_➕️_add_plasmid.py
from __future__ import annotations
import os, pathlib, sys
from typing import List, Dict

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

# ───────────── auth & page ─────────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="CARP — Add plasmid", page_icon="🧪", layout="wide")
st.title("Add new plasmid")

# ───────────── engine cache ────────────
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _get_engine() -> Engine:
    return _cached_engine()

# ───────────── helpers ────────────
def _coerce_strings(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _load_fluors() -> pd.DataFrame:
    sql = text("SELECT fluor_code FROM public.fluors ORDER BY fluor_code")
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx)
    df = _coerce_strings(df)
    if "✓" not in df.columns:
        df.insert(0, "✓", False)
    return df[["✓", "fluor_code"]]

def _load_tags() -> pd.DataFrame:
    sql = text("SELECT tag_code FROM public.tags ORDER BY tag_code")
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx)
    df = _coerce_strings(df)
    if "✓" not in df.columns:
        df.insert(0, "✓", False)
    return df[["✓", "tag_code"]]

def _load_tag_positions() -> pd.DataFrame:
    rows = [
        {"✓": False, "tag_pos": ""},
        {"✓": False, "tag_pos": "N-term"},
        {"✓": False, "tag_pos": "C-term"},
        {"✓": False, "tag_pos": "internal"},
    ]
    return pd.DataFrame(rows)

def _ensure_fusion_and_link(cx, plasmid_id: str, fluor_code: str | None,
                            tag_code: str | None, tag_pos: str | None,
                            fusion_name: str | None):
    if not fluor_code and not tag_code:
        return None
    fid = cx.execute(
        text("SELECT id FROM public.fluors WHERE fluor_code=:c LIMIT 1"),
        {"c": (fluor_code or None)}
    ).scalar() if fluor_code else None
    tid = cx.execute(
        text("SELECT id FROM public.tags WHERE tag_code=:c LIMIT 1"),
        {"c": (tag_code or None)}
    ).scalar() if tag_code else None
    if fluor_code and not fid:
        raise ValueError(f"Unknown fluor_code '{fluor_code}'")
    if tag_code and not tid:
        raise ValueError(f"Unknown tag_code '{tag_code}'")

    fusion_id = cx.execute(text("""
        WITH ins AS (
          INSERT INTO public.fusions (fluor_id, tag_id, tag_pos, name)
          VALUES (:fid, :tid, NULLIF(:pos,''), NULLIF(:fname,''))
          ON CONFLICT DO NOTHING
          RETURNING id
        )
        SELECT id FROM ins
        UNION ALL
        SELECT id
        FROM public.fusions
        WHERE (fluor_id IS NOT DISTINCT FROM :fid)
          AND (tag_id  IS NOT DISTINCT FROM :tid)
          AND COALESCE(tag_pos,'') = COALESCE(:pos,'')
        LIMIT 1
    """), {"fid": fid, "tid": tid, "pos": (tag_pos or ""), "fname": (fusion_name or None)}).scalar()
    if not fusion_id:
        raise RuntimeError("Could not create or find fusion")

    cx.execute(text("""
        INSERT INTO public.join_plasmid_fusions (plasmid_id, fusion_id)
        VALUES (:pid, :fid)
        ON CONFLICT DO NOTHING
    """), {"pid": plasmid_id, "fid": fusion_id})
    return fusion_id

def _insert_plasmid_with_fusions(code: str, nickname: str,
                                 resistance: str | None,
                                 notes: str | None,
                                 fusion_rows: List[Dict[str, str]]):
    if not code or not nickname:
        raise ValueError("code and nickname are required")
    with _get_engine().begin() as cx:
        row = cx.execute(text("""
          INSERT INTO public.plasmids (code, name, nickname, resistance, created_at)
          VALUES (:code, :name, :nick, NULLIF(:res,''), now())
          ON CONFLICT (code) DO UPDATE
            SET name       = excluded.name,
                nickname   = excluded.nickname,
                resistance = excluded.resistance
          RETURNING id, code
        """), {
            "code": code.strip(),
            "name": nickname.strip(),
            "nick": nickname.strip(),
            "res":  (resistance or "").strip()
        }).mappings().first()
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

    # Basic plasmid fields
    c1, c2 = st.columns([2, 2])
    with c1:
        new_code = st.text_input("code (required)", placeholder="example pDQM001")
        new_nick = st.text_input("nickname (required)")
    with c2:
        new_res  = st.text_input("resistance")
        new_note = st.text_area("notes", height=80)

    st.divider()
    st.subheader("Fusions for this plasmid")

    # 3 selection tables side by side
    col_fluor, col_tag, col_pos = st.columns([2, 2, 1])

    with col_fluor:
        st.caption("Select fluor")
        fluor_df = _load_fluors()
        fluor_sel = st.data_editor(
            fluor_df,
            width="stretch",
            hide_index=True,
            num_rows="fixed",
            column_config={
                "✓":          st.column_config.CheckboxColumn("✓", default=False),
                "fluor_code": st.column_config.TextColumn("Fluor", disabled=True),
            },
            key="fluor_selector",
        )

    with col_tag:
        st.caption("Select tag")
        tag_df = _load_tags()
        tag_sel = st.data_editor(
            tag_df,
            width="stretch",
            hide_index=True,
            num_rows="fixed",
            column_config={
                "✓":        st.column_config.CheckboxColumn("✓", default=False),
                "tag_code": st.column_config.TextColumn("Tag", disabled=True),
            },
            key="tag_selector",
        )

    with col_pos:
        st.caption("Select tag position")
        pos_df = _load_tag_positions()
        pos_sel = st.data_editor(
            pos_df,
            width="stretch",
            hide_index=True,
            num_rows="fixed",
            column_config={
                "✓":      st.column_config.CheckboxColumn("✓", default=False),
                "tag_pos": st.column_config.TextColumn("Pos", disabled=True),
            },
            key="pos_selector",
        )

    # Optional manual fusion name
    fusion_name = st.text_input("Fusion name (optional)", value="")

    # Build a list of selected fusion rows in session state
    if "new_plasmid_fusions" not in st.session_state:
        st.session_state.new_plasmid_fusions = []

    # Single-click "add" button
    if st.button("➕ Add fusion to plasmid"):
        # Pick first checked fluor
        fs = fluor_sel[fluor_sel["✓"].fillna(False)]
        fluor_code = fs["fluor_code"].iloc[0] if not fs.empty else ""

        # Pick first checked tag
        ts = tag_sel[tag_sel["✓"].fillna(False)]
        tag_code = ts["tag_code"].iloc[0] if not ts.empty else ""

        # Pick first checked pos
        ps = pos_sel[pos_sel["✓"].fillna(False)]
        tag_pos = ps["tag_pos"].iloc[0] if not ps.empty else ""

        if not fluor_code and not tag_code:
            st.warning("Select at least a fluor or a tag before adding a fusion.")
        else:
            st.session_state.new_plasmid_fusions.append({
                "fluor_code": fluor_code,
                "tag_code":   tag_code,
                "tag_pos":    tag_pos,
                "fusion_name": fusion_name.strip(),
            })
            st.success("Fusion added to preview.")

    # Preview of all fusions that will be linked
    st.subheader("Fusion preview")
    fusions_preview = st.session_state.new_plasmid_fusions
    if fusions_preview:
        prev_df = pd.DataFrame(fusions_preview)
        st.dataframe(prev_df, width="stretch", hide_index=True)
    else:
        st.info("No fusions added yet. Use the tables above and click 'Add fusion to plasmid'.")

    # Save plasmid button
    if st.button("💾 Save new plasmid", type="primary"):
        try:
            res = _insert_plasmid_with_fusions(
                new_code.strip(),
                new_nick.strip(),
                new_res,
                new_note,
                fusions_preview,
            )
            st.success(f"Inserted/updated {res['plasmid_code']} • linked {res['linked_fusions']} fusion(s).")
            st.session_state.new_plasmid_fusions = []
        except Exception as e:
            st.error(f"Save failed: {e}")

if __name__ == "__main__":
    main()