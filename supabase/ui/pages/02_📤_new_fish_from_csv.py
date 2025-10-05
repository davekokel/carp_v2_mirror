# supabase/ui/pages/02_📤_new_fish_from_csv.py
from __future__ import annotations

import sys, io
from pathlib import Path
from hashlib import sha256
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supabase.ui.lib.app_ctx import get_engine, engine_info
from supabase.ui.lib.csv_normalize import normalize_fish_seedkit, validate_seedkit
from supabase.ui.lib.alloc_link import resolve_or_allocate_number, ensure_transgene_pair, link_fish_to

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

from typing import List, Dict, Any, Optional
import pandas as pd
import streamlit as st
from sqlalchemy import text

PAGE_TITLE = "CARP — New fish from CSV"
st.set_page_config(page_title=PAGE_TITLE, page_icon="📤", layout="wide")
st.title("📤 New fish from CSV")

eng = get_engine()
dbg = engine_info(eng)
st.caption(f"DB debug → db={dbg['db']} user={dbg['usr']} host={dbg['host']}:{dbg['port']}")

REQUIRED_TABLES = [
    ("public", "fish"),
    ("public", "fish_transgene_alleles"),
    ("public", "transgene_allele_registry"),
    ("public", "transgene_allele_counters"),
]
REQUIRED_VIEW = ("public", "v_fish_overview")

with eng.begin() as cx:
    missing: List[str] = []
    for sch, tbl in REQUIRED_TABLES:
        ok = cx.execute(text("select to_regclass(:q) is not null"), {"q": f"{sch}.{tbl}"}).scalar()
        if not ok:
            missing.append(f"{sch}.{tbl}")
    ok_view = cx.execute(text("select to_regclass(:q) is not null"), {"q": f"{REQUIRED_VIEW[0]}.{REQUIRED_VIEW[1]}"}).scalar()
    if not ok_view:
        missing.append(f"{REQUIRED_VIEW[0]}.{REQUIRED_VIEW[1]}")

if missing:
    st.error("Database schema is incomplete. Missing objects:\n\n- " + "\n- ".join(missing) + "\n\nRun your migrations, then reload this page.")
    st.stop()

PREVIEW_KEY = "upload_preview_df"
RESULT_KEY  = "upload_insert_result"

def _reset_preview():
    st.session_state.pop(PREVIEW_KEY, None)
    st.session_state.pop(RESULT_KEY, None)

uploaded = st.file_uploader("Upload .csv", type=["csv"], on_change=_reset_preview)

col1, col2, col3 = st.columns([1,1,2])
with col1:
    load_clicked = st.button("Load preview", disabled=uploaded is None)
with col2:
    insert_clicked = st.button("Insert into database", disabled=(PREVIEW_KEY not in st.session_state))
with col3:
    st.caption(
        "CSV headers: transgene_base_code, allele_nickname or allele_number, name, created_by, date_birth, "
        "zygosity (optional). Note: fish_code is **ignored**; the database will generate it."
    )

# ------------------------- Load preview -------------------------
if load_clicked and uploaded is not None:
    try:
        raw = uploaded.read().decode("utf-8")
        df_in = pd.read_csv(io.StringIO(raw))

        # Normalize to canonical schema
        df_norm = normalize_fish_seedkit(df_in)

        # Ensure fish_code column exists for validation, even if CSV didn't have it
        if "fish_code" not in df_norm.columns:
            df_norm["fish_code"] = ""

        # Pass-through optional CSV columns (kept if present)
        passthrough = ["nickname", "line_building_stage", "description", "notes"]
        for col in [c for c in passthrough if c in df_in.columns]:
            df_norm[col] = df_in[col]

        # Seed batch id = file basename (no extension)
        seed_batch_id = Path(uploaded.name).stem
        df_norm["__seed_batch_id__"] = seed_batch_id

        # Stable row_key from key fields
        def _row_key(row: pd.Series) -> str:
            parts = [
                str(row.get("name") or ""),
                str(row.get("created_by") or ""),
                str(row.get("date_birth") or ""),
                str(row.get("transgene_base_code") or ""),
                str(row.get("allele_nickname") or row.get("allele_number") or ""),
                str(row.get("zygosity") or ""),
            ]
            return sha256("|".join(parts).encode("utf-8")).hexdigest()
        df_norm["__row_key__"] = [ _row_key(r) for _, r in df_norm.iterrows() ]

        # Validate after augmentation (now safe: fish_code exists)
        issues = validate_seedkit(df_norm)
        if issues:
            st.warning(" • ".join(issues))

        # Store; we still HIDE fish_code in the preview table later
        st.session_state[PREVIEW_KEY] = {"raw": df_in, "norm": df_norm, "seed": seed_batch_id}
        st.info(f"Batch detected: **{seed_batch_id}**")
    except Exception as e:
        st.exception(e)

# ------------------------- Preview UI -------------------------
if PREVIEW_KEY in st.session_state:
    store = st.session_state[PREVIEW_KEY]
    if isinstance(store, dict):
        df_in = store.get("raw")
        df_norm = store.get("norm")
        seed_batch_id = store.get("seed")
    else:
        df_in = None
        df_norm = store
        seed_batch_id = "unknown_batch"

    st.subheader("Preview")
    tab_raw, tab_norm, tab_cols = st.tabs(["Raw CSV", "Normalized", "Columns"])

    with tab_raw:
        if df_in is not None:
            st.caption(f"Raw CSV shape: {df_in.shape[0]} rows × {df_in.shape[1]} cols")
            st.dataframe(df_in, width='stretch')
        else:
            st.info("Raw CSV not available for this preview (loaded via legacy flow).")

    with tab_norm:
        st.caption(
            f"Normalized shape: {df_norm.shape[0]} rows × {df_norm.shape[1]} cols • batch: {seed_batch_id}  "
            "• note: fish_code will be generated by the database on insert"
        )
        df_norm_preview = df_norm.drop(
            columns=["fish_code", "allele_number", "__seed_batch_id__", "__row_key__"],
            errors="ignore",
        )
        st.dataframe(df_norm_preview, width='stretch')

    with tab_cols:
        st.write("Normalized columns:", list(df_norm.columns))

# ------------------------- Insert -------------------------
if insert_clicked and (PREVIEW_KEY in st.session_state):
    created_ct = 0
    updated_ct = 0
    linked_ct  = 0
    skipped_ct = 0

    try:
        _store = st.session_state[PREVIEW_KEY]
        if isinstance(_store, dict):
            df_norm = _store["norm"]
            seed_batch_id = _store.get("seed") or "unknown_batch"
        else:
            df_norm = _store
            seed_batch_id = "unknown_batch"

        # Option: replace existing batch first (idempotent per file)
        replace_batch = st.toggle(
            "Replace existing rows for this batch_id before insert",
            value=True,
            help="Deletes any prior imports with this batch id, then loads fresh.",
        )

        with eng.begin() as conn:
            conn.execute(text("set application_name to 'csv_page'"))
            conn.execute(text("SET CONSTRAINTS ALL DEFERRED"))
            # Preflight: ensure load_log_fish exists with row_key + UNIQUE; also show where we are connected
            probe = conn.execute(text("""
                select current_database() as db, inet_server_addr()::text as server_addr, inet_server_port() as port
            """)).mappings().first()
            st.caption(f"Import probe → db={probe['db']} server={probe['server_addr']}:{probe['port']}")

            # Preflight: ensure fish_seed_batches exists + DEFERRABLE FK → fish(id); drop legacy trigger
            conn.execute(text("""
                DO $$
                BEGIN
                IF to_regclass('public.fish_seed_batches') IS NULL THEN
                    CREATE TABLE public.fish_seed_batches (
                    fish_id       uuid PRIMARY KEY,
                    seed_batch_id text NOT NULL,
                    updated_at    timestamptz NOT NULL DEFAULT now()
                    );
                END IF;

                -- Drop any existing FK by name, then recreate DEFERRABLE INITIALLY DEFERRED
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE table_schema='public' AND table_name='fish_seed_batches'
                    AND constraint_type='FOREIGN KEY'
                ) THEN
                    EXECUTE (
                    SELECT 'ALTER TABLE public.fish_seed_batches DROP CONSTRAINT ' || quote_ident(tc.constraint_name)
                    FROM information_schema.table_constraints tc
                    WHERE tc.table_schema='public' AND tc.table_name='fish_seed_batches'
                        AND tc.constraint_type='FOREIGN KEY'
                    LIMIT 1
                    );
                END IF;

                ALTER TABLE public.fish_seed_batches
                    ADD CONSTRAINT fk_fsb_fish
                    FOREIGN KEY (fish_id) REFERENCES public.fish(id)
                    ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED;

                -- Remove legacy trigger; we upsert mapping explicitly in app code
                IF EXISTS (
                    SELECT 1 FROM pg_trigger
                    WHERE tgrelid='public.load_log_fish'::regclass
                    AND tgname='tg_upsert_fish_seed_maps'
                    AND NOT tgisinternal
                ) THEN
                    DROP TRIGGER tg_upsert_fish_seed_maps ON public.load_log_fish;
                END IF;
                END$$;
            """))

            conn.execute(text("""
                DO $$
                BEGIN
                IF to_regclass('public.load_log_fish') IS NULL THEN
                    CREATE TABLE public.load_log_fish (
                    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    fish_id       uuid NOT NULL REFERENCES public.fish(id) ON DELETE CASCADE,
                    seed_batch_id text NOT NULL,
                    row_key       text NOT NULL,
                    logged_at     timestamptz NOT NULL DEFAULT now()
                    );
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='load_log_fish' AND column_name='row_key'
                ) THEN
                    ALTER TABLE public.load_log_fish ADD COLUMN row_key text NOT NULL DEFAULT '';
                    ALTER TABLE public.load_log_fish ALTER COLUMN row_key DROP DEFAULT;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE table_schema='public' AND table_name='load_log_fish'
                    AND constraint_type='UNIQUE' AND constraint_name='uq_load_log_fish_batch_row'
                ) THEN
                    ALTER TABLE public.load_log_fish
                    ADD CONSTRAINT uq_load_log_fish_batch_row UNIQUE (seed_batch_id, row_key);
                END IF;
                END$$;
            """))
            # Ensure optional fish columns
            conn.execute(text("""
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='fish' AND column_name='nickname'
                  ) THEN
                    ALTER TABLE public.fish ADD COLUMN nickname text;
                  END IF;
                  IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='fish' AND column_name='line_building_stage'
                  ) THEN
                    ALTER TABLE public.fish ADD COLUMN line_building_stage text;
                  END IF;
                END$$;
            """))

            # Optional: clear previous rows for this batch (and its log)
            if replace_batch:
                conn.execute(text("""
                    delete from public.fish
                    where id in (select fish_id from public.load_log_fish where seed_batch_id = :seed)
                """), {"seed": seed_batch_id})
                conn.execute(text("delete from public.load_log_fish where seed_batch_id = :seed"), {"seed": seed_batch_id})

            # Insert fish — DB trigger generates fish_code; include optional cols if present
            base_cols = ["name","created_by","date_birth"]
            opt_cols  = [c for c in ["nickname","line_building_stage"] if c in df_norm.columns]
            to_insert = df_norm[base_cols + opt_cols].copy()

            created_rows: List[Dict[str, Any]] = []
            new_codes: list[str] = []  # capture codes trigger returned
            # NOTE: `r` comes from `to_insert`; for metadata like __row_key__, read from df_norm via r.name
            for _, r in to_insert.iterrows():
                params = {
                    "name":  r.get("name"),
                    "by":    r.get("created_by"),
                    "dob":   r.get("date_birth"),
                    "nick":  (r.get("nickname") if "nickname" in opt_cols else None),
                    "stage": (r.get("line_building_stage") if "line_building_stage" in opt_cols else None),
                }
                row = conn.execute(
                    text(f"""
                        insert into public.fish (
                          id, name, created_by, date_birth
                          {', nickname' if 'nickname' in opt_cols else ''}
                          {', line_building_stage' if 'line_building_stage' in opt_cols else ''}
                        )
                        values (
                          gen_random_uuid(), :name, :by, :dob
                          {', :nick' if 'nickname' in opt_cols else ''}
                          {', :stage' if 'line_building_stage' in opt_cols else ''}
                        )
                        returning id, fish_code
                    """),
                    params,
                ).mappings().first()
                if not row or not row.get("id"):
                    raise RuntimeError("Fish insert returned no id")
                created_rows.append(dict(row))
                new_codes.append(row["fish_code"])

                # Upsert the batch mapping explicitly (no trigger needed)
                conn.execute(
                    text("""
                        insert into public.fish_seed_batches (fish_id, seed_batch_id, updated_at)
                        values (:fid, :seed, now())
                        on conflict (fish_id) do update
                        set seed_batch_id = excluded.seed_batch_id,
                            updated_at    = excluded.updated_at
                    """),
                    {"fid": row["id"], "seed": seed_batch_id},
                )

                # Log the load for idempotency and batch provenance
                conn.execute(
                    text("""
                        insert into public.load_log_fish (fish_id, seed_batch_id, row_key)
                        values (:fid, :seed, :rk)
                        on conflict (seed_batch_id, row_key) do nothing
                    """),
                    {"fid": row["id"], "seed": seed_batch_id, "rk": df_norm.loc[r.name, "__row_key__"]},
                )

            created_ct = len(created_rows)
            st.caption(f"new fish_code(s): {', '.join(new_codes)}")
            # Map row index → inserted id
            idx_to_id = {i: cr["id"] for i, cr in zip(to_insert.index.tolist(), created_rows)}

            # Link genotype (registry-first; legacy-aware)
            base_nonempty = df_norm["transgene_base_code"].astype("string").str.strip().ne("")
            nick_nonempty = df_norm["allele_nickname"].astype("string").str.strip().ne("")
            has_num       = df_norm["allele_number"].notna()
            gmask = base_nonempty & (nick_nonempty | has_num)
            st.caption("debug: base_nonempty=%d nick_nonempty=%d gmask=%d" % (int(base_nonempty.sum()), int(nick_nonempty.sum()), int(gmask.sum())))

            # Seed unique bases up front to satisfy FK on transgene_alleles
            bases_to_seed = (
                df_norm.loc[gmask, "transgene_base_code"]
                .astype("string").str.strip()
                .dropna().unique().tolist()
            )
            for b in bases_to_seed:
                if b:
                    conn.execute(
                        text("""
                            insert into public.transgenes (transgene_base_code)
                            values (:b)
                            on conflict (transgene_base_code) do nothing
                        """),
                        {"b": b},
                    )

            for idx, r in df_norm.loc[gmask].iterrows():
                fish_id = idx_to_id.get(idx)
                if not fish_id:
                    skipped_ct += 1
                    continue

                base = (r.get("transgene_base_code") or "").strip()
                nick = (r.get("allele_nickname") or "").strip() or None
                by   = (r.get("created_by") or None)
                zyg  = (r.get("zygosity") or None)

                n: Optional[int] = None
                if nick:
                    n = resolve_or_allocate_number(conn, base, nick, by)
                    if n is not None:
                        st.caption(f"alloc: registry hit base='{base}' nick='{nick}' → n={int(n)}")

                if n is None:
                    try:
                        n = int(r.get("allele_number"))
                        st.caption(f"alloc: csv numeric base='{base}' → n={n}")
                    except Exception:
                        n = None

                if n is None:
                    try:
                        rows = conn.execute(
                            text("""
                            select allele_nickname, allele_number
                            from public.transgene_allele_registry
                            where transgene_base_code = :b
                            order by allele_nickname
                            limit 10
                            """),
                            {"b": base},
                        ).mappings().all()
                        sample = ", ".join(f"{row['allele_nickname']}→{row['allele_number']}" for row in rows)
                    except Exception:
                        sample = ""
                    st.caption(f"debug skip: base='{base}' nick='{nick}' (no number) {('['+sample+']') if sample else ''}")
                    skipped_ct += 1
                    continue

                ensure_transgene_pair(conn, base, n)
                link_fish_to(conn, str(fish_id), base, n, zygosity=zyg, nickname=nick)
                linked_ct += 1

        st.session_state[RESULT_KEY] = {
            "created": int(created_ct),
            "updated": int(0),
            "with_alleles": int(linked_ct),
            "skipped_no_allele": int(skipped_ct),
            "skipped": int(skipped_ct),
            "seed_batch_id": seed_batch_id,
        }

    except Exception as e:
        st.exception(e)

# ------------------------- Result & recent slice -------------------------
res = st.session_state.get(RESULT_KEY)
if res:
    st.success(
        f"Batch **{res.get('seed_batch_id','?')}** — "
        f"Inserted {res.get('created',0)} new, updated {res.get('updated',0)}; "
        f"linked genotype for {res.get('with_alleles',0)} rows; "
        f"skipped {res.get('skipped_no_allele',res.get('skipped',0))} without allele."
    )

    st.markdown("#### Recent rows (from `vw_fish_overview_with_label`)")
    try:
        recent = pd.read_sql(
            """
            select *
            from public.vw_fish_overview_with_label
            where batch_label = %(seed)s
            limit 50
            """,
            eng,
            params={"seed": seed_batch_id},
        )

        # sort in pandas if created_at exists
        if "created_at" in recent.columns:
            recent = recent.sort_values(["created_at", "fish_code"], ascending=[False, True])
        else:
            recent = recent.sort_values(["fish_code"], ascending=[True])

        # cast UUID-like columns to strings for Arrow display
        for c in ("id", "fish_id"):
            if c in recent.columns:
                recent[c] = recent[c].astype("string")

        preview_like = [
            "fish_code","name","created_by","date_birth",
            "transgene_base_code_filled","allele_code_filled","allele_name_filled",
            "genotype_display",
            "nickname","line_building_stage",
        ]
        view_generated = [
            "age_weeks","age_days","batch_label",
            "zygosity_text","link_nicknames_text",
            "last_plasmid_injection_at","plasmid_injections_text",
            "last_rna_injection_at","rna_injections_text",
            "created_at","id",
        ]

        r = recent.copy().replace("", pd.NA).replace("None", pd.NA)
        nonempty_cols = [c for c in r.columns if r[c].notna().any()]

        ordered = [c for c in preview_like if c in nonempty_cols] + [c for c in view_generated if c in nonempty_cols]
        ordered += [c for c in nonempty_cols if c not in ordered]
        if not ordered:
            ordered = list(recent.columns)

        st.dataframe(recent[ordered], width="stretch")

        hidden = [c for c in recent.columns if c not in ordered]
        if hidden:
            st.caption(f"({len(hidden)} empty columns hidden: {', '.join(hidden[:6])}{'…' if len(hidden)>6 else ''})")
    except Exception as e:
        st.warning(f"Could not read vw_fish_overview_with_label yet: {e}")
