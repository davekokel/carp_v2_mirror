# supabase/ui/pages/01_📤_upload_fish_seedkit.py
from __future__ import annotations

# --- put project root on sys.path (works no matter how Streamlit is launched) ---
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]  # …/carp_v2
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Centralized engine & helpers
from supabase.ui.lib.app_ctx import get_engine, engine_info
from supabase.ui.lib.csv_normalize import normalize_fish_seedkit, validate_seedkit
from supabase.ui.lib.alloc_link import (
    resolve_or_allocate_number,
    ensure_transgene_pair,
    link_fish_to,
)

# 🔒 auth
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

from datetime import UTC, datetime
from typing import List, Dict, Any, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text

PAGE_TITLE = "CARP — Upload Fish (CSV only)"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
st.title("📤 Upload Fish (CSV only)")

# --------------------------------------------------------------------------------------
# Engine / DB info
# --------------------------------------------------------------------------------------
eng = get_engine()
dbg = engine_info(eng)
st.caption(f"DB debug → db={dbg['db']} user={dbg['usr']} host={dbg['host']}:{dbg['port']}")

# --------------------------------------------------------------------------------------
# Preflight (read-only) — fail fast if required objects are missing
# --------------------------------------------------------------------------------------
REQUIRED_TABLES = [
    ("public", "fish"),
    ("public", "fish_transgene_alleles"),
    ("public", "transgene_allele_registry"),
    ("public", "transgene_allele_counters"),
]
REQUIRED_VIEW = ("public", "v_fish_overview")

with eng.begin() as cx:
    missing: List[str] = []
    for sch, tbl in REQUIRED_TABLES:
        ok = cx.execute(
            text("select to_regclass(:q) is not null"),
            {"q": f"{sch}.{tbl}"},
        ).scalar()
        if not ok:
            missing.append(f"{sch}.{tbl}")
    ok_view = cx.execute(
        text("select to_regclass(:q) is not null"),
        {"q": f"{REQUIRED_VIEW[0]}.{REQUIRED_VIEW[1]}"},
    ).scalar()
    if not ok_view:
        missing.append(f"{REQUIRED_VIEW[0]}.{REQUIRED_VIEW[1]}")

if missing:
    st.error(
        "Database schema is incomplete. Missing objects:\n\n- " + "\n- ".join(missing) +
        "\n\nRun your migrations, then reload this page."
    )
    st.stop()

# --------------------------------------------------------------------------------------
# UI State
# --------------------------------------------------------------------------------------
PREVIEW_KEY = "upload_preview_df"
RESULT_KEY  = "upload_insert_result"

def _reset_preview():
    st.session_state.pop(PREVIEW_KEY, None)
    st.session_state.pop(RESULT_KEY, None)

uploaded = st.file_uploader("Upload .csv", type=["csv"], on_change=_reset_preview)

col1, col2, col3 = st.columns([1,1,2])
with col1:
    load_clicked = st.button("Load preview", disabled=uploaded is None)
with col2:
    insert_clicked = st.button("Insert into database", disabled=(PREVIEW_KEY not in st.session_state))
with col3:
    st.caption("CSV headers expected: fish_code, transgene_base_code, allele_nickname, "
               "name, created_by, date_birth, zygosity. (legacy: allele_number)")

# --------------------------------------------------------------------------------------
# Load Preview
# --------------------------------------------------------------------------------------
if load_clicked and uploaded is not None:
    try:
        raw = uploaded.read().decode("utf-8")
        df_in = pd.read_csv(io.StringIO(raw))
        df_norm = normalize_fish_seedkit(df_in)
        issues = validate_seedkit(df_norm)
        if issues:
            st.warning(" • ".join(issues))
        st.session_state[PREVIEW_KEY] = df_norm
    except Exception as e:
        st.exception(e)

if PREVIEW_KEY in st.session_state:
    df_norm = st.session_state[PREVIEW_KEY]
    st.subheader("Preview (normalized)")
    preview_cols = [
        "fish_code","name","created_by","date_birth",
        "transgene_base_code","allele_nickname","allele_number","zygosity",
    ]
    present = [c for c in preview_cols if c in df_norm.columns]
    st.dataframe(df_norm[present], width="stretch")

# --------------------------------------------------------------------------------------
# Insert
# --------------------------------------------------------------------------------------
if insert_clicked and (PREVIEW_KEY in st.session_state):
    created_ct = 0
    updated_ct = 0   # we don't track separately in this simple flow; left for future
    linked_ct  = 0
    skipped_ct = 0

    try:
        df_norm = st.session_state[PREVIEW_KEY]

        with eng.begin() as conn:
            # 1) Upsert fish rows, collect ids
            fish_cols = ["fish_code","name","created_by","date_birth"]
            to_insert = df_norm[fish_cols].copy()

            created_rows: List[Dict[str, Any]] = []
            for _, r in to_insert.iterrows():
                row = conn.execute(
                    text("""
                        insert into public.fish (id, fish_code, name, created_by, date_birth)
                        values (gen_random_uuid(), :code, :name, :by, :dob)
                        on conflict (fish_code) do update set
                          name=excluded.name,
                          created_by=excluded.created_by,
                          date_birth=excluded.date_birth
                        returning id, fish_code
                    """),
                    {
                        "code": r.get("fish_code"),
                        "name": r.get("name"),
                        "by":   r.get("created_by"),
                        "dob":  r.get("date_birth"),
                    },
                ).mappings().first()
                created_rows.append(dict(row))
            created_ct = len(created_rows)

            # 2) Link genotype for each row (registry-first; legacy-aware)
            code_to_id = {c["fish_code"]: c["id"] for c in created_rows}

            base_nonempty = df_norm["transgene_base_code"].astype("string").str.strip().ne("")
            nick_nonempty = df_norm["allele_nickname"].astype("string").str.strip().ne("")
            has_num       = df_norm["allele_number"].notna()

            gmask = base_nonempty & (nick_nonempty | has_num)
            st.caption(
                "debug: base_nonempty=%d nick_nonempty=%d gmask=%d"
                % (int(base_nonempty.sum()), int(nick_nonempty.sum()), int(gmask.sum()))
            )

            for _, r in df_norm.loc[gmask].iterrows():
                fish_code = r["fish_code"]
                fish_id   = code_to_id.get(fish_code) or conn.execute(
                    text("select id from public.fish where fish_code=:c limit 1"),
                    {"c": fish_code},
                ).scalar()

                if not fish_id:
                    skipped_ct += 1
                    continue

                base = (r.get("transgene_base_code") or "").strip()
                nick = (r.get("allele_nickname") or "").strip() or None
                by   = (r.get("created_by") or None)
                zyg  = (r.get("zygosity") or None)

                # (a) try registry modern/legacy
                n: Optional[int] = None
                if nick:
                    n = resolve_or_allocate_number(conn, base, nick, by)
                    if n is not None:
                        st.caption(f"alloc: registry hit base='{base}' nick='{nick}' → n={int(n)}")

                # (b) fallback to CSV numeric (legacy) if still None
                if n is None:
                    try:
                        n = int(r.get("allele_number"))
                        st.caption(f"alloc: csv numeric base='{base}' → n={n}")
                    except Exception:
                        n = None

                if n is None:
                    # diag: show sample of registry
                    try:
                        rows = conn.execute(
                            text("""
                            select allele_nickname, allele_number
                            from public.transgene_allele_registry
                            where transgene_base_code = :b
                            order by allele_nickname
                            limit 10
                            """),
                            {"b": base},
                        ).mappings().all()
                        sample = ", ".join(f"{row['allele_nickname']}→{row['allele_number']}" for row in rows)
                        st.caption(f"alloc: registry sample for base='{base}' [{sample}]")
                    except Exception:
                        pass
                    st.caption(f"debug skip: base='{base}' nick='{nick}' (no number)")
                    skipped_ct += 1
                    continue

                # (c) ensure FK pair exists and link the fish
                ensure_transgene_pair(conn, base, n)
                link_fish_to(conn, str(fish_id), base, n, zygosity=zyg, nickname=nick)
                linked_ct += 1

        # write result
        st.session_state[RESULT_KEY] = {
            "created": int(created_ct),
            "updated": int(updated_ct),
            "with_alleles": int(linked_ct),
            "skipped_no_allele": int(skipped_ct),
            "skipped": int(skipped_ct),
        }

    except Exception as e:
        st.exception(e)

# --------------------------------------------------------------------------------------
# Result + Overview slice
# --------------------------------------------------------------------------------------
res = st.session_state.get(RESULT_KEY)
if res:
    st.success(
        f"Inserted {res.get('created',0)} new, updated {res.get('updated',0)}; "
        f"linked genotype for {res.get('with_alleles',0)} rows; "
        f"skipped {res.get('skipped_no_allele',res.get('skipped',0))} without allele."
    )

    st.markdown("#### Recent rows (from `v_fish_overview`)")
    try:
        recent = pd.read_sql(
            """
            select id, fish_code, name,
                   transgene_base_code_filled, allele_code_filled, allele_name_filled,
                   created_at, created_by
            from public.v_fish_overview
            order by created_at desc
            limit 50
            """,
            eng,
        )
        if "id" in recent.columns:
            recent["id"] = recent["id"].astype(str)
        st.dataframe(recent, width="stretch")
    except Exception as e:
        st.warning(f"Could not read v_fish_overview yet: {e}")