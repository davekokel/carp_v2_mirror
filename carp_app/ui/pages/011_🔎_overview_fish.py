from __future__ import annotations

# ── sys.path prime ───────────────────────────────────────────────────────────
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.lib.time import utc_now  # now this is safe

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
from carp_app.ui.lib.app_ctx import get_engine as _create_engine
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

LIVE_STATUSES = ("active", "new")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _normalize_q(q_raw: str) -> str | None:
    q = (q_raw or "").strip()
    return q or None

@st.cache_data(show_spinner=False)
def _pick_fish_view() -> str:
    with _get_engine().begin() as cx:
        df = pd.read_sql(
            text("""
                select table_name
                from information_schema.views
                where table_schema='public'
                  and table_name in ('v_fish_rich','v_fish')
            """),
            cx,
        )
    names = set(df["table_name"].tolist())
    return "public.v_fish_richrich" if "v_fish_rich" in names else "public.v_fish"

@st.cache_data(show_spinner=False)
def _view_cols(view: str) -> list[str]:
    schema, tbl = view.split(".")
    with _get_engine().begin() as cx:
        df = pd.read_sql(
            text("""
                select column_name
                from information_schema.columns
                where table_schema=:s and table_name=:t
                order by ordinal_position
            """),
            cx,
            params={"s": schema, "t": tbl},
        )
    return df["column_name"].tolist()

def _build_haystack(cols: list[str]) -> str:
    # include modern fields if they exist
    fields = ["fish_code", "fish_name", "fish_nickname",
              "genetic_background", "genotype_text"]
    parts = [f"coalesce({c},'')" for c in fields if c in cols]
    return " || ' ' || ".join(parts) if parts else "coalesce(fish_code,'')"

def _coerce_strings(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _load_fish_overview(q: str | None, limit: int) -> list[dict]:
    # explicit rich query: pretties + tank counts + dates
    sql = text("""
    WITH base AS (
      SELECT
        p.fish_uuid,
        p.fish_code,
        p.genetic_background,
        p.line_building_stage,
        p.genotype_text AS transgene_pretty
      FROM public.v_fish_richrich_derive_pretties p
    ),
    ages AS (
      SELECT f.fish_uuid, f.date_birth, f.created_at
      FROM public.fish f
    ),
    tank AS (
      SELECT fish_uuid, current_tanks
      FROM public.v_fish_richcurrent_tank_counts
    )
    SELECT
      b.fish_uuid,
      b.fish_code,
      b.genetic_background,
      b.line_building_stage,
      b.transgene_pretty,
      a.date_birth,
      a.created_at,
      COALESCE(t.current_tanks, 0) AS current_tanks
    FROM base b
    LEFT JOIN ages a USING (fish_uuid)
    LEFT JOIN tank t USING (fish_uuid)
    WHERE (:q IS NULL) OR (
      (b.fish_code ILIKE :q) OR
      (b.genetic_background ILIKE :q) OR
      (b.line_building_stage ILIKE :q) OR
      (b.transgene_pretty ILIKE :q)
    )
    ORDER BY a.created_at DESC NULLS LAST, b.fish_code
    LIMIT :lim
    """)
    params = {"q": (f"%{q}%" if q else None), "lim": int(limit)}
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=params)

    # display-friendly names
    df = _coerce_strings(df)
    df.rename(columns={
        "genetic_background": "Genetic background",
        "line_building_stage": "Line-building stage",
        "transgene_pretty": "Transgene (pretty)",
        "date_birth": "Birth date",
        "created_at": "Created time",
        "current_tanks": "Current tanks",
        "fish_code": "Fish code",
    }, inplace=True)

    # keep a consistent column order
    want = ["Fish code", "Genetic background", "Line-building stage",
            "Transgene (pretty)", "Birth date", "Created time", "Current tanks"]
    cols = [c for c in want if c in df.columns]
    return df[cols].to_dict(orient="records")

def _load_tanks_for_codes(codes: list[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=["fish_code","tank_code","status","created_at","container_id"])
    sql = text("""
      SELECT
        v.tank_uuid::text AS container_id,
        v.tank_code::text AS tank_code,
        v.status::text    AS status,
        v.fish_code::text AS fish_code,
        v.created_at::timestamptz AS created_at
      FROM public.v_tanks v
      WHERE v.fish_code = ANY(:codes)
      ORDER BY v.created_at ASC, v.tank_code ASC
    """)
    with _get_engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"codes": codes})
    return df

def _fetch_enriched_for_containers(container_ids: list[str]) -> pd.DataFrame:
    want_cols = [
        "container_id","label","status","fish_code",
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
        select
            v.tank_uuid::uuid         as tank_id,
            v.fish_code::text         as fish_code,
            v.tank_code::text         as tank_code,
            v.status::text            as status,
            v.created_at::timestamptz as created_at
        from public.v_tanks v
      ),
      geno as (
        select
          f.fish_code::text as fish_code,
          string_agg('Tg('||fta.transgene_base_code||')'||coalesce(ta.allele_name,''),
                     '; ' order by fta.transgene_base_code, coalesce(ta.allele_name,'')) as genotype
        from public.fish f
        left join public.fish_transgene_alleles fta on fta.id = f.primary_allele_id or fta.fish_uuid = f.fish_uuid
        left join public.transgene_alleles ta
               on ta.transgene_base_code = fta.transgene_base_code
              and ta.allele_number       = fta.allele_number
        group by f.fish_code
      )
      select
        p.container_id::text               as container_id,
        vt.tank_code                       as tank_code,
        vt.status                          as status,
        vt.fish_code                       as fish_code,
        coalesce(f.nickname,'')            as nickname,
        coalesce(f.name,'')                as name,
        coalesce(g.genotype,'')            as genotype,
        coalesce(f.genetic_background,'')  as genetic_background,
        coalesce(f.line_building_stage,'') as stage,
        (f.date_birth)::date               as dob
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

    df["label"] = df["tank_code"].fillna("")
    for c in ["label","fish_code","nickname","name","genotype","genetic_background","stage","status"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str)

    if "dob" in df.columns:
        try:
            df["dob"] = pd.to_datetime(df["dob"], errors="coerce").dt.date
        except Exception:
            df["dob"] = None

    return df[[c for c in want_cols if c in df.columns]]

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

    # Prefer rich columns; show what exists
    preferred = [
        "fish_code","fish_name","fish_nickname","genetic_background","line_building_stage",
        "transgene_base_code","allele_number","allele_code","allele_numbers","allele_codes",
        "transgene","genotype_rollup","n_living_tanks","active_tank_count",
        "birth_date","created_time","created_at","created_by"
    ]
    cols = [c for c in preferred if c in fish_df.columns]
    if "fish_code" in cols:
        cols = ["fish_code"] + [c for c in cols if c != "fish_code"]

    fish_view = fish_df[cols].rename(columns={
        "fish_code":"Fish code",
        "fish_name":"Fish name",
        "fish_nickname":"Fish nickname",
        "genetic_background":"Genetic background",
        "line_building_stage":"Line-building stage",
        "transgene_base_code":"Transgene base code",
        "allele_number":"Allele number",
        "allele_code":"Allele code",
        "allele_numbers":"Allele numbers",
        "allele_codes":"Allele codes",
        "transgene":"Transgene (pretty)",
        "genotype_rollup":"Genotype rollup",
        "n_living_tanks":"# living tanks",
        "active_tank_count":"Active tanks",
        "birth_date":"Birth date",
        "created_time":"Created time",
        "created_at":"Created at",
        "created_by":"Created by"
    })

    st.subheader("Fish (select to see tanks and print labels)")
    view = fish_view.copy()
    view.insert(0, "✓ Select", False)

    key_sig = "|".join(fish_df.get("fish_code", pd.Series(dtype=str)).astype(str).tolist())
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
        width="stretch",
        hide_index=True,
        key="sft_editor",
    )
    st.session_state["_sft_table"] = edited.copy()
    selected_codes = edited.loc[edited["✓ Select"], "Fish code"].astype(str).tolist() if "Fish code" in edited.columns else []

    st.subheader("Tanks for selected fish")
    if not selected_codes:
        st.info("Select one or more fish above to see their tanks.")
    else:
        tanks_details = _load_tanks_for_codes(selected_codes)
        if tanks_details.empty:
            st.info("No tanks for the selected fish.")
        else:
            tcols = [c for c in ["fish_code","tank_code","status","created_at","container_id"] if c in tanks_details.columns]
            st.dataframe(tanks_details[tcols], width="stretch", hide_index=True)

    st.subheader("Print labels")
    if not selected_codes:
        st.info("Select fish to load their tanks for printing.")
        return

    tanks_df = _load_tanks_for_codes(selected_codes)
    if tanks_df.empty:
        st.info("No tanks found for selected fish.")
        return

    tanks_df = tanks_df.copy()
    tanks_df.insert(0, "✓ Print", False)

    cols_print = [c for c in ["✓ Print","fish_code","tank_code","status","created_at","container_id"] if c in tanks_df.columns]
    tanks_edit = st.data_editor(
        tanks_df[cols_print],
        width="stretch",
        hide_index=True,
        key="sft_tanks_editor",
        column_config={
            "✓ Print":    st.column_config.CheckboxColumn("✓ Print", default=False),
            "created_at": st.column_config.DatetimeColumn("created_at"),
        },
    )

    to_print = tanks_edit.loc[tanks_edit["✓ Print"] == True] if "✓ Print" in tanks_edit.columns else pd.DataFrame()
    st.caption(f"{len(to_print)} tank(s) selected for labels")

    pdf_bytes = b""
    if not to_print.empty:
        ids = to_print["container_id"].astype(str).tolist() if "container_id" in to_print.columns else []
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
                            d2 = pd.to_datetime(dob, errors="coerce"); dob = None if pd.isna(d2) else d2.date()
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
            width="stretch",
            disabled=(pdf_bytes == b""),
        )
    with right:
        def _detect_default_queue() -> str:
            try:
                p = subprocess.run(["lpstat", "-d"], capture_output=True, text=True, check=False)
                line = p.stdout.strip()
                if ":" in line:
                    return line.split(":", 1)[1].strip()
            except Exception:
                return ""
            return ""

        PRINTER_QUEUE_DEFAULT = os.getenv("LABEL_PRINTER_QUEUE", "").strip() or _detect_default_queue()
        PRINTER_MEDIA_DEFAULT = os.getenv("LABEL_MEDIA_NAME", "Custom.61x38mm")
        with st.expander("Printer settings", expanded=(PRINTER_QUEUE_DEFAULT == "")):
            queue = st.text_input("CUPS queue", value=PRINTER_QUEUE_DEFAULT, placeholder="Brother_QL_1110NWB")
            media = st.text_input("Media name", value=PRINTER_MEDIA_DEFAULT, help="e.g., Custom.61x38mm for 2.4×1.5 stock")
        can_print = bool(pdf_bytes) and bool(queue.strip())
        if st.button("🖨️ Send to Brother", type="secondary", width="stretch", disabled=not can_print):
            ok, msg = _print_pdf_to_cups(pdf_bytes, queue.strip(), media.strip())
            if ok:
                st.success(f"Sent to printer '{queue}'. {msg}")
            else:
                st.error(f"Print failed: {msg}")

if __name__ == "__main__":
    main()