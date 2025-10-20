from __future__ import annotations

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
import os, re, tempfile, requests
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# ── app libs ─────────────────────────────────────────────────────────────────
from carp_app.lib.db import get_engine as _create_engine
from carp_app.lib.queries import load_fish_overview_human
from carp_app.ui.lib.labels_components import build_tank_labels_pdf  # 2.4"×1.5" + QR

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="CARP — Overview Fish (Cloud Print)", page_icon="☁️", layout="wide")
st.title("☁️ Overview Fish — Cloud Print")

# ── engine cache ─────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _cached_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        raise RuntimeError("DB_URL not set")
    return _create_engine()

def _get_engine() -> Engine:
    return _cached_engine()

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _normalize_q(q_raw: str) -> str | None:
    q = (q_raw or "").strip()
    return q or None

def _open_membership_counts_for_codes(codes: list[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=["fish_code","n_living_tanks"])
    sql = text("""
      with wanted as (
        select id, fish_code
        from public.fish
        where fish_code = any(:codes)
      )
      select
        w.fish_code,
        count(*)::int as n_living_tanks
      from wanted w
      join public.fish_tank_memberships m
        on m.fish_id = w.id
      where coalesce(
              nullif(to_jsonb(m)->>'left_at','')::timestamptz,
              nullif(to_jsonb(m)->>'ended_at','')::timestamptz
            ) is null
      group by w.fish_code
    """)
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params={"codes": codes})

def _load_tanks_for_codes(codes: list[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=[
            "fish_code","tank_code","container_id","label","status","container_type",
            "location","created_at","activated_at","deactivated_at","last_seen_at"
        ])
    with _get_engine().begin() as cx:
        has_loc = pd.read_sql(
            text("""
              select 1
              from information_schema.columns
              where table_schema='public'
                and table_name='containers'
                and column_name='location'
              limit 1
            """),
            cx,
        ).shape[0] > 0
    base_sql = """
      select
        f.fish_code,
        c.tank_code,
        c.id::text             as container_id,
        coalesce(c.label,'')   as label,
        coalesce(c.status,'')  as status,
        c.container_type,
        {loc_expr}             as location,
        c.created_at,
        c.activated_at,
        c.deactivated_at,
        c.last_seen_at
      from public.fish f
      join public.fish_tank_memberships m
        on m.fish_id = f.id
      join public.containers c
        on c.id = m.container_id
      where f.fish_code = any(:codes)
        and coalesce(
              nullif(to_jsonb(m)->>'left_at','')::timestamptz,
              nullif(to_jsonb(m)->>'ended_at','')::timestamptz
            ) is null
      order by f.fish_code, c.created_at desc nulls last
    """
    loc_expr = "coalesce(c.location,'')" if has_loc else "''::text"
    sql = text(base_sql.format(loc_expr=loc_expr))
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params={"codes": codes})

def _view_exists(schema: str, view: str) -> bool:
    with _get_engine().begin() as cx:
        n = pd.read_sql(
            text("""
              select 1
              from information_schema.views
              where table_schema = :s and table_name = :v
              limit 1
            """),
            cx, params={"s": schema, "v": view}
        ).shape[0]
    return n > 0

def _fetch_enriched_for_containers(container_ids: list[str]) -> pd.DataFrame:
    """
    Enrichment for tank labels: resolves nickname, name, genotype, etc.
    Uses public.v_fish_label_fields if present; otherwise returns minimal fields.
    """
    if not container_ids:
        cols = [
            "container_id","tank_code","label","status","container_type","location",
            "created_at","activated_at","deactivated_at","last_seen_at",
            "fish_code","nickname","name","genotype","genetic_background","stage","dob"
        ]
        return pd.DataFrame(columns=cols)

    with _get_engine().begin() as cx:
        has_location = pd.read_sql(
            text("""
              select 1
              from information_schema.columns
              where table_schema='public'
                and table_name='containers'
                and column_name='location'
              limit 1
            """), cx
        ).shape[0] > 0

    loc_expr = "c.location::text" if has_location else "''::text"
    use_label_view = _view_exists("public", "v_fish_label_fields")

    if use_label_view:
        sql = text(f"""
          with picked as (select unnest(cast(:ids as uuid[])) as container_id),
          live as (
            select m.container_id, m.fish_id
            from public.fish_tank_memberships m
            where m.left_at is null
          )
          select
            c.id::text                   as container_id,
            c.tank_code::text            as tank_code,
            coalesce(c.label,'')         as label,
            coalesce(c.status,'')        as status,
            c.container_type::text       as container_type,
            {loc_expr}                   as location,
            c.created_at::timestamptz    as created_at,
            c.activated_at,
            c.deactivated_at,
            c.last_seen_at,
            f.fish_code::text            as fish_code,
            coalesce(v.nickname,'')      as nickname,
            coalesce(v.name,'')          as name,
            coalesce(v.genotype,'')      as genotype,
            coalesce(v.genetic_background,'') as genetic_background,
            coalesce(v.stage,'')         as stage,
            v.dob                        as dob
          from picked p
          join public.containers c on c.id = p.container_id
          left join live L on L.container_id = c.id
          left join public.fish f on f.id = L.fish_id
          left join public.v_fish_label_fields v on v.fish_code = f.fish_code
          order by c.created_at asc, c.tank_code asc
        """)
    else:
        sql = text(f"""
          with picked as (select unnest(cast(:ids as uuid[])) as container_id),
          live as (
            select m.container_id, m.fish_id
            from public.fish_tank_memberships m
            where m.left_at is null
          )
          select
            c.id::text                   as container_id,
            c.tank_code::text            as tank_code,
            coalesce(c.label,'')         as label,
            coalesce(c.status,'')        as status,
            c.container_type::text       as container_type,
            {loc_expr}                   as location,
            c.created_at::timestamptz    as created_at,
            c.activated_at,
            c.deactivated_at,
            c.last_seen_at,
            f.fish_code::text            as fish_code,
            ''::text                     as nickname,
            ''::text                     as name,
            ''::text                     as genotype,
            ''::text                     as genetic_background,
            ''::text                     as stage,
            null::date                   as dob
          from picked p
          join public.containers c on c.id = p.container_id
          left join live L on L.container_id = c.id
          left join public.fish f on f.id = L.fish_id
          order by c.created_at asc, c.tank_code asc
        """)
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params={"ids": container_ids})

# ─────────────────────────────────────────────────────────────────────────────
# Cloud relay printing
# ─────────────────────────────────────────────────────────────────────────────
def _mm_to_in(mm: float) -> float:
    return mm / 25.4

def pretty_media_inches(media_token: str) -> str:
    """
    Converts tokens like 'Custom.61x38mm' or 'iso_a4_210x297mm' → 2.4" × 1.5"
    If already inches (e.g., 'na_index-3x5_3x5in'), uses those.
    Falls back to the raw token if it doesn't recognize the pattern.
    """
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)x([0-9]+(?:\.[0-9]+)?)(mm|in)', media_token)
    if not m:
        return media_token
    w, h, unit = m.groups()
    w = float(w); h = float(h)
    if unit == "mm":
        w_in = _mm_to_in(w); h_in = _mm_to_in(h)
    else:
        w_in, h_in = w, h
    return f'{w_in:.1f}" × {h_in:.1f}"'

PRINT_RELAY_URL   = os.getenv("PRINT_RELAY_URL", "").strip()
PRINT_RELAY_TOKEN = os.getenv("PRINT_RELAY_TOKEN", "").strip()
PRINT_RELAY_QUEUE = os.getenv("PRINT_RELAY_QUEUE", "Brother_QL_1110NWB").strip()
PRINTER_MEDIA_DEFAULT = os.getenv("LABEL_MEDIA_NAME", "Custom.61x38mm").strip()  # sent to CUPS; help shows inches

def _send_to_relay(pdf_bytes: bytes, url: str, token: str, queue: str, media: str) -> tuple[bool, str]:
    if not pdf_bytes:
        return False, "No PDF data to print."
    if not (url and token and queue and media):
        return False, "Missing relay configuration."
    try:
        with tempfile.NamedTemporaryFile(prefix="labels_", suffix=".pdf", delete=True) as tmp:
            tmp.write(pdf_bytes)
            tmp.flush()
            with open(tmp.name, "rb") as f:
                files = {"pdf": ("labels.pdf", f, "application/pdf")}
                data  = {"token": token, "queue": queue, "media": media}
                r = requests.post(url.rstrip("/") + "/print", files=files, data=data, timeout=20)
        if r.status_code >= 400:
            return False, f"Relay error [{r.status_code}]: {r.text}"
        js = r.json()
        return True, js.get("lp_out", "submitted")
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

# ─────────────────────────────────────────────────────────────────────────────
# Page
# ─────────────────────────────────────────────────────────────────────────────
def main():
    # Filters
    with st.form("filters"):
        c1, c2 = st.columns([3,1])
        with c1:
            q_raw = st.text_input("Search fish (multi-term; quotes & -negation supported)", "")
        with c2:
            limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
        st.form_submit_button("Search")

    q = _normalize_q(q_raw)

    try:
        fish_rows = load_fish_overview_human(_get_engine(), q=q, stages=None, limit=limit)
    except Exception as e:
        st.error(f"Query error: {type(e).__name__}: {e}")
        with st.expander("Debug"):
            st.code(str(e))
        return

    if not fish_rows:
        st.info("No fish match your search.")
        return

    fish_df = pd.DataFrame(fish_rows)
    codes = fish_df["fish_code"].astype(str).tolist()
    counts_df = _open_membership_counts_for_codes(codes)
    fish_df = fish_df.merge(counts_df, on="fish_code", how="left")
    fish_df["n_living_tanks"] = fish_df["n_living_tanks"].fillna(0).astype(int)

    fish_cols = [c for c in [
        "fish_code","fish_name","fish_nickname","genetic_background",
        "allele_code","transgene","genotype_rollup",
        "n_living_tanks",
        "date_birth","created_at","created_by"
    ] if c in fish_df.columns]
    fish_view = fish_df[fish_cols].rename(columns={
        "fish_code":"Fish code",
        "fish_name":"Name",
        "fish_nickname":"Nickname",
        "genetic_background":"Background",
        "allele_code":"Allele code",
        "transgene":"Transgene",
        "genotype_rollup":"Genotype rollup",
        "n_living_tanks":"# living tanks",
        "date_birth":"Birth date",
        "created_at":"Created",
        "created_by":"Created by",
    }).copy()

    st.subheader("Fish (select to see tanks)")
    view = fish_view.copy()
    view.insert(0, "✓ Select", False)

    key_sig = "|".join(fish_df["fish_code"].astype(str).tolist())
    if st.session_state.get("_sft_sig_cloud") != key_sig:
        st.session_state["_sft_sig_cloud"] = key_sig
        st.session_state["_sft_table_cloud"] = view.copy()

    csa, csb, csc = st.columns([1,1,2])
    with csa:
        if st.button("Select all"):
            st.session_state["_sft_table_cloud"].loc[:, "✓ Select"] = True
    with csb:
        if st.button("Clear all"):
            st.session_state["_sft_table_cloud"].loc[:, "✓ Select"] = False
    with csc:
        st.caption(f"{len(fish_view)} fish")

    edited = st.data_editor(
        st.session_state["_sft_table_cloud"],
        use_container_width=True,
        hide_index=True,
        key="sft_editor_cloud",
    )
    st.session_state["_sft_table_cloud"] = edited.copy()

    selected_codes = edited.loc[edited["✓ Select"], "Fish code"].astype(str).tolist()

    # Tanks for selected fish
    st.subheader("Current tanks for selected fish")
    if not selected_codes:
        st.info("Select one or more fish above to see their current tanks.")
        return

    tanks_df = _load_tanks_for_codes(selected_codes)
    if tanks_df.empty:
        st.info("No active memberships / tanks for selected fish.")
        return

    tanks_view = tanks_df.rename(columns={
        "fish_code":"Fish code",
        "tank_code":"Tank code",
        "container_id":"Container ID",
        "label":"Label",
        "status":"Status",
        "container_type":"Type",
        "location":"Location",
        "created_at":"Created",
        "activated_at":"Activated",
        "deactivated_at":"Deactivated",
        "last_seen_at":"Last seen",
    }).copy()

    # Add print-selection column and grid
    tanks_view.insert(0, "✓ Print", False)

    cols = ["✓ Print","Fish code","Tank code","Label","Status","Type","Created","Activated","Deactivated","Last seen","Container ID"]
    if "Location" in tanks_view.columns:
        cols.insert(5, "Location")

    tanks_sig = "|".join(tanks_view["Container ID"].astype(str).tolist())
    if st.session_state.get("_sft_tanks_sig_cloud") != tanks_sig:
        st.session_state["_sft_tanks_sig_cloud"] = tanks_sig
        st.session_state["_sft_tanks_table_cloud"] = tanks_view.copy()

    ctp_a, ctp_b, _ = st.columns([1,1,6])
    with ctp_a:
        if st.button("Select all tanks"):
            st.session_state["_sft_tanks_table_cloud"].loc[:, "✓ Print"] = True
            st.rerun()
    with ctp_b:
        if st.button("Clear all tanks"):
            st.session_state["_sft_tanks_table_cloud"].loc[:, "✓ Print"] = False
            st.rerun()

    tanks_edited = st.data_editor(
        st.session_state["_sft_tanks_table_cloud"][cols],
        use_container_width=True,
        hide_index=True,
        key="sft_tanks_editor_cloud",
        column_config={"✓ Print": st.column_config.CheckboxColumn("✓ Print", default=False)},
    )
    st.session_state["_sft_tanks_table_cloud"] = tanks_edited.copy()

    # Print section
    st.subheader("Print labels")
    to_print = tanks_edited.loc[tanks_edited["✓ Print"] == True]
    st.caption(f"{len(to_print)} tank(s) selected for labels")

    pdf_bytes = b""
    if not to_print.empty:
        ids = to_print["Container ID"].astype(str).tolist()
        enriched = _fetch_enriched_for_containers(ids)
        if not enriched.empty:
            rows: list[dict] = []
            for _, r in enriched.iterrows():
                rows.append({
                    "tank_code": r.get("tank_code") or r.get("label"),
                    "label":     r.get("label"),
                    "fish_code": r.get("fish_code"),
                    "nickname":  r.get("nickname"),
                    "name":      r.get("name"),
                    "genotype":  r.get("genotype"),
                    "genetic_background": r.get("genetic_background"),
                    "stage":     r.get("stage"),
                    "dob":       r.get("dob"),
                })
            pdf_bytes = build_tank_labels_pdf(rows)

    left, right = st.columns([1,1])

    with left:
        st.download_button(
            "⬇️ Download PDF labels (2.4×1.5 • QR)",
            data=(pdf_bytes if pdf_bytes else b""),
            file_name=f"tank_labels_2_4x1_5_{pd.Timestamp.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
            disabled=(pdf_bytes == b""),
        )

    with right:
        with st.expander("🖨️ Cloud relay settings", expanded=(PRINT_RELAY_URL == "")):
            relay_url = st.text_input("Relay URL", value=PRINT_RELAY_URL, placeholder="https://your-relay.example.org/print")
            relay_token = st.text_input("Relay token", value=PRINT_RELAY_TOKEN, type="password", placeholder="••••••")
            queue = st.text_input("CUPS queue", value=PRINT_RELAY_QUEUE, placeholder="Brother_QL_1110NWB")
            media = st.text_input("Media token", value=PRINTER_MEDIA_DEFAULT, help=f'Inches: {pretty_media_inches(PRINTER_MEDIA_DEFAULT)}')

        can_send = bool(pdf_bytes) and bool(relay_url.strip()) and bool(relay_token.strip()) and bool(queue.strip()) and bool(media.strip())
        send = st.button("☁️ Send to Relay", type="secondary", use_container_width=True, disabled=not can_send)
        if send:
            ok, msg = _send_to_relay(pdf_bytes, relay_url.strip(), relay_token.strip(), queue.strip(), media.strip())
            if ok:
                st.success(f"Relayed to CUPS: {msg}")
            else:
                st.error(f"Relay failed: {msg}")

if __name__ == "__main__":
    main()