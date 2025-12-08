# carp_app/ui/pages/210_🧪_overview_treatments.py
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
    def require_app_unlock() -> None:
        ...

from carp_app.ui.lib.page_engine import engine

# ───────── auth & page ─────────
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — Overview: Treatments",
    page_icon="🧪",
    layout="wide",
)
st.title("🧪 Overview: Treatments")


def _eng() -> Engine:
    return engine()


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


# ════════════════════════════════════════════════════════
# FILTERS
# ════════════════════════════════════════════════════════
with st.form("treatment_filters", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 1.2, 1.4, 0.8])
    with c1:
        q_raw = st.text_input(
            "Search (code / nickname / text / notes / source / labels)",
            "",
            key="treatments_search",
        )
    with c2:
        kind_raw = st.text_input(
            "Filter kind_code (contains)",
            "",
            key="treatments_kind",
        )
    with c3:
        source_raw = st.text_input(
            "Filter source_system (contains)",
            "",
            key="treatments_source",
        )
    with c4:
        lim = int(
            st.number_input(
                "Limit",
                min_value=50,
                max_value=5000,
                value=1000,
                step=50,
                key="treatments_limit",
            )
        )
    _ = st.form_submit_button("Apply", key="treatments_apply")

q = _norm(q_raw)
kind_token = _norm(kind_raw)
source_token = _norm(source_raw)

# ════════════════════════════════════════════════════════
# MAIN QUERY (via v11_treatment_label_star)
# ════════════════════════════════════════════════════════
where = ["1=1"]
params: Dict[str, object] = {"lim": lim}

if q:
    params["ql"] = f"%{q}%"
    where.append(
        "("
        "  treat_code                        ILIKE :ql"
        " OR COALESCE(nickname,'')          ILIKE :ql"
        " OR COALESCE(display_name,'')      ILIKE :ql"
        " OR COALESCE(treat_text,'')        ILIKE :ql"
        " OR COALESCE(notes,'')             ILIKE :ql"
        " OR COALESCE(kind_code,'')         ILIKE :ql"
        " OR COALESCE(treatment_type,'')    ILIKE :ql"
        " OR COALESCE(source_system,'')     ILIKE :ql"
        " OR COALESCE(import_batch_id,'')   ILIKE :ql"
        " OR COALESCE(treatment_display,'') ILIKE :ql"
        " OR COALESCE(fluor_tag_style,'')   ILIKE :ql"
        " OR COALESCE(fluor_organelle_style,'') ILIKE :ql"
        " OR COALESCE(genotype_basecode_code,'') ILIKE :ql"
        " OR COALESCE(materials_by_kind,'') ILIKE :ql"
        ")"
    )

if kind_token:
    params["kind_like"] = f"%{kind_token}%"
    where.append("COALESCE(kind_code,'') ILIKE :kind_like")

if source_token:
    params["src_like"] = f"%{source_token}%"
    where.append("COALESCE(source_system,'') ILIKE :src_like")

where_sql = " AND ".join(where)

sql = text(
    f"""
    SELECT
      treatment_id::text AS treatment_id,
      treat_code,
      kind_code,
      treatment_type,
      nickname,
      display_name,
      treat_text,
      notes,
      source_system,
      import_batch_id,
      created_at,
      n_mixes,
      n_constructs,
      n_dyes,
      ingredient_kinds,
      n_kinds,
      genotype_basecode_code,
      materials_by_kind,
      fluor_tag_style,
      fluor_organelle_style,
      treatment_display
    FROM public.v11_treatment_label_star
    WHERE {where_sql}
    ORDER BY created_at DESC NULLS LAST, treat_code
    LIMIT :lim;
    """
)

with _eng().begin() as cx:
    df = pd.read_sql(sql, cx, params=params)

if df.empty:
    st.info("No treatments match these filters.")
else:
    df = df.fillna("")

    # ── Build delivery-form-aware material label per treatment ───────────────
    with _eng().begin() as cx:
        df_delivery = pd.read_sql(
            text(
                """
                WITH base AS (
                  SELECT
                    t.id::text                     AS treatment_id,
                    COALESCE(tmc.delivery_form,'') AS delivery_form,
                    c.construct_code               AS construct_code
                  FROM public.treatments t
                  JOIN public.treatment_mixes tm
                    ON tm.treatment_id = t.id
                  JOIN public.treatment_mix_constructs tmc
                    ON tmc.mix_id = tm.id
                  JOIN public.constructs c
                    ON c.id = tmc.construct_id
                )
                SELECT
                  treatment_id,
                  delivery_form,
                  string_agg(
                    DISTINCT construct_code::text,
                    ', ' ORDER BY construct_code
                  ) AS construct_codes
                FROM base
                GROUP BY treatment_id, delivery_form;
                """
            ),
            cx,
        )

    delivery_label_map: Dict[str, str] = {}
    if not df_delivery.empty:
        for tid, sub in df_delivery.groupby("treatment_id"):
            parts: List[str] = []
            for _, r in sub.iterrows():
                form = (r["delivery_form"] or "").strip()
                codes = (r["construct_codes"] or "").strip()
                if not codes:
                    continue
                if form:
                    parts.append(f"{form}({codes})")
                else:
                    parts.append(codes)
            delivery_label_map[tid] = "; ".join(parts)

    df["materials_delivery_style"] = df["treatment_id"].map(
        lambda tid: delivery_label_map.get(tid, "")
    )

    st.caption(f"{len(df)} treatment(s)")

    # keep an untouched copy in case we ever want to diff more fields
    df_orig = df.copy()

    view = pd.DataFrame(
        {
            "treat_code": df["treat_code"],
            "nickname": df["nickname"],
            "treatment_type": df["treatment_type"],
            "kind_code": df["kind_code"],
            "treatment_display": df["treatment_display"],
            "materials_delivery_style": df["materials_delivery_style"],
            "fluor_tag_style": df["fluor_tag_style"],
            "fluor_organelle_style": df["fluor_organelle_style"],
            "ingredient_kinds": df["ingredient_kinds"],
            "n_kinds": df["n_kinds"],
            "treat_text": df["treat_text"],
            "n_mixes": df["n_mixes"],
            "n_constructs": df["n_constructs"],
            "n_dyes": df["n_dyes"],
            "source_system": df["source_system"],
            "import_batch_id": df["import_batch_id"],
            "created_at": df["created_at"],
            "treatment_id": df["treatment_id"],
            "notes": df["notes"],
            "genotype_basecode_code": df["genotype_basecode_code"],
            "materials_by_kind": df["materials_by_kind"],
            "display_name": df["display_name"],
        }
    )
    view.insert(0, "✓ Select", False)

    grid = st.data_editor(
        view,
        key="treatments_overview_v11",
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        column_order=[
            "✓ Select",
            "treat_code",
            "nickname",
            "treatment_type",
            "kind_code",
            "treatment_display",
            "materials_delivery_style",
            "fluor_tag_style",
            "fluor_organelle_style",
            "ingredient_kinds",
            "n_kinds",
            "treat_text",
            "n_mixes",
            "n_constructs",
            "n_dyes",
            "source_system",
            "import_batch_id",
            "created_at",
        ],
        column_config={
            "✓ Select": st.column_config.CheckboxColumn("✓", default=False),
            "treat_code": st.column_config.TextColumn("treat_code", disabled=True),
            "nickname": st.column_config.TextColumn("nickname", disabled=False),
            "treatment_type": st.column_config.TextColumn(
                "treatment_type", disabled=True
            ),
            "kind_code": st.column_config.TextColumn("kind_code", disabled=True),
            "treatment_display": st.column_config.TextColumn(
                "treatment_display (tg-style)", disabled=True, width="large"
            ),
            "materials_delivery_style": st.column_config.TextColumn(
                "materials (by delivery_form)", disabled=True, width="large"
            ),
            "fluor_tag_style": st.column_config.TextColumn(
                "fluor-tag style", disabled=True, width="large"
            ),
            "fluor_organelle_style": st.column_config.TextColumn(
                "fluor-organelle style", disabled=True, width="large"
            ),
            "ingredient_kinds": st.column_config.TextColumn(
                "ingredient_kinds", disabled=True
            ),
            "n_kinds": st.column_config.NumberColumn("n_kinds", disabled=True),
            "treat_text": st.column_config.TextColumn(
                "treat_text", disabled=True, width="large"
            ),
            "n_mixes": st.column_config.NumberColumn("mixes", disabled=True),
            "n_constructs": st.column_config.NumberColumn(
                "construct ingredients", disabled=True
            ),
            "n_dyes": st.column_config.NumberColumn(
                "dye ingredients", disabled=True
            ),
            "source_system": st.column_config.TextColumn(
                "source_system", disabled=True
            ),
            "import_batch_id": st.column_config.TextColumn(
                "import_batch_id", disabled=True
            ),
            "created_at": st.column_config.DatetimeColumn(
                "created_at", disabled=True
            ),
            "treatment_id": st.column_config.TextColumn(
                "treatment_id", disabled=True
            ),
            "notes": st.column_config.TextColumn("notes", disabled=True),
            "genotype_basecode_code": st.column_config.TextColumn(
                "genotype_basecode_code", disabled=True
            ),
            "materials_by_kind": st.column_config.TextColumn(
                "materials_by_kind", disabled=True
            ),
            "display_name": st.column_config.TextColumn(
                "display_name", disabled=True
            ),
        },
    )

    # ════════════════════════════════════════════════════
    # NICKNAME SAVE HANDLING
    # ════════════════════════════════════════════════════
    changed_mask = grid["nickname"] != view["nickname"]
    changed_idxs = grid.index[changed_mask].tolist()

    if changed_idxs:
        st.warning(f"{len(changed_idxs)} nickname change(s) pending save.")
        if st.button("💾 Save nickname changes", type="primary"):
            updates = []
            for idx in changed_idxs:
                new_nick = _norm(grid.loc[idx, "nickname"])
                old_nick = _norm(view.loc[idx, "nickname"])
                tid = grid.loc[idx, "treatment_id"]
                if new_nick and new_nick != old_nick and tid:
                    updates.append((tid, new_nick))

            if not updates:
                st.info("No valid nickname changes to save.")
            else:
                try:
                    with _eng().begin() as cx:
                        for tid, new_nick in updates:
                            cx.execute(
                                text(
                                    """
                                    UPDATE public.treatments
                                    SET nickname = :nickname
                                    WHERE id = CAST(:tid AS uuid)
                                    """
                                ),
                                {"nickname": new_nick, "tid": tid},
                            )
                    st.success(f"Saved {len(updates)} nickname change(s).")
                except Exception as e:
                    st.error(f"Error saving nickname changes: {e}")

    # ════════════════════════════════════════════════════
    # DETAILS
    # ════════════════════════════════════════════════════
    st.divider()
    st.subheader("Treatment details")

    selected_idxs: List[int] = []
    if "✓ Select" in grid.columns:
        selected_idxs = grid.index[grid["✓ Select"] == True].to_series().tolist()

    if not selected_idxs:
        st.info("Select one treatment above to see mixes and ingredients.")
    elif len(selected_idxs) > 1:
        st.info("Select exactly one treatment to view details.")
    else:
        row = grid.loc[selected_idxs[0]]
        treatment_id = row["treatment_id"]
        treat_code = row["treat_code"]

        tab1, tab2 = st.tabs(["Overview", "Mixes & ingredients"])

        with tab1:
            st.write(
                {
                    "treat_code": row["treat_code"],
                    "nickname": row["nickname"],
                    "display_name": row["display_name"],
                    "treatment_type": row["treatment_type"],
                    "kind_code": row["kind_code"],
                    "treatment_display (tg-style)": row["treatment_display"],
                    "materials_delivery_style": row["materials_delivery_style"],
                    "fluor_tag_style": row["fluor_tag_style"],
                    "fluor_organelle_style": row["fluor_organelle_style"],
                    "ingredient_kinds": row["ingredient_kinds"],
                    "n_kinds": int(row["n_kinds"]),
                    "treat_text": row["treat_text"],
                    "notes": row["notes"],
                    "genotype_basecode_code": row["genotype_basecode_code"],
                    "materials_by_kind": row["materials_by_kind"],
                    "source_system": row["source_system"],
                    "import_batch_id": row["import_batch_id"],
                    "created_at": row["created_at"],
                    "n_mixes": int(row["n_mixes"]),
                    "n_constructs": int(row["n_constructs"]),
                    "n_dyes": int(row["n_dyes"]),
                }
            )

        with tab2:
            with _eng().begin() as cx:
                mixes_df = pd.read_sql(
                    text(
                        """
                        SELECT
                          tm.id::text AS mix_id,
                          tm.mix_code,
                          tm.notes,
                          tm.created_at
                        FROM public.treatment_mixes tm
                        WHERE tm.treatment_id = CAST(:tid AS uuid)
                        ORDER BY tm.mix_code, tm.created_at
                        """
                    ),
                    cx,
                    params={"tid": treatment_id},
                )

                ingredients_df = pd.read_sql(
                    text(
                        """
                        WITH mix_base AS (
                          SELECT id::text AS mix_id, mix_code
                          FROM public.treatment_mixes
                          WHERE treatment_id = CAST(:tid AS uuid)
                        ),
                        construct_ing AS (
                          SELECT
                            mb.mix_id,
                            mb.mix_code,
                            'construct'::text AS ingredient_type,
                            c.construct_code  AS ingredient_code,
                            COALESCE(c.construct_name, c.construct_code) AS ingredient_name,
                            COALESCE(tmc.delivery_form,'') AS delivery_form,
                            tmc.concentration
                          FROM mix_base mb
                          JOIN public.treatment_mix_constructs tmc
                            ON tmc.mix_id = CAST(mb.mix_id AS uuid)
                          JOIN public.constructs c
                            ON c.id = tmc.construct_id
                        ),
                        dye_ing AS (
                          SELECT
                            mb.mix_id,
                            mb.mix_code,
                            'dye'::text AS ingredient_type,
                            d.code       AS ingredient_code,
                            COALESCE(d.display_name, d.nickname, d.code) AS ingredient_name,
                            ''::text     AS delivery_form,
                            tmd.concentration
                          FROM mix_base mb
                          JOIN public.treatment_mix_dyes tmd
                            ON tmd.mix_id = CAST(mb.mix_id AS uuid)
                          JOIN public.dyes d
                            ON d.id = tmd.dye_id
                        )
                        SELECT *
                        FROM construct_ing
                        UNION ALL
                        SELECT *
                        FROM dye_ing
                        ORDER BY mix_code, ingredient_type, ingredient_code, delivery_form
                        """
                    ),
                    cx,
                    params={"tid": treatment_id},
                )

            st.markdown(f"**Mixes for treatment {treat_code}**")
            if mixes_df.empty:
                st.info("No mixes found for this treatment.")
            else:
                st.dataframe(
                    mixes_df[["mix_code", "notes", "created_at", "mix_id"]],
                    hide_index=True,
                    width="stretch",
                )

            st.markdown(f"**Ingredients for treatment {treat_code}**")
            if ingredients_df.empty:
                st.info("No construct/dye ingredients found for this treatment.")
            else:
                st.dataframe(
                    ingredients_df[
                        [
                            "mix_code",
                            "ingredient_type",
                            "ingredient_code",
                            "ingredient_name",
                            "delivery_form",
                            "concentration",
                        ]
                    ],
                    hide_index=True,
                    width="stretch",
                )

    st.download_button(
        "⬇︎ Download treatments (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="treatments_overview_v11.csv",
        type="secondary",
        mime="text/csv",
    )