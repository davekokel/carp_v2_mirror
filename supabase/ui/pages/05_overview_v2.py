from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

import os, sys, importlib
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# queries
import supabase.queries as _queries
importlib.reload(_queries)
from supabase.queries import load_fish_overview

# page bootstrap
from supabase.ui.lib.page_bootstrap import (
    set_page, get_params, set_params,
    text_search, kpi_row, paginate, pager_controls, download_csv
)

# ----- engine resolver -----
def _get_engine():
    # Prefer app context if available
    try:
        from supabase.ui.lib.app_ctx import get_engine as ctx_engine  # your existing helper
        return ctx_engine()
    except Exception:
        pass
    # Fallback to DB_URL from env or secrets
    from sqlalchemy import create_engine
    url = os.environ.get("DB_URL") or st.secrets.get("DB_URL", None)
    if not url:
        raise RuntimeError("DB_URL is not set (env or secrets). Set DB_URL or configure app_ctx.get_engine().")
    return create_engine(url)

ENGINE = _get_engine()

set_page("CARP — Overview v2", icon="🔎", layout="wide")

@st.cache_data(show_spinner=False)
def _load() -> pd.DataFrame:
    df = load_fish_overview(ENGINE)
    needed = ["fish_code","name","nickname","created_at","created_by","date_birth","batch_label","seed_batch_id",
              "transgene_base_code","allele_number","zygosity"]
    for c in needed:
        if c not in df.columns:
            df[c] = None

    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    if "date_birth" in df.columns:
        df["date_birth"] = pd.to_datetime(df["date_birth"], errors="coerce").dt.date

    if "batch_label" in df.columns and "seed_batch_id" in df.columns:
        df["batch_display"] = df["batch_label"].fillna(df["seed_batch_id"])
    else:
        df["batch_display"] = df.get("batch_label") or df.get("seed_batch_id")

    now = datetime.now(timezone.utc).date()
    if "date_birth" in df.columns:
        df["age_days"] = (pd.to_datetime(now) - pd.to_datetime(df["date_birth"])).dt.days
        df.loc[df["date_birth"].isna(), "age_days"] = None
    else:
        df["age_days"] = None

    df["has_transgene"] = df["transgene_base_code"].notna()
    df["has_nickname"] = df["nickname"].fillna("").astype(str).str.len().gt(0)
    return df

def main():
    df = _load()
    qp = get_params()

    with st.sidebar:
        st.subheader("Filters")
        q = st.text_input("Search", qp.get("q", [""])[0] if qp.get("q") else "")

        batches = sorted([b for b in df["batch_display"].dropna().unique().tolist() if b])
        batch = st.selectbox("Batch / Seed", ["(all)"] + batches, index=0)
        batch = None if batch == "(all)" else batch

        creators = sorted([c for c in df["created_by"].dropna().unique().tolist() if c])
        created_by = st.multiselect("Created by", options=creators, default=qp.get("cb", []))

        st.markdown("**Quick filters**")
        q_has_tg = st.checkbox("Has transgene", value=qp.get("qtg", ["0"])[0] == "1")
        q_has_nk = st.checkbox("Has nickname", value=qp.get("qnk", ["0"])[0] == "1")
        max_age = st.number_input("Max age (days)", min_value=0, value=int(qp.get("age", [0])[0]) if qp.get("age") else 0, step=1)

        page_size = int(qp.get("ps", [100])[0]) if qp.get("ps") else 100
        page_size = st.select_slider("Rows per page", options=[25,50,100,200,500], value=page_size)

    set_params(
        q=q or None, b=batch or None, cb=created_by or None, ps=page_size,
        qtg="1" if q_has_tg else "0",
        qnk="1" if q_has_nk else "0",
        age=max_age or None
    )

    out = text_search(df, q, cols=["fish_code","name","nickname","batch_display","created_by"])
    if batch:
        out = out[out["batch_display"] == batch]
    if created_by:
        out = out[out["created_by"].isin(created_by)]
    if q_has_tg and "has_transgene" in out.columns:
        out = out[out["has_transgene"]]
    if q_has_nk and "has_nickname" in out.columns:
        out = out[out["has_nickname"]]
    if max_age and "age_days" in out.columns:
        out = out[(out["age_days"].notna()) & (out["age_days"] <= max_age)]

    kpi_row([
        ("Rows (filtered)", f"{len(out):,}"),
        ("Unique Batches", int(out["batch_display"].dropna().nunique())),
        ("Creators", int(out["created_by"].dropna().nunique())),
    ])

    with st.expander("Batch summary", expanded=False):
        if len(out):
            summary = out.groupby("batch_display", dropna=True, as_index=False)["fish_code"].count().rename(columns={"fish_code":"rows"})
            st.dataframe(summary.sort_values("rows", ascending=False), hide_index=True, use_container_width=True)
        else:
            st.info("No rows to summarize.")

    download_csv(out, filename="overview_v2.csv", label="Download CSV")

    page = int(qp.get("page", [1])[0]) if qp.get("page") else 1
    page_df, pages, page = paginate(out.reset_index(drop=True), page, page_size)
    page = pager_controls(page, pages, key="ov2")
    set_params(q=q or None, b=batch or None, cb=created_by or None, ps=page_size, page=page,
               qtg="1" if q_has_tg else "0", qnk="1" if q_has_nk else "0", age=max_age or None)

    st.dataframe(
        page_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "fish_code": st.column_config.TextColumn("Fish Code"),
            "name": st.column_config.TextColumn("Name"),
            "nickname": st.column_config.TextColumn("Nickname"),
            "batch_display": st.column_config.TextColumn("Batch / Seed"),
            "created_by": st.column_config.TextColumn("Created By"),
            "date_birth": st.column_config.DateColumn("Birth Date"),
            "age_days": st.column_config.NumberColumn("Age (days)"),
            "created_at": st.column_config.DatetimeColumn("Created At (UTC)"),
        }
    )

if __name__ == "__main__":
    main()
