from lib.page_bootstrap import secure_page; secure_page()

import os, subprocess, tempfile, re, streamlit as st
from pathlib import Path
from lib.authz import require_app_access, logout_button
import hashlib, time

st.set_page_config(page_title="Import (wide CSV)", layout="wide")
require_app_access("🔐 CARP — Private")
logout_button("sidebar", key="logout_btn_import")

st.title("Import (wide CSV)")
st.caption("Uploads a normalized wide CSV and calls the loader script.")

uploaded = st.file_uploader("Choose a CSV", type=["csv"])
dry_run = st.checkbox("Dry run (no DB writes)", value=False)  # placeholder

# --- Template download -------------------------------------------------------
import io, csv

def _make_template_csv() -> bytes:
    headers = [
        "fish_name",
        "nickname",
        "birth_date",           # accepts YYYY-MM-DD or MM/DD/YYYY
        "background_strain",
        "line_building_stage",
        "description",
        "notes",
        "transgene_base_code",
        "legacy_allele_number", # comma/semicolon ok (e.g., "301; 302")
        "zygosity",
        "created_by",
    ]
    example_rows = [
        {
            "fish_name": "mem-tdmSG-8m",
            "nickname": "membrane-tandem-mStayGold",
            "birth_date": "2024-08-16",
            "background_strain": "casper",
            "line_building_stage": "founder",
            "description": "multiple alleles, male founder #8",
            "notes": "import test",
            "transgene_base_code": "pDQM005",
            "legacy_allele_number": "301",
            "zygosity": "heterozygous",
            "created_by": "dqm",
        },
        {
            "fish_name": "mem-tdmSG-11m",
            "nickname": "membrane-tandem-mStayGold",
            "birth_date": "2024-08-16",
            "background_strain": "casper",
            "line_building_stage": "founder",
            "description": "another example row",
            "notes": "",
            "transgene_base_code": "pDQM005",
            "legacy_allele_number": "302",
            "zygosity": "heterozygous",
            "created_by": "dqm",
        },
    ]

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=headers, lineterminator="\n")
    w.writeheader()
    for r in example_rows:
        w.writerow(r)
    return buf.getvalue().encode("utf-8")

with st.expander("Download a template CSV", expanded=False):
    st.download_button(
        "Download example template",
        data=_make_template_csv(),
        file_name="fish_wide_template.csv",
        mime="text/csv",
    )
# ---------------------------------------------------------------------------

if uploaded is not None:
    # stage upload to a temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(uploaded.getvalue())
        tmp_path = tmp.name
    st.write(f"Staged: `{tmp_path}`")

    # Compute paths WITHOUT repo_root
    SCRIPT_PATH = str(Path(__file__).resolve().parents[3] / "scripts" / "seedkit_load_wide.py")
    PY = str(Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python")
    from lib.config import DB_URL
    DB = DB_URL or "postgresql://postgres:postgres@127.0.0.1:54322/postgres?sslmode=disable"

    # Diagnostics
    sp = Path(SCRIPT_PATH)
    st.caption(f"Loader path: {SCRIPT_PATH} (exists={sp.exists()})")
    try:
        mtime = sp.stat().st_mtime
        sha1 = hashlib.sha1(sp.read_bytes()).hexdigest()
        st.caption(f"mtime: {time.ctime(mtime)}  •  sha1: {sha1[:12]}")
    except Exception as _e:
        st.caption(f"(could not stat loader: {_e})")

    # Build and show command
    cmd = [PY, "-u", SCRIPT_PATH, "--db", DB, "--csv", tmp_path]
    if dry_run:
        cmd += ["--dry-run"]
    st.code(" ".join(cmd), language="bash")

    # Interpreter diagnostic & fallback
    st.caption(f"Python interpreter: {PY} (exists={Path(PY).exists()})")
    if not Path(PY).exists():
        PY = "python3"
        cmd[0] = PY
        st.caption(f"Falling back to: {PY}")

    # Run
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        out = e.output
        st.error("Import failed")
        st.code(out)
    else:
        st.success("Import finished")
        st.code(out)

    # Parse the loader’s summary line and surface a friendlier message
    m = re.search(
        r'Upserted\s+(\d+)\s+fish;\s+linked\s+(\d+)/(\d+)\s+new allele rows(?:;\s+(\d+)\s+already existed)?\.',
        out,
    )
    if m:
        upserted, linked, attempted, dupes = m.group(1), m.group(2), m.group(3), m.group(4) or "0"
        if int(linked) > 0:
            st.success(
                f"✅ Imported: {upserted} fish; linked {linked}/{attempted} allele rows "
                f"({dupes} duplicates skipped)."
            )
        else:
            st.info(
                f"ℹ️ No new links to add ({dupes} duplicates skipped). "
                f"Fish upserted: {upserted}."
            )
    else:
        st.info("ℹ️ Import ran, but I didn’t find the summary line. See log above.")
