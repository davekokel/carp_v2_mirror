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
from carp_app.etl.constructs_v10_shared import load_constructs_from_df


sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 📥 Import constructs from CSV",
    page_icon="📥",
    layout="wide",
)
st.title("📥 Import constructs from CSV")


def eng() -> Engine:
    return _engine()


st.markdown(
    """
Use this page to import **constructs / plasmids** from a CSV file.

It mirrors the `constructs_plasmid.csv` used by
`scripts/v10_load_constructs_from_csv.py`.

### Expected CSV columns

These should match the headers in `constructs_plasmid.csv`:

- `plasmid_code` — e.g. `pDQM155`
- `plasmid_nickname` — short name
- `resistance` — e.g. `Amp`
- `plasmid_notes` — free text
- `used_for_injection_plasmid` — truthy flag
- `used_for_injection_rna` — truthy flag
- `used_for_injection_crispr` — truthy flag

The shared loader will normalize construct codes, upsert into
`public.constructs`, and return a summary.
"""
)

template_cols = [
    "plasmid_code",
    "plasmid_nickname",
    "resistance",
    "plasmid_notes",
    "used_for_injection_plasmid",
    "used_for_injection_rna",
    "used_for_injection_crispr",
]

template_df = pd.DataFrame(
    [
        {
            "plasmid_code": "pDQM155",
            "plasmid_nickname": "ef1a:tdmScarlet3S2",
            "resistance": "Amp",
            "plasmid_notes": "example row",
            "used_for_injection_plasmid": "true",
            "used_for_injection_rna": "",
            "used_for_injection_crispr": "",
        }
    ],
    columns=template_cols,
)

csv_bytes = template_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇︎ Download constructs CSV template",
    data=csv_bytes,
    file_name="constructs_template.csv",
    type="secondary",
    mime="text/csv",
)

uploaded_file = st.file_uploader(
    "Upload constructs CSV",
    type=["csv"],
    key="constructs_import_csv",
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
            "📥 Import constructs from CSV",
            type="primary",
            use_container_width=True,
            key="constructs_import_btn",
        ):
            try:
                with eng().begin() as cx:
                    summary = load_constructs_from_df(df_csv, cx)

                st.success(
                    f"Import complete: {summary['n_base_rows']} base row(s) processed "
                    f"from {summary['n_csv_rows']} CSV row(s); "
                    f"{summary['n_upserted']} upserted."
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
                        file_name="constructs_rejected_rows.csv",
                        type="secondary",
                        mime="text/csv",
                    )

            except Exception as e:
                st.error(f"Import failed: {type(e).__name__}: {e}")
else:
    st.info("Upload a constructs CSV file to begin the import.")
