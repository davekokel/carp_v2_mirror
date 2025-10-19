from __future__ import annotations

import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

import os, tempfile, subprocess
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine
from carp_app.lib.db import get_engine as _create_engine
from carp_app.ui.lib.labels_components import build_tank_labels_pdf

@st.cache_resource(show_spinner=False)
def _cached_engine(url: str) -> Engine:
    return _create_engine()

def _get_engine() -> Engine:
    url = os.getenv("DB_URL", "")
    if not url:
        st.error("DB_URL not set"); st.stop()
    return _cached_engine(url)

st.set_page_config(page_title="CARP — Search Fish → Tanks", page_icon="🔎", layout="wide")

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
            cmd = ["lp", "-o", f"media={media}", "-o", "fit-to-page", "-d", queue, tmp.name]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        ok = (proc.returncode == 0)
        msg = proc.stdout.strip() or proc.stderr.strip() or ("Printed to " + queue)
        return ok, msg
    except FileNotFoundError:
        return False, "`lp` not found. Install CUPS or set up a print proxy."
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def _view_exists(schema: str, view: str) -> bool:
    with _get_engine().begin() as cx:
        n = pd.read_sql(
            text("select 1 from information_schema.views where table_schema=:s and table_name=:v limit 1"),
            cx, params={"s": schema, "v": view}
        ).shape[0]
    return n > 0

def _search_overview_all(q: str | None, limit: int) -> pd.DataFrame:
    base_sql = """
      select *
      from public.v_fish_overview_all
      {where}
      order by created_at desc nulls last, fish_code
      limit :lim
    """
    params = {"lim": int(limit)}
    if q and q.strip():
        qq = f"%{q.strip()}%"
        where = """
          where fish_code ilike :qq
             or name ilike :qq
             or nickname ilike :qq
             or genetic_background ilike :qq
             or genotype ilike :qq
             or transgene_base_code ilike :qq
             or allele_nickname ilike :qq
        """
        params["qq"] = qq
    else:
        where = ""
    with _get_engine().begin() as cx:
        return pd.read_sql(text(base_sql.format(where=where)), cx, params=params)

def _load_tanks_for_codes(codes: list[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=[
            "fish_code","tank_code","container_id","label","status","container_type",
            "location","created_at","activated_at","deactivated_at","last_seen_at"
        ])
    with _get_engine().begin() as cx:
        has_loc = pd.read_sql(
            text("select 1 from information_schema.columns where table_schema='public' and table_name='containers' and column_name='location' limit 1"), cx
        ).shape[0] > 0
    loc_expr = "coalesce(c.location,'')" if has_loc else "''::text"
    sql = text(f"""
      select
        f.fish_code,
        c.tank_code,
        c.id::text as container_id,
        coalesce(c.label,'') as label,
        coalesce(c.status,'') as status,
        c.container_type,
        {loc_expr} as location,
        c.created_at,
        c.activated_at,
        c.deactivated_at,
        c.last_seen_at
      from public.fish f
      join public.fish_tank_memberships m on m.fish_id = f.id
      join public.containers c on c.id = m.container_id
      where f.fish_code = any(:codes)
        and coalesce(
              nullif(to_jsonb(m)->>'left_at','')::timestamptz,
              nullif(to_jsonb(m)->>'ended_at','')::timestamptz
            ) is null
      order by f.fish_code, c.created_at desc nulls last
    """)
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params={"codes": codes})

def _fetch_enriched_for_containers(container_ids: list[str]) -> pd.DataFrame:
    if not container_ids:
        return pd.DataFrame(columns=[
            "container_id","tank_code","label","status","container_type","location",
            "created_at","activated_at","deactivated_at","last_seen_at",
            "fish_code","nickname","name","genotype","genetic_background","stage","dob"
        ])
    with _get_engine().begin() as cx:
        has_location = pd.read_sql(
            text("select 1 from information_schema.columns where table_schema='public' and table_name='containers' and column_name='location' limit 1"), cx
        ).shape[0] > 0
        use_label_view = _view_exists("public", "v_fish_label_fields")
    loc_expr = "c.location::text" if has_location else "''::text"
    if use_label_view:
        sql = text(f"""
          with picked as (select unnest(cast(:ids as uuid[])) as container_id),
               live as (select m.container_id, m.fish_id from public.fish_tank_memberships m where m.left_at is null)
          select
            c.id::text as container_id,
            c.tank_code::text as tank_code,
            coalesce(c.label,'') as label,
            coalesce(c.status,'') as status,
            c.container_type::text as container_type,
            {loc_expr} as location,
            c.created_at::timestamptz as created_at,
            c.activated_at,
            c.deactivated_at,
            c.last_seen_at,
            f.fish_code::text as fish_code,
            coalesce(v.nickname,'') as nickname,
            coalesce(v.name,'') as name,
            coalesce(v.genotype,'') as genotype,
            coalesce(v.genetic_background,'') as genetic_background,
            coalesce(v.stage,'') as stage,
            v.dob as dob
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
               live as (select m.container_id, m.fish_id from public.fish_tank_memberships m where m.left_at is null)
          select
            c.id::text as container_id,
            c.tank_code::text as tank_code,
            coalesce(c.label,'') as label,
            coalesce(c.status,'') as status,
            c.container_type::text as container_type,
            {loc_expr} as location,
            c.created_at::timestamptz as created_at,
            c.activated_at,
            c.deactivated_at,
            c.last_seen_at,
            f.fish_code::text as fish_code,
            ''::text as nickname,
            ''::text as name,
            ''::text as genotype,
            ''::text as genetic_background,
            ''::text as stage,
            null::date as dob
          from picked p
          join public.containers c on c.id = p.container_id
          left join live L on L.container_id = c.id
          left join public.fish f on f.id = L.fish_id
          order by c.created_at asc, c.tank_code asc
        """)
    with _get_engine().begin() as cx:
        return pd.read_sql(sql, cx, params={"ids": container_ids})

def main():
    st.title("🔎 Search Fish → Tanks")

    with _get_engine().begin() as cx:
        dbg = pd.read_sql(text("select current_database() db, inet_server_addr() host, current_user u"), cx)
    st.caption(f"DB: {dbg['db'][0]} @ {dbg['host'][0]} as {dbg['u'][0]}")

    with st.form("filters"):
        c1, c2 = st.columns([3,1])
        with c1:
            q_raw = st.text_input("Search fish (code/name/nickname/background/genotype/base)", "")
        with c2:
            limit = int(st.number_input("Limit", min_value=1, max_value=5000, value=500, step=100))
        st.form_submit_button("Search")

    q = (q_raw or "").strip() or None

    if not _view_exists("public", "v_fish_overview_all"):
        st.error("View public.v_fish_overview_all not found. Apply the migration and retry.")
        st.stop()

    df = _search_overview_all(q, limit)
    if df.empty:
        st.info("No fish match your search."); return

    safe_text = [
        "fish_code","name","nickname","genetic_background",
        "line_building_stage","description","notes",
        "created_by","transgene_base_code","allele_nickname","zygosity",
        "transgene_base","allele_name",
        "transgene_pretty_nickname","transgene_pretty_name",
        "genotype","genotype_rollup_clean",
    ]
    for c in safe_text:
        if c in df.columns:
            df[c] = df[c].astype("string").fillna("")

    if "n_living_tanks" in df.columns:
        df["n_living_tanks"] = pd.to_numeric(df["n_living_tanks"], errors="coerce").fillna(0).astype(int)

    df_display = df.copy()
    if "allele_number" in df_display.columns:
        s = pd.to_numeric(df_display["allele_number"], errors="coerce")
        df_display["allele_number"] = s.map(lambda x: "" if pd.isna(x) or int(x)==0 else int(x))

    st.subheader("Fish (from public.v_fish_overview_all)")
    df_display.insert(0, "✓ Select", False)
    key_sig = "|".join(df_display.get("fish_code", pd.Series([], dtype=str)).astype(str).tolist()) or str(len(df_display))
    if st.session_state.get("_sft_sig") != key_sig:
        st.session_state["_sft_sig"] = key_sig
        st.session_state["_sft_table"] = df_display.copy()

    a, b, c = st.columns([1,1,3])
    with a:
        if st.button("Select all"):
            st.session_state["_sft_table"].loc[:, "✓ Select"] = True
    with b:
        if st.button("Clear all"):
            st.session_state["_sft_table"].loc[:, "✓ Select"] = False
    with c:
        st.caption(f"{len(df_display)} fish")

    edited = st.data_editor(
        st.session_state["_sft_table"],
        use_container_width=True,
        hide_index=True,
        key="sft_editor",
    )
    st.session_state["_sft_table"] = edited.copy()

    if "fish_code" not in edited.columns:
        st.warning("This view lacks fish_code; cannot load tanks."); return

    selected_codes = edited.loc[edited["✓ Select"], "fish_code"].astype(str).tolist()

    st.subheader("Current tanks for selected fish")
    if not selected_codes:
        st.info("Select one or more fish above to see their current tanks."); return

    tanks_df = _load_tanks_for_codes(selected_codes)
    if tanks_df.empty:
        st.info("No active memberships / tanks for selected fish."); return

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
    tanks_view.insert(0, "✓ Print", False)

    cols = ["✓ Print","Fish code","Tank code","Label","Status","Type","Created","Activated","Deactivated","Last seen","Container ID"]
    if "Location" in tanks_view.columns:
        cols.insert(5, "Location")

    tanks_sig = "|".join(tanks_view["Container ID"].astype(str).tolist())
    if st.session_state.get("_sft_tanks_sig") != tanks_sig:
        st.session_state["_sft_tanks_sig"] = tanks_sig
        st.session_state["_sft_tanks_table"] = tanks_view.copy()

    t1, t2, _ = st.columns([1,1,6])
    with t1:
        if st.button("Select all tanks"):
            st.session_state["_sft_tanks_table"].loc[:, "✓ Print"] = True
            st.rerun()
    with t2:
        if st.button("Clear all tanks"):
            st.session_state["_sft_tanks_table"].loc[:, "✓ Print"] = False
            st.rerun()

    tanks_edited = st.data_editor(
        st.session_state["_sft_tanks_table"][cols],
        use_container_width=True,
        hide_index=True,
        key="sft_tanks_editor",
        column_config={"✓ Print": st.column_config.CheckboxColumn("✓ Print", default=False)},
    )
    st.session_state["_sft_tanks_table"] = tanks_edited.copy()

    st.subheader("Print labels")
    to_print = tanks_edited.loc[tanks_edited["✓ Print"] == True]
    st.caption(f"{len(to_print)} tank(s) selected for labels")

    pdf_bytes = b""
    if not to_print.empty:
        ids = to_print["Container ID"].astype(str).tolist()
        enriched = _fetch_enriched_for_containers(ids)
        if not enriched.empty:
            rows = []
            for _, r in enriched.iterrows():
                rows.append({
                    "tank_code": r.get("tank_code") or r.get("label"),
                    "label": r.get("label"),
                    "fish_code": r.get("fish_code"),
                    "nickname": r.get("nickname"),
                    "name": r.get("name"),
                    "genotype": r.get("genotype"),
                    "genetic_background": r.get("genetic_background"),
                    "stage": r.get("stage"),
                    "dob": r.get("dob"),
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
        with st.expander("Printer settings", expanded=(PRINTER_QUEUE_DEFAULT == "")):
            queue = st.text_input("CUPS queue", value=PRINTER_QUEUE_DEFAULT, placeholder="Brother_QL_1110NWB")
            media = st.text_input("Media name", value=PRINTER_MEDIA_DEFAULT, help="e.g., Custom.61x38mm")
        can_print = bool(pdf_bytes) and bool(queue.strip())
        if st.button("🖨️ Send to Brother", type="secondary", use_container_width=True, disabled=not can_print):
            ok, msg = _print_pdf_to_cups(pdf_bytes, queue.strip(), media.strip())
            if ok:
                st.success(f"Sent to printer '{queue}'. {msg}")
            else:
                st.error(f"Print failed: {msg}")

if __name__ == "__main__":
    main()