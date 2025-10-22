from __future__ import annotations
from carp_app.ui.lib.app_ctx import get_engine as _shared_get_engine
from carp_app.lib.time import utc_now

# ── sys.path prime ───────────────────────────────────────────────────────────
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── auth gates ───────────────────────────────────────────────────────────────
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

# ── std/3p ───────────────────────────────────────────────────────────────────
import os, tempfile, subprocess
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ── app libs ─────────────────────────────────────────────────────────────────
from carp_app.lib.db import get_engine as _create_engine
from carp_app.ui.lib.labels_components import build_tank_labels_pdf  # 2.4"×1.5" + QR

@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _get_engine() -> Engine:
    return _cached_engine()

st.set_page_config(page_title="CARP — Search Fish → Tanks", page_icon="🔎", layout="wide")

LIVE_STATUSES = ("active", "new_tank")  # used in rollups

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _normalize_q(q_raw: str) -> str | None:
    q = (q_raw or "").strip()
    return q or None

def _load_fish_overview(q: str | None, limit: int) -> list[dict]:
    """
    One row per fish with:
      fish_code, fish_name, fish_nickname, genetic_background,
      transgene_base_code/allele*/pretty (aggregated), genotype_rollup (deterministic),
      n_living_tanks (active + new_tank),
      birth_date, created_time, created_by.
    Tank-centric note: joins to v_tanks by fish_code (no fish_id).
    """
    where_terms = []
    params = {"lim": int(limit), "ql": f"%{q or ''}%"}
    if q:
        where_terms += [
            "coalesce(f.fish_code,'') ilike :ql",
            "coalesce(f.name,'') ilike :ql",
            "coalesce(f.nickname,'') ilike :ql",
            "coalesce(f.genetic_background,'') ilike :ql",
        ]
    where_sql = ("where " + " or ".join(where_terms)) if where_terms else ""

    sql = text(f"""
      with alleles as (
        select
          f.fish_code,
          fta.transgene_base_code,
          fta.allele_number,
          ta.allele_name,
          ta.allele_nickname,
          ('Tg('||fta.transgene_base_code||')'||coalesce(ta.allele_name,''))::text as transgene_pretty
        from public.fish f
        left join public.fish_transgene_alleles fta on fta.fish_id = f.id
        left join public.transgene_alleles ta
          on ta.transgene_base_code = fta.transgene_base_code
         and ta.allele_number       = fta.allele_number
      ),
      alleles_agg as (
        select
          a.fish_code,
          string_agg(distinct coalesce(a.transgene_base_code,''), '; ' order by coalesce(a.transgene_base_code,'')) as transgene_base_code,
          string_agg(distinct coalesce(a.allele_number::text,''), '; ' order by coalesce(a.allele_number::text,'')) as allele_number,
          string_agg(distinct coalesce(a.allele_name,''), '; ' order by coalesce(a.allele_name,'')) as allele_name,
          string_agg(distinct coalesce(a.allele_nickname,''), '; ' order by coalesce(a.allele_nickname,'')) as allele_nickname,
          string_agg(distinct coalesce(a.transgene_pretty,''), '; ' order by coalesce(a.transgene_pretty,'')) as transgene_pretty,
          -- deterministic genotype rollup
          string_agg(distinct coalesce(a.transgene_pretty,''), '; ' order by coalesce(a.transgene_pretty,'')) as genotype_rollup_calc
        from alleles a
        group by a.fish_code
      ),
      live as (
        select f.fish_code, v.n_living_tanks
        from public.v_fish_living_tank_counts v
        join public.fish f on f.id = v.fish_id
      ),
      base as (
        select
          f.fish_code,
          coalesce(f.name,'')               as fish_name,
          coalesce(f.nickname,'')           as fish_nickname,
          coalesce(f.genetic_background,'') as genetic_background,
          coalesce(f.line_building_stage,'') as line_building_stage,  -- column not in your minimal fish: keep API stable
          f.date_birth                      as birth_date,
          f.created_at                      as created_time,
          coalesce(f.created_by,'')         as created_by
        from public.fish f
        {where_sql}
        order by f.created_at desc nulls last, f.fish_code
        limit :lim
      )
      select
        b.fish_code,
        b.fish_name,
        b.fish_nickname,
        b.genetic_background,
        b.line_building_stage,
        coalesce(aa.transgene_base_code,'') as transgene_base_code,
        coalesce(aa.allele_number,'')       as allele_number,
        coalesce(aa.allele_name,'')         as allele_name,
        coalesce(aa.allele_nickname,'')     as allele_nickname,
        coalesce(aa.transgene_pretty,'')    as transgene_pretty,
        coalesce(aa.genotype_rollup_calc,'') as genotype_rollup,
        coalesce(l.n_living_tanks,0)         as n_living_tanks,
        b.birth_date,
        b.created_time,
        b.created_by
      from base b
      left join alleles_agg aa using (fish_code)
      left join live       l  using (fish_code)
      order by b.created_time desc nulls last, b.fish_code
    """)
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params=params).to_dict(orient="records")

def _load_tanks_for_codes(codes: list[str]) -> pd.DataFrame:
    """Tank details for selected fish (for drilldown + printing)."""
    if not codes:
        return pd.DataFrame(columns=["fish_code","tank_code","container_id","status","created_at"])
    sql = text("""
      select
        vt.fish_code,
        vt.tank_code,
        vt.tank_id::text             as container_id,
        vt.status::text              as status,
        vt.tank_created_at           as created_at
      from public.v_tanks vt
      where vt.fish_code = any(:codes)
      order by vt.fish_code, vt.tank_created_at desc nulls last
    """)
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params={"codes": list({c for c in codes if c})})

def _fetch_enriched_for_containers(container_ids: list[str]) -> pd.DataFrame:
    """
    Enrichment for label printing (no membership dependency).
    Produces fields expected by build_tank_labels_pdf():
      tank_code, label, fish_code, nickname, name, genotype, genetic_background, stage, dob
    """
    want_cols = [
        "container_id","tank_code","label","status","fish_code",
        "nickname","name","genotype","genetic_background","stage","dob"
    ]
    if not container_ids:
        return pd.DataFrame(columns=want_cols)

    ids = [x for x in container_ids if x]
    if not ids:
        return pd.DataFrame(columns=want_cols)

    sql = text("""
      with picked as (
        select unnest(cast(:ids as uuid[])) as container_id
      ),
      vt as (
        -- authoritative tank + fish_code (tank-centric)
        select
          v.tank_id::uuid                 as tank_id,
          v.fish_code::text               as fish_code,
          v.tank_code::text               as tank_code,
          v.status::text                  as status,
          v.tank_created_at::timestamptz  as created_at
        from public.v_tanks v
      ),
      geno as (
        -- genotype pretty rollup per fish_code
        select
          f.fish_code::text as fish_code,
          string_agg('Tg('||fta.transgene_base_code||')'||coalesce(ta.allele_name,''),
                     '; ' order by fta.transgene_base_code, coalesce(ta.allele_name,'')) as genotype
        from public.fish f
        left join public.fish_transgene_alleles fta on fta.fish_id = f.id
        left join public.transgene_alleles ta
               on ta.transgene_base_code = fta.transgene_base_code
              and ta.allele_number       = fta.allele_number
        group by f.fish_code
      )
      select
        p.container_id::text                 as container_id,
        vt.tank_code                         as tank_code,
        vt.status                            as status,
        vt.fish_code                         as fish_code,
        coalesce(f.nickname,'')              as nickname,
        coalesce(f.name,'')                  as name,
        coalesce(g.genotype,'')              as genotype,
        coalesce(f.genetic_background,'')    as genetic_background,
        null::text                           as stage,   -- stage not in minimal fish (keep API shape)
        (f.date_birth)::date                 as dob
      from picked p
      join vt on vt.tank_id = p.container_id
      left join public.fish f on f.fish_code = vt.fish_code
      left join geno g on g.fish_code = vt.fish_code
      order by vt.created_at asc, vt.tank_code asc
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"ids": ids})

    if df.empty:
        return df

    # Default printable label text
    df["label"] = df["tank_code"].fillna("")

    # Hygiene: strings only; dob must be date or None
    str_cols = ["tank_code","label","fish_code","nickname","name","genotype","genetic_background","stage","status"]
    for c in str_cols:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str)

    if "dob" in df.columns:
        try:
            df["dob"] = pd.to_datetime(df["dob"], errors="coerce").dt.date
        except Exception:
            df["dob"] = None

    return df[[c for c in want_cols if c in df.columns]]

# Printer helpers
def _detect_default_queue() -> str:
    try:
        p = subprocess.run(["lpstat", "-d"], capture_output=True, text=True, check=False)
        line = p.stdout.strip()
        if ":" in line:
            return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return ""

PRINTER_QUEUE_DEFAULT = os.getenv("LABEL_PRINTER_QUEUE", "").strip() or _detect_default_queue()
PRINTER_MEDIA_DEFAULT = os.getenv("LABEL_MEDIA_NAME", "Custom.61x38mm")

def _print_pdf_to_cups(pdf_bytes: bytes, queue: str, media: str) -> tuple[bool, str]:
    if not pdf_bytes:
        return False, "No PDF data to print."
    if not queue:
        return False, "CUPS queue is empty."
    try:
        with tempfile.NamedTemporaryFile(prefix="labels_", suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp.flush()
            cmd = ["lp", "-d", queue, "-o", f"media={media}", "-o", "fit-to-page", tmp.name]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        ok = (proc.returncode == 0)
        msg = proc.stdout.strip() or proc.stderr.strip() or ("Printed to " + queue if ok else "Unknown print error")
        return ok, msg
    except FileNotFoundError:
        return False, "`lp` not found. Install CUPS or set up a print proxy."
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

# ─────────────────────────────────────────────────────────────────────────────
# Page
# ─────────────────────────────────────────────────────────────────────────────
def main():
    st.title("🔎 Search Fish → Tanks")

    with st.form("filters"):
        c1, c2 = st.columns([3,1])
        with c1:
            q_raw = st.text_input("Search fish (multi-term; quotes & -negation supported)", "")
        with c2:
            limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
        st.form_submit_button("Search")

    q = _normalize_q(q_raw)

    # Load one row per fish with your requested fields
    try:
        fish_rows = _load_fish_overview(q=q, limit=limit)
    except Exception as e:
        st.error(f"Query error: {type(e).__name__}: {e}")
        with st.expander("Debug"):
            st.code(str(e))
        return
    if not fish_rows:
        st.info("No fish match your search.")
        return

    fish_df = pd.DataFrame(fish_rows)

    # Main grid columns
    fish_cols = [c for c in [
        "fish_code",
        "fish_name",
        "fish_nickname",
        "genetic_background",
        "line_building_stage",
        "transgene_base_code",
        "allele_number",
        "allele_name",
        "allele_nickname",
        "transgene_pretty",
        "genotype_rollup",
        "n_living_tanks",
        "birth_date",
        "created_time",
        "created_by",
    ] if c in fish_df.columns]
    fish_view = fish_df[fish_cols].rename(columns={
        "fish_code":"Fish code",
        "fish_name":"Fish name",
        "fish_nickname":"Fish nickname",
        "genetic_background":"Genetic background",
        "line_building_stage":"Line-building stage",
        "transgene_base_code":"Transgene base code",
        "allele_number":"Allele number",
        "allele_name":"Allele name",
        "allele_nickname":"Allele nickname",
        "transgene_pretty":"Transgene pretty",
        "genotype_rollup":"Genotype rollup",
        "n_living_tanks":"# living tanks",
        "birth_date":"Birth date",
        "created_time":"Created time",
        "created_by":"Created by",
    }).copy()

    st.subheader("Fish (select to see tanks and print labels)")
    view = fish_view.copy()
    view.insert(0, "✓ Select", False)

    key_sig = "|".join(fish_df["fish_code"].astype(str).tolist())
    if st.session_state.get("_sft_sig") != key_sig:
        st.session_state["_sft_sig"] = key_sig
        st.session_state["_sft_table"] = view.copy()

    csa, csb, csc = st.columns([1,1,2])
    with csa:
        if st.button("Select all"):
            st.session_state["_sft_table"].loc[:, "✓ Select"] = True
    with csb:
        if st.button("Clear all"):
            st.session_state["_sft_table"].loc[:, "✓ Select"] = False
    with csc:
        st.caption(f"{len(fish_view)} fish")

    edited = st.data_editor(
        st.session_state["_sft_table"],
        use_container_width=True,
        hide_index=True,
        key="sft_editor",
    )
    st.session_state["_sft_table"] = edited.copy()
    selected_codes = edited.loc[edited["✓ Select"], "Fish code"].astype(str).tolist()

    # Tanks for selected fish
    st.subheader("Tanks for selected fish (tank_code, tank_status)")
    if not selected_codes:
        st.info("Select one or more fish above to see their tanks.")
    else:
        tanks_details = _load_tanks_for_codes(selected_codes)
        if tanks_details.empty:
            st.info("No tanks for the selected fish.")
        else:
            st.dataframe(
                tanks_details[["fish_code","tank_code","status","created_at"]],
                use_container_width=True,
                hide_index=True,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Printing labels
    # ─────────────────────────────────────────────────────────────────────────
    st.subheader("Print labels")
    if not selected_codes:
        st.info("Select fish to load their tanks for printing.")
        return

    tanks_df = _load_tanks_for_codes(selected_codes)
    if tanks_df.empty:
        st.info("No tanks found for selected fish.")
        return

    # Add selection column
    tanks_df = tanks_df.copy()
    tanks_df.insert(0, "✓ Print", False)

    cols = ["✓ Print","fish_code","tank_code","status","created_at","container_id"]
    tanks_edit = st.data_editor(
        tanks_df[cols],
        use_container_width=True,
        hide_index=True,
        key="sft_tanks_editor",
        column_config={
            "✓ Print":    st.column_config.CheckboxColumn("✓ Print", default=False),
            "created_at": st.column_config.DatetimeColumn("created_at"),
        },
    )

    to_print = tanks_edit.loc[tanks_edit["✓ Print"] == True]
    st.caption(f"{len(to_print)} tank(s) selected for labels")

    # Build the labels PDF (enrichment preserved; fish_code-join)
    pdf_bytes = b""
    if not to_print.empty:
        ids = to_print["container_id"].astype(str).tolist()
        enriched = _fetch_enriched_for_containers(ids)
        if not enriched.empty:
            rows: list[dict] = []
            for _, r in enriched.iterrows():
                dob = r.get("dob", None)
                if dob is not None:
                    try:
                        if pd.isna(dob):
                            dob = None
                        elif isinstance(dob, pd.Timestamp):
                            dob = dob.date()
                        elif isinstance(dob, str) and dob.strip():
                            dob_parsed = pd.to_datetime(dob, errors="coerce")
                            dob = None if pd.isna(dob_parsed) else dob_parsed.date()
                        elif hasattr(dob, "strftime") and hasattr(dob, "year"):
                            dob = getattr(dob, "date", lambda: dob)()
                        else:
                            dob = None
                    except Exception:
                        dob = None

                rows.append({
                    "tank_code":            r.get("tank_code") or r.get("label"),
                    "label":                r.get("label") or r.get("tank_code"),
                    "fish_code":            (r.get("fish_code") or "").strip(),
                    "nickname":             (r.get("nickname") or "").strip(),
                    "name":                 (r.get("name") or "").strip(),
                    "genotype":             (r.get("genotype") or "").strip(),
                    "genetic_background":   (r.get("genetic_background") or "").strip(),
                    "stage":                (r.get("stage") or "").strip(),
                    "dob":                  dob,
                })

            pdf_bytes = build_tank_labels_pdf(rows)

    left, right = st.columns([1,1])
    with left:
        st.download_button(
            "⬇️ Download PDF labels (2.4×1.5 • QR)",
            data=(pdf_bytes if pdf_bytes else b""),
            file_name=f"tank_labels_2_4x1_5_{utc_now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
            disabled=(pdf_bytes == b""),
        )
    with right:
        # CUPS printing
        def _detect_default_queue() -> str:
            try:
                p = subprocess.run(["lpstat", "-d"], capture_output=True, text=True, check=False)
                line = p.stdout.strip()
                if ":" in line:
                    return line.split(":", 1)[1].strip()
            except Exception:
                pass
            return ""
        PRINTER_QUEUE_DEFAULT = os.getenv("LABEL_PRINTER_QUEUE", "").strip() or _detect_default_queue()
        PRINTER_MEDIA_DEFAULT = os.getenv("LABEL_MEDIA_NAME", "Custom.61x38mm")
        with st.expander("Printer settings", expanded=(PRINTER_QUEUE_DEFAULT == "")):
            queue = st.text_input("CUPS queue", value=PRINTER_QUEUE_DEFAULT, placeholder="Brother_QL_1110NWB")
            media = st.text_input("Media name", value=PRINTER_MEDIA_DEFAULT, help="e.g., Custom.61x38mm for 2.4×1.5 stock")
        can_print = bool(pdf_bytes) and bool(queue.strip())
        if st.button("🖨️ Send to Brother", type="secondary", use_container_width=True, disabled=not can_print):
            ok, msg = _print_pdf_to_cups(pdf_bytes, queue.strip(), media.strip())
            if ok:
                st.success(f"Sent to printer '{queue}'. {msg}")
            else:
                st.error(f"Print failed: {msg}")

if __name__ == "__main__":
    main()
