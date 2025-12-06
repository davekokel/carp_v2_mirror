from __future__ import annotations

import pathlib
import sys
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ───────── repo bootstrap ─────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview: Transgenes & Alleles",
    page_icon="🔎",
    layout="wide",
)
st.title("🔎 Overview: Transgenes & Alleles")


def _eng() -> Engine:
    return engine()


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


# ════════════════════════════════════════════════════════
# TRANSGENES — FILTERS + TABLE (TOP)
# ════════════════════════════════════════════════════════
st.subheader("Transgenes")

with st.form("transgene_filters", clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        q_raw_tg = st.text_input(
            "Search (base_code / nickname / display_label / description)",
            "",
            key="tg_search",
        )
    with c2:
        lim_tg = int(
            st.number_input(
                "Limit (transgenes)",
                min_value=50,
                max_value=5000,
                value=1000,
                step=50,
                key="tg_limit",
            )
        )
    _ = st.form_submit_button("Apply", key="tg_apply")

q_tg = _norm(q_raw_tg)
q_param_tg = q_tg or None

sql_tg = text(
    """
    WITH allele_counts AS (
      SELECT
        transgene_base_code,
        COUNT(*)::int AS n_alleles
      FROM public.transgene_alleles
      GROUP BY transgene_base_code
    )
    SELECT
      t.transgene_base_code,
      t.nickname,
      t.display_name,
      t.transgene_name,
      t.description,
      t.created_at,
      COALESCE(ac.n_alleles, 0) AS n_alleles
    FROM public.transgenes t
    LEFT JOIN allele_counts ac
      ON ac.transgene_base_code = t.transgene_base_code
    WHERE (
         :q IS NULL
      OR  t.transgene_base_code        ILIKE :ql
      OR  COALESCE(t.nickname,'')      ILIKE :ql
      OR  COALESCE(t.display_name,'')  ILIKE :ql
      OR  COALESCE(t.transgene_name,'') ILIKE :ql
      OR  COALESCE(t.description,'')   ILIKE :ql
    )
    ORDER BY t.transgene_base_code
    LIMIT :lim;
    """
)

params_tg = {
    "q": q_param_tg,
    "ql": f"%{q_tg}%" if q_tg else None,
    "lim": lim_tg,
}

with _eng().begin() as cx:
    df_tg = pd.read_sql(sql_tg, cx, params=params_tg)

if df_tg.empty:
    st.info("No transgenes match these filters.")
    selected_base_code = None
else:
    df_tg = df_tg.fillna("")

    # build a display label: display_name → transgene_name → nickname → base_code
    def _display_label(row: pd.Series) -> str:
        for col in ("display_name", "transgene_name", "nickname", "transgene_base_code"):
            val = _norm(row.get(col))
            if val:
                return val
        return ""

    df_tg["display_label"] = df_tg.apply(_display_label, axis=1)

    st.caption(f"{len(df_tg)} transgene(s)")

    view_tg = pd.DataFrame(
        {
            "transgene_base_code": df_tg["transgene_base_code"],
            "nickname": df_tg["nickname"],
            "display_label": df_tg["display_label"],
            "n_alleles": df_tg["n_alleles"],
            "description": df_tg["description"],
            "created_at": df_tg["created_at"],
            "display_name": df_tg["display_name"],
            "transgene_name": df_tg["transgene_name"],
        }
    )
    view_tg.insert(0, "✓ Select", False)

    df_orig_tg = view_tg.copy()

    grid_tg = st.data_editor(
        view_tg,
        key="transgenes_overview_v11",
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        column_order=[
            "✓ Select",
            "transgene_base_code",
            "nickname",
            "display_label",
            "n_alleles",
            "description",
            "created_at",
        ],
        column_config={
            "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
            "transgene_base_code": st.column_config.TextColumn(
                "base_code", disabled=True
            ),
            # nickname is editable
            "nickname": st.column_config.TextColumn(
                "nickname", disabled=False
            ),
            "display_label": st.column_config.TextColumn(
                "display_label", disabled=True, width="large"
            ),
            "n_alleles": st.column_config.NumberColumn(
                "n_alleles", disabled=True
            ),
            "description": st.column_config.TextColumn(
                "description", disabled=True, width="large"
            ),
            "created_at": st.column_config.DatetimeColumn(
                "created_at", disabled=True
            ),
            "display_name": st.column_config.TextColumn(
                "display_name", disabled=True
            ),
            "transgene_name": st.column_config.TextColumn(
                "transgene_name", disabled=True
            ),
        },
    )

    # nickname save handling
    changed_mask = grid_tg["nickname"] != df_orig_tg["nickname"]
    changed_idxs = grid_tg.index[changed_mask].tolist()

    if changed_idxs:
        st.warning(f"{len(changed_idxs)} nickname change(s) pending save.")
        if st.button("💾 Save transgene nicknames", type="primary"):
            updates = []
            for idx in changed_idxs:
                new_nick = _norm(grid_tg.loc[idx, "nickname"])
                old_nick = _norm(df_orig_tg.loc[idx, "nickname"])
                base_code = grid_tg.loc[idx, "transgene_base_code"]
                if new_nick and new_nick != old_nick and base_code:
                    updates.append((base_code, new_nick))

            if not updates:
                st.info("No valid nickname changes to save.")
            else:
                try:
                    with _eng().begin() as cx:
                        for base_code, new_nick in updates:
                            cx.execute(
                                text(
                                    """
                                    UPDATE public.transgenes
                                    SET nickname = :nickname
                                    WHERE transgene_base_code = :base_code
                                    """
                                ),
                                {"nickname": new_nick, "base_code": base_code},
                            )
                    st.success(f"Saved {len(updates)} nickname change(s).")
                except Exception as e:
                    st.error(f"Error saving nickname changes: {e}")

    # Determine selected transgene (for alleles section)
    selected_base_code: Optional[str] = None
    if isinstance(grid_tg, pd.DataFrame) and "✓ Select" in grid_tg.columns:
        sel = grid_tg.loc[grid_tg["✓ Select"] == True]
        if not sel.empty:
            selected_base_code = (
                str(sel.iloc[0]["transgene_base_code"]).strip() or None
            )

    st.download_button(
        "⬇︎ Download transgenes (CSV)",
        data=df_tg.to_csv(index=False).encode("utf-8"),
        file_name="transgenes_overview_v11.csv",
        type="secondary",
        mime="text/csv",
    )

# ════════════════════════════════════════════════════════
# ALLELES — DETAIL TABLE (BOTTOM)
# ════════════════════════════════════════════════════════
st.divider()
st.subheader("Alleles for selected transgene")

if not selected_base_code:
    st.info("Select a transgene above to see its alleles.")
else:
    st.caption(f"Showing alleles for **{selected_base_code}**")

    sql_alleles = text(
        """
        SELECT
          transgene_base_code,
          allele_number,
          allele_name,
          allele_nickname,
          notes,
          created_at
        FROM public.transgene_alleles
        WHERE transgene_base_code = :base_code
        ORDER BY allele_number;
        """
    )

    with _eng().begin() as cx:
        df_alleles = pd.read_sql(
            sql_alleles, cx, params={"base_code": selected_base_code}
        )

    if df_alleles.empty:
        st.info("No alleles defined yet for this transgene.")
    else:
        df_alleles = df_alleles.fillna("")
        st.caption(f"{len(df_alleles)} allele(s)")

        view_alleles = df_alleles[
            [
                "transgene_base_code",
                "allele_number",
                "allele_name",
                "allele_nickname",
                "notes",
                "created_at",
            ]
        ]

        st.dataframe(
            view_alleles,
            hide_index=True,
            width="stretch",
        )

        st.download_button(
            "⬇︎ Download alleles (CSV)",
            data=df_alleles.to_csv(index=False).encode("utf-8"),
            file_name=f"transgene_alleles_{selected_base_code}.csv",
            type="secondary",
            mime="text/csv",
        )