# 03_🧬_new_fish_from_cross.py
from __future__ import annotations

# --- sys.path before local imports ---
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]  # …/carp_v2
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Shared engine / helpers
from supabase.ui.lib_shared import current_engine, connection_info
import supabase.queries as Q

# 🔒 auth
try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
require_app_unlock()

from datetime import date, datetime, UTC
from typing import List, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text

# --------------------------------------------------------------------------------------
# Page config & engine
# --------------------------------------------------------------------------------------
st.set_page_config(page_title="CARP — New Cross → Offspring → Treatments", page_icon="🧬", layout="wide")
st.title("🧬 New Cross → Offspring → Treatments")

eng = current_engine()
dbg = connection_info(eng)
st.caption(f"DB debug → db={dbg['db']} user={dbg['user']}")

# Optional: force-refresh to clear caches / sticky editors
if st.button("🔁 Refresh data", key="refresh_nc"):
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    for k in list(st.session_state.keys()):
        if k in ("nc_parent_grid", "nc_parent_grid_v2"):
            st.session_state.pop(k, None)
    st.rerun()

# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def load_parents(engine) -> pd.DataFrame:
    with engine.begin() as conn:
        rows = Q.fish_overview_minimal(conn, q=None, limit=1000, require_links=True)
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
        "id","fish_code","name","created_at","created_by",
        "transgene_base_code_filled","allele_code_filled"
    ])
    if "id" in df.columns:
        df["id"] = df["id"].astype(str)
    # keep the columns your grid expects
    return df[[
        "id","fish_code","name",
        "transgene_base_code_filled","allele_code_filled","created_at"
    ]]

def _alleles_for_fish(conn, fish_id: str) -> list[tuple[str,int]]:
    rows = Q.alleles_for_fish(conn, fish_id)
    return [(r["transgene_base_code"], int(r["allele_number"])) for r in rows]
    
def ensure_treatment_objects(conn) -> None:
    conn.execute(text("""
    do $$
    begin
      if to_regclass('public.injected_plasmid_treatments') is null then
        create table public.injected_plasmid_treatments(
          id uuid primary key default gen_random_uuid(),
          fish_id uuid not null references public.fish(id) on delete cascade,
          plasmid_id uuid not null,
          amount numeric null,
          units text null,
          at_time timestamptz null,
          note text null
        );
      end if;

      if to_regclass('public.injected_rna_treatments') is null then
        create table public.injected_rna_treatments(
          id uuid primary key default gen_random_uuid(),
          fish_id uuid not null references public.fish(id) on delete cascade,
          rna_id uuid not null,
          amount numeric null,
          units text null,
          at_time timestamptz null,
          note text null
        );
      end if;
    end$$;
    """))

# --------------------------------------------------------------------------------------
# Parent picker (checkbox grid)
# --------------------------------------------------------------------------------------
st.subheader("Pick exactly two parents below (check the boxes):")

parents = load_parents(eng)

with eng.begin() as _cx:
    base_ct  = _cx.execute(text("select count(*) from public.v_fish_overview")).scalar()
    label_ct = _cx.execute(text("select count(*) from public.vw_fish_overview_with_label")).scalar()
    fish_ct  = _cx.execute(text("select count(*) from public.fish")).scalar()
st.caption(f"Diagnostic → v_fish_overview: {base_ct} • vw_with_label: {label_ct} • fish table: {fish_ct}")

if parents.empty:
    st.info("No eligible parents found. Upload cohorts with genotype first.")
    st.stop()

grid = parents.copy()
grid.insert(0, "select", False)
grid = grid.set_index("id")

edited = st.data_editor(
    grid,
    key="nc_parent_grid_v2",
    width="stretch",
    hide_index=False,
    column_config={
        "select": st.column_config.CheckboxColumn("Select"),
        "fish_code": st.column_config.TextColumn("Fish code"),
        "name": st.column_config.TextColumn("Name"),
        "transgene_base_code_filled": st.column_config.TextColumn("Transgene base codes"),
        "allele_code_filled": st.column_config.TextColumn("Allele numbers"),
        "created_at": st.column_config.DatetimeColumn("Created"),
    },
    disabled=False,
)

selected_ids = [str(idx) for idx, sel in edited["select"].items() if sel]
if len(selected_ids) < 2:
    st.warning("Select two rows to continue.")
    st.stop()
elif len(selected_ids) > 2:
    st.warning("Please select exactly two rows.")
    st.stop()

# Convert IDs to labels
id_to_label = {
    r["id"]: f"{r['fish_code']}{' — ' + r['name'] if r['name'] else ''}"
    for _, r in parents.iterrows()
}
mother_id, father_id = selected_ids[0], selected_ids[1]

# --------------------------------------------------------------------------------------
# Genotype selection (precise)
# --------------------------------------------------------------------------------------
st.markdown("### Genotype to assign to offspring")

with eng.begin() as c:
    mom_pairs = _alleles_for_fish(c, mother_id)
    dad_pairs = _alleles_for_fish(c, father_id)

def _labels(pairs: list[Tuple[str,int]]) -> list[str]:
    return [f"{b} • {a}" for (b, a) in pairs]

mom_labels_all = _labels(mom_pairs)
dad_labels_all = _labels(dad_pairs)

col_m, col_d = st.columns(2)
sel_mom = col_m.multiselect("From mother", mom_labels_all, default=mom_labels_all, key="nc_sel_mom")
sel_dad = col_d.multiselect("From father", dad_labels_all, default=dad_labels_all, key="nc_sel_dad")

zyg_inherited = st.selectbox("Zygosity for inherited elements",
                             ["unknown", "heterozygous", "homozygous"], index=0, key="nc_zyg_inh")

# Optional extras (union)
st.markdown("**Add extra genotype elements (optional)**")
union_labels = sorted(set(mom_labels_all + dad_labels_all))
sel_extra = st.multiselect("Add extra (base • allele)", union_labels, default=[], key="nc_sel_extra")
zyg_extra = st.selectbox("Zygosity for added elements",
                         ["unknown", "heterozygous", "homozygous"], index=0, key="nc_zyg_extra")

def _rev(labels: list[str], base_pairs: list[Tuple[str,int]]) -> list[Tuple[str,int]]:
    lut = {f"{b} • {a}": (b, a) for (b, a) in base_pairs}
    return [lut[l] for l in labels if l in lut]

sel_mom_pairs = _rev(sel_mom, mom_pairs)
sel_dad_pairs = _rev(sel_dad, dad_pairs)
sel_extra_pairs = _rev(sel_extra, list(set(mom_pairs + dad_pairs)))

# --------------------------------------------------------------------------------------
# Offspring & Treatments
# --------------------------------------------------------------------------------------
st.markdown("### Treatment details (optional)")

with st.expander("Plasmid treatments"):
    apply_plasmid = st.checkbox("Apply plasmid treatment", value=False, key="nc_apply_plasmid")
    plasmid_id = st.text_input("plasmid_id (UUID)", value="", key="nc_plasmid_id")
    plasmid_amount = st.number_input("amount", value=0.0, step=0.1, format="%.3f", key="nc_plasmid_amount")
    plasmid_units = st.text_input("units", value="ng", key="nc_plasmid_units")
    plasmid_note = st.text_input("note", value="", key="nc_plasmid_note")

with st.expander("RNA treatments"):
    apply_rna = st.checkbox("Apply RNA treatment", value=False, key="nc_apply_rna")
    rna_id = st.text_input("rna_id (UUID)", value="", key="nc_rna_id")
    rna_amount = st.number_input("amount (RNA)", value=0.0, step=0.1, format="%.3f", key="nc_rna_amount")
    rna_units = st.text_input("units (RNA)", value="ng", key="nc_rna_units")
    rna_note = st.text_input("note (RNA)", value="", key="nc_rna_note")

st.markdown("### Create offspring")
birth_date = st.date_input("Birth date (optional)", value=date.today(), key="nc_birth")
created_by = st.text_input("Created by (optional)", value="", key="nc_created_by")
name_prefix = st.text_input("Offspring name prefix (optional)", value="offspring", key="nc_name_prefix")

do_create = st.button("Create offspring", type="primary", key="nc_create_btn")

created: List[Tuple[str, str]] = []

if do_create:
    with st.spinner("Creating offspring…"):
        with eng.begin() as conn:
            # Try function first (check pg_proc)
            has_fn = conn.execute(text("""
            select exists (
                select 1
                from pg_proc p
                join pg_namespace n on n.oid = p.pronamespace
                where p.proname = 'create_offspring_batch'
                and n.nspname = 'public'
            )
            """)).scalar()
            if has_fn:
                res = conn.execute(
                    text("""
                        select child_id, fish_code
                        from public.create_offspring_batch(
                          :mother_id, :father_id, :count, :created_by, :birth_date, :name_prefix
                        )
                    """),
                    {
                        "mother_id": str(mother_id),
                        "father_id": str(father_id),
                        "count": 1,
                        "created_by": created_by if created_by else None,
                        "birth_date": birth_date if birth_date else None,
                        "name_prefix": name_prefix if name_prefix else None,
                    },
                ).fetchone()
                if res:
                    child_id, fish_code = str(res[0]), res[1]
                else:
                    child_id, fish_code = None, None
            else:
                # Safe fallback: insert a cohort row with generated code
                row = conn.execute(
                    text("""
                      insert into public.fish (id, name, created_by, date_birth)
                      values (gen_random_uuid(), concat('X-', to_char(now(),'YYMMDD-HH24MISS')), null, :by, :dob)
                      returning id, fish_code
                    """),
                    {"by": created_by or None, "dob": birth_date or None},
                ).mappings().first()
                child_id, fish_code = str(row["id"]), row["fish_code"]

            if not child_id:
                st.error("Failed to create offspring.")
                st.stop()

            created.append((child_id, fish_code))

            # Copy precisely-chosen parental alleles
            def _insert_pairs(pairs: list[Tuple[str,int]], zyg: str):
                for base_code, allele_number in pairs:
                    try:
                        conn.execute(
                            text("""
                                insert into public.fish_transgene_alleles
                                  (fish_id, transgene_base_code, allele_number, zygosity)
                                values (:fish_id, :base, :allele, :zyg)
                                on conflict do nothing
                            """),
                            {"fish_id": child_id, "base": base_code, "allele": int(allele_number), "zyg": zyg},
                        )
                    except Exception:
                        pass

            _insert_pairs(sel_mom_pairs, zyg_inherited)
            _insert_pairs(sel_dad_pairs, zyg_inherited)
            _insert_pairs(sel_extra_pairs, zyg_extra)


            # Ensure child has at least one allele (avoid orphan)
            n_links = conn.execute(
                text("select count(*) from public.fish_transgene_alleles where fish_id=:fid"),
                {"fid": child_id},
            ).scalar()
            if int(n_links) == 0:
                conn.execute(text("delete from public.fish where id=:fid"), {"fid": child_id})
                st.error("Created cohort had no genotype links; it was removed.")
                st.stop()

            # Optional treatments
            ensure_treatment_objects(conn)
            now = datetime.now(UTC)
            if apply_plasmid and plasmid_id.strip():
                conn.execute(
                    text("""
                        insert into public.injected_plasmid_treatments
                          (id, fish_id, plasmid_id, amount, units, at_time, note)
                        values (gen_random_uuid(), :fish_id, :plasmid_id, :amount, :units, :at_time, :note)
                        on conflict do nothing
                    """),
                    {
                        "fish_id": child_id,
                        "plasmid_id": plasmid_id.strip(),
                        "amount": None if plasmid_amount == 0 else plasmid_amount,
                        "units": plasmid_units.strip() or None,
                        "at_time": now,
                        "note": plasmid_note.strip() or None,
                    },
                )
            if apply_rna and rna_id.strip():
                conn.execute(
                    text("""
                        insert into public.injected_rna_treatments
                          (id, fish_id, rna_id, amount, units, at_time, note)
                        values (gen_random_uuid(), :fish_id, :rna_id, :amount, :units, :at_time, :note)
                        on conflict do nothing
                    """),
                    {
                        "fish_id": child_id,
                        "rna_id": rna_id.strip(),
                        "amount": None if rna_amount == 0 else rna_amount,
                        "units": rna_units.strip() or None,
                        "at_time": now,
                        "note": rna_note.strip() or None,
                    },
                )

    out_df = pd.DataFrame(created, columns=["child_id", "fish_code"])
    st.success(f"Created offspring {fish_code} from {id_to_label.get(mother_id, mother_id)} × {id_to_label.get(father_id, father_id)}")
    st.dataframe(out_df, width="stretch")
    st.caption("Selected parental genotype elements were applied; extras optional; treatments added if specified.")