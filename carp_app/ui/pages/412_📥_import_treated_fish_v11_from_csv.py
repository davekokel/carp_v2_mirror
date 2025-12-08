from __future__ import annotations

import sys
import pathlib
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy.engine import Engine

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
from carp_app.ui.lib.page_engine import engine as _engine

from carp_app.etl.fish_v11_treatments_import import (
    load_treated_fish_from_csv as _load_treated_fish_from_csv,
)

# ───────── auth & page setup ─────────

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 📥 Import treated fish (v11) from CSV",
    page_icon="📥",
    layout="wide",
)
st.title("📥 Import treated fish (v11) from CSV")


def eng() -> Engine:
    return _engine()


# ───────── short explainer ─────────

st.markdown(
    """
This importer expects each row to describe **one treated fish instance**:

- `treatment_basecode`: injection mix basecode(s), e.g. `pDQM133` or `pDQM133,pDQM125`.
- `transgene_basecode` + `allele_nickname`: the **stable line(s)** this fish was injected into.
- `enzyme`: optional helper for the injection system (e.g. `tol2`, `Meganuclease`, `phiC; p14a`).

The ETL will:
- resolve or create the injection **treatment** from `treatment_basecode` (+ `enzyme`),
- resolve or create **transgene alleles** from `(transgene_basecode, allele_nickname)` pairs,
- create fish instances and link them to both the genotype and treatment.
"""
)

# ───────── template download ─────────

template_cols = [
    "line_nickname",
    "birthday",
    "genetic_background",
    "instance_stage",
    "treatment_basecode",
    "transgene_basecode",
    "allele_nickname",
    "zygosity",
    "created_by",
    "enzyme",
    "description",
]

template_df = pd.DataFrame(
    [
        {
            "line_nickname": "membrane tandem mSG; mChilada H2B (ef1a:2xlynk:tdmSG-tPT2A:tdmChilada:H2B)",
            "birthday": date.today().isoformat(),
            "genetic_background": "casper",
            "instance_stage": "injection",
            "treatment_basecode": "pDQM065",
            "transgene_basecode": "",
            "allele_nickname": "",
            "zygosity": "unknown",
            "created_by": "dqm",
            "enzyme": "tol2",
            "description": "tol2 injection into pdqm005:301 line",
        }
    ],
    columns=template_cols,
)

csv_bytes = template_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇︎ Download treated_fish_v11 CSV template",
    data=csv_bytes,
    file_name="treated_fish_v11_template.csv",
    type="secondary",
    mime="text/csv",
)

# ───────── file upload & run ─────────

uploaded_file = st.file_uploader(
    "Upload treated_fish_v11 CSV",
    type=["csv"],
    key="treated_fish_v11_import_csv",
)

if uploaded_file is not None:
    try:
        df_csv = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"Could not read CSV: {type(e).__name__}: {e}")
    else:
        st.caption("Preview of uploaded CSV (first 20 rows):")
        st.dataframe(df_csv.head(20), use_container_width=True, hide_index=True)

        if st.button(
            "📥 Import treated fish from CSV",
            type="primary",
            use_container_width=True,
            key="treated_fish_v11_import_btn",
        ):
            try:
                with eng().begin() as cx:
                    summary = _load_treated_fish_from_csv(df_csv, cx)

                st.success(
                    f"Import complete: "
                    f"rows processed={summary.get('n_rows', 0)}, "
                    f"distinct treatments touched={summary.get('n_treatments', 0)}, "
                    f"fish instance↔treatment links inserted={summary.get('n_instances_linked', 0)}."
                )

                rej = summary.get("rejected_rows")
                if isinstance(rej, pd.DataFrame) and not rej.empty:
                    st.warning(
                        f"{len(rej)} row(s) could not be imported. "
                        "See table below and optionally download them for fixing."
                    )
                    st.dataframe(rej, use_container_width=True, hide_index=True)

                    rej_csv = rej.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "⬇︎ Download rejected rows (CSV)",
                        data=rej_csv,
                        file_name="treated_fish_v11_rejected_rows.csv",
                        type="secondary",
                        mime="text/csv",
                    )

            except Exception as e:
                st.error(f"Import failed: {type(e).__name__}: {e}")
else:
    st.info("Upload a treated-fish CSV to begin the import.")