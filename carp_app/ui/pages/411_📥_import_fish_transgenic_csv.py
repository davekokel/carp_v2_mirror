# carp_app/ui/pages/411_📥_import_fish_v11_from_csv.py

from __future__ import annotations

import sys
import pathlib
from datetime import date
import inspect
import hashlib

import pandas as pd
import streamlit as st
from sqlalchemy import text
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
from carp_app.etl.fish_v11_shared import load_fish_from_csv as _load_fish_from_csv


# ───────── auth & page setup ─────────

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — 📥 Import fish (v11) from CSV",
    page_icon="📥",
    layout="wide",
)
st.title("📥 Import fish (v11) from CSV")

src = inspect.getsource(_load_fish_from_csv).encode("utf-8")
loader_hash = hashlib.sha256(src).hexdigest()[:12]
st.caption(f"loader_hash={loader_hash}")


def eng() -> Engine:
    return _engine()


with eng().connect() as conn:
    row = conn.execute(
        text("select current_user, current_database(), inet_server_addr();")
    ).first()

st.caption(f"DB debug → user={row[0]}, db={row[1]}, host={row[2]}")

# ───────── explainer ─────────

st.markdown(
    """
Use this page to import **fish lines • alleles • instances** from a CSV file.

### CSV contract (minimal change from fish.csv)

**Required columns:**

- `transgene_base_code` — construct base code (e.g. `pdqm063`, or legacy alias like `pDQM063`)
- `line_nickname` — nickname for the line (line-level)
- `allele_nickname` — allele nickname; importer will create-or-reuse by nickname (allele-level)
- `fish_nickname` — per-fish nickname (instance-level, optional but recommended)
- `instance_stage` — e.g. `P0`, `F1`, `juvenile`
- `birthday` — `YYYY-MM-DD`
- `genetic_background` — `bg_code` from `genetic_backgrounds`
- `notes` — optional free text

### Rules

- Rows are grouped by (`transgene_base_code`, `line_nickname`, `allele_nickname`).
- For each group, we:

  1. Normalize `transgene_base_code` (e.g. `pDQM005` → `pdqm-5`) and ensure it exists in `public.constructs`.
  2. Create-or-reuse an allele with that base code + nickname.
  3. Derive a genotype + fish_group for that allele set.
  4. Derive or reuse a line for (`genotype`, `line_nickname`).
  5. Create one fish instance per row (with auto-generated `fish_code` and a tank).

- `fish_code` is always auto-generated (`FSH-xxxxxxxx`).
- Any groups that cannot be imported (e.g. bad base code) are collected as **rejected rows** with an `_error` column.
"""
)

# ───────── template download ─────────

template_cols = [
    "transgene_base_code",
    "line_nickname",
    "allele_nickname",
    "fish_nickname",
    "instance_stage",
    "birthday",
    "genetic_background",
    "notes",
]

template_df = pd.DataFrame(
    [
        {
            "transgene_base_code": "pdqm063",
            "line_nickname": "skittlez 4 FP",
            "allele_nickname": "318",
            "fish_nickname": "founder A",
            "instance_stage": "P0",
            "birthday": date.today().isoformat(),
            "genetic_background": "casper",
            "notes": "example row",
        }
    ],
    columns=template_cols,
)

csv_bytes = template_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇︎ Download fish_v11 CSV template",
    data=csv_bytes,
    file_name="fish_v11_add_fish_template.csv",
    type="secondary",
    mime="text/csv",
)

# ───────── file upload ─────────

uploaded_file = st.file_uploader(
    "Upload fish_v11 CSV",
    type=["csv"],
    key="fish_v11_import_csv",
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
            "📥 Import fish from CSV",
            type="primary",
            use_container_width=True,
            key="fish_v11_import_btn",
        ):
            try:
                with eng().begin() as cx:
                    summary = _load_fish_from_csv(df_csv, cx)

                st.success(
                    f"Import complete: "
                    f"{summary['n_instances']} instance(s), "
                    f"{summary['n_tanks']} tank(s); "
                    f"lines created={summary['n_lines_created']}, "
                    f"lines reused={summary['n_lines_reused']}."
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
                        file_name="fish_v11_rejected_rows.csv",
                        type="secondary",
                        mime="text/csv",
                    )

            except Exception as e:
                st.error(f"Import failed: {type(e).__name__}: {e}")
else:
    st.info("Upload a CSV file to begin the import.")