from __future__ import annotations

try:
    from supabase.ui.auth_gate import require_app_unlock
except Exception:
    from auth_gate import require_app_unlock
require_app_unlock()

import os, uuid
from datetime import date, timedelta
from typing import Optional, List, Dict

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------
st.set_page_config(page_title="Define Cross — Fish, Genotype, Treatments", page_icon="🧬")
st.title("🧬 Define Cross — Fish, Genotype, Treatments")

def _db_url() -> str:
    u = os.environ.get("DB_URL", "")
    if not u:
        raise RuntimeError("DB_URL not set")
    return u

ENGINE = create_engine(_db_url(), pool_pre_ping=True)

# ---------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------
def _find_plan_matches(mother_id: Optional[str], father_id: Optional[str], limit: int = 50) -> pd.DataFrame:
    """
    Return existing cross_plans for these parents, including:
      - genotype_plan (human readable)
      - treatments_plan (human readable)
      - geno_sig, tx_sig (stable signatures for exact matching)
      - created_by
    """
    if not mother_id or not father_id:
        return pd.DataFrame(columns=[
            "id","plan_title","plan_nickname","plan_date","created_at","created_by",
            "genotype_plan","treatments_plan","geno_sig","tx_sig","mom","dad"
        ])

    sql = text("""
    WITH geno AS (
      SELECT p.id,
             -- human readable genotype
             COALESCE(string_agg(
               format('%s[%s]%s',
                      ga.transgene_base_code,
                      ga.allele_number,
                      COALESCE(' '||ga.zygosity_planned, '')
               ),
               ', ' ORDER BY ga.transgene_base_code, ga.allele_number
             ), '') AS genotype_plan,
             -- signature for exact matching
             COALESCE(string_agg(
               format('%s[%s]|%s',
                      ga.transgene_base_code,
                      ga.allele_number,
                      COALESCE(ga.zygosity_planned,'')
               ),
               ';' ORDER BY ga.transgene_base_code, ga.allele_number
             ), '') AS geno_sig
      FROM public.cross_plans p
      LEFT JOIN public.cross_plan_genotype_alleles ga ON ga.plan_id = p.id
      GROUP BY p.id
    ),
    tx AS (
      SELECT p.id,
             -- human readable treatments (include mix/notes/timing if present)
             COALESCE(string_agg(
               trim(BOTH ' ' FROM concat(
                 COALESCE(ct.treatment_name,''),
                 CASE WHEN ct.injection_mix   IS NOT NULL AND ct.injection_mix   <> '' THEN ' (mix='||ct.injection_mix||')' ELSE '' END,
                 CASE WHEN ct.treatment_notes IS NOT NULL AND ct.treatment_notes <> '' THEN ' ['||ct.treatment_notes||']' ELSE '' END,
                 CASE WHEN ct.timing_note     IS NOT NULL AND ct.timing_note     <> '' THEN ' {'||ct.timing_note||'}' ELSE '' END
               )),
               ' • ' ORDER BY COALESCE(ct.treatment_name,''), COALESCE(ct.rna_id::text,''), COALESCE(ct.plasmid_id::text,'')
             ), '') AS treatments_plan,
             -- signature for exact matching
             COALESCE(string_agg(
               COALESCE(ct.treatment_name,'') || '|' ||
               COALESCE(ct.injection_mix,'')  || '|' ||
               COALESCE(ct.treatment_notes,'')|| '|' ||
               COALESCE(ct.timing_note,'')    || '|' ||
               COALESCE(ct.rna_id::text,'')   || '|' ||
               COALESCE(ct.plasmid_id::text,''),
               ';' ORDER BY COALESCE(ct.treatment_name,''), COALESCE(ct.rna_id::text,''), COALESCE(ct.plasmid_id::text,'')
             ), '') AS tx_sig
      FROM public.cross_plans p
      LEFT JOIN public.cross_plan_treatments ct ON ct.plan_id = p.id
      GROUP BY p.id
    )
    SELECT
      p.id::text AS id,
      p.plan_title,
      p.plan_nickname,
      p.plan_date,
      p.created_at,
      p.created_by,
      g.genotype_plan,
      t.treatments_plan,
      g.geno_sig,
      t.tx_sig,
      fm.fish_code AS mom,
      ff.fish_code AS dad
    FROM public.cross_plans p
    LEFT JOIN geno g ON g.id = p.id
    LEFT JOIN tx   t ON t.id = p.id
    LEFT JOIN public.fish fm ON fm.id = p.mother_fish_id
    LEFT JOIN public.fish ff ON ff.id = p.father_fish_id
    WHERE p.mother_fish_id = :mf AND p.father_fish_id = :ff
    ORDER BY p.created_at DESC
    LIMIT :lim
    """)

    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx, params={"mf": mother_id, "ff": father_id, "lim": limit})

def _geno_signature(rows: List[dict]) -> str:
    """Stable string for planned genotype rows."""
    parts = []
    for r in rows or []:
        bc = (r.get("base_code") or "").strip()
        num = str(int(r.get("allele_number"))) if r.get("allele_number") is not None else ""
        z  = (r.get("zygosity_planned") or "").strip()
        parts.append(f"{bc}[{num}]|{z}")
    parts.sort()
    return ";".join(parts)

def _tx_signature(rows: List[dict]) -> str:
    """Stable string for treatment rows (uses IDs when present to avoid text mismatch)."""
    parts = []
    for r in rows or []:
        parts.append("|".join([
            (r.get("treatment_name") or "").strip(),
            (r.get("injection_mix") or "").strip(),
            (r.get("treatment_notes") or "").strip(),
            (r.get("timing_note") or "").strip(),
            (r.get("rna_id") or "") or "",
            (r.get("plasmid_id") or "") or "",
        ]))
    parts.sort()
    return ";".join(parts)

def _load_fish_overview() -> pd.DataFrame:
    sql = text("""
      select fish_code, name, nickname,
             genotype_text as genotype,
             genetic_background, line_building_stage as stage,
             date_birth, age_days, created_at
      from public.v_fish_overview
      order by created_at desc
    """)
    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx)

def _fish_id_by_code(code: Optional[str]) -> Optional[str]:
    if not code: return None
    with ENGINE.begin() as cx:
        row = cx.execute(text("select id from public.fish where fish_code=:c limit 1"), {"c": code}).fetchone()
        return str(row[0]) if row else None

def _load_fish_alleles_by_codes(codes: List[str]) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=["fish_code","transgene_base_code","allele_number","zygosity","allele_nickname"])
    sql = text("""
      select f.fish_code,
             a.transgene_base_code,
             a.allele_number,
             coalesce(a.zygosity,'')::text as zygosity,
             coalesce(a.allele_nickname,'')::text as allele_nickname
      from public.fish f
      join public.fish_transgene_alleles a on a.fish_id = f.id
      where f.fish_code = any(:codes)
      order by f.fish_code, a.transgene_base_code, a.allele_number
    """)
    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx, params={"codes": codes})

def _load_rna_registry() -> pd.DataFrame:
    sql = text("""
      select id::text as id, rna_code, coalesce(rna_nickname,'') as rna_nickname,
             coalesce(vendor,'') as vendor, coalesce(lot_number,'') as lot_number,
             coalesce(notes,'') as notes, created_at
      from public.rna_registry
      order by rna_code
    """)
    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx)

def _load_plasmid_registry() -> pd.DataFrame:
    sql = text("""
      select id::text as id, plasmid_code, coalesce(plasmid_nickname,'') as plasmid_nickname,
             coalesce(backbone,'') as backbone, coalesce(insert_desc,'') as insert_desc,
             coalesce(vendor,'') as vendor, coalesce(lot_number,'') as lot_number,
             coalesce(notes,'') as notes, created_at
      from public.plasmid_registry
      order by plasmid_code
    """)
    with ENGINE.begin() as cx:
        return pd.read_sql(sql, cx)

def _upsert_rna(rna_code: str, rna_nickname: str, vendor: str, lot_number: str, notes: str, created_by: str) -> None:
    sql = text("""
      insert into public.rna_registry (rna_code, rna_nickname, vendor, lot_number, notes, created_by)
      values (:c, :n, :v, :l, :t, :by)
      on conflict (rna_code) do update
        set rna_nickname = excluded.rna_nickname,
            vendor       = excluded.vendor,
            lot_number   = excluded.lot_number,
            notes        = excluded.notes
    """)
    with ENGINE.begin() as cx:
        cx.execute(sql, dict(c=rna_code.strip(), n=(rna_nickname or "").strip(),
                             v=(vendor or "").strip(), l=(lot_number or "").strip(),
                             t=(notes or "").strip(), by=(created_by or "")))

def _upsert_plasmid(plasmid_code: str, plasmid_nickname: str, backbone: str, insert_desc: str,
                    vendor: str, lot_number: str, notes: str, created_by: str) -> None:
    sql = text("""
      insert into public.plasmid_registry (plasmid_code, plasmid_nickname, backbone, insert_desc, vendor, lot_number, notes, created_by)
      values (:c, :n, :b, :i, :v, :l, :t, :by)
      on conflict (plasmid_code) do update
        set plasmid_nickname = excluded.plasmid_nickname,
            backbone         = excluded.backbone,
            insert_desc      = excluded.insert_desc,
            vendor           = excluded.vendor,
            lot_number       = excluded.lot_number,
            notes            = excluded.notes
    """)
    with ENGINE.begin() as cx:
        cx.execute(sql, dict(c=plasmid_code.strip(), n=(plasmid_nickname or "").strip(),
                             b=(backbone or "").strip(), i=(insert_desc or "").strip(),
                             v=(vendor or "").strip(), l=(lot_number or "").strip(),
                             t=(notes or "").strip(), by=(created_by or "")))

def _insert_cross_plan(plan_date: date,
                       created_by: str,
                       note: Optional[str],
                       mother_fish_id: Optional[str],
                       father_fish_id: Optional[str],
                       plan_title: Optional[str],
                       plan_nickname: Optional[str]) -> Optional[str]:
    sql = text("""
      insert into public.cross_plans
        (plan_date, created_by, note, mother_fish_id, father_fish_id, plan_title, plan_nickname)
      values (:d, :by, :note, :mf, :ff, :title, :nick)
      returning id
    """)
    with ENGINE.begin() as cx:
        row = cx.execute(sql, dict(d=plan_date, by=created_by, note=note,
                                   mf=mother_fish_id, ff=father_fish_id,
                                   title=plan_title, nick=plan_nickname)).fetchone()
        return str(row[0]) if row else None

def _upsert_plan_genotypes(plan_id: str, rows: List[dict]) -> int:
    if not rows: return 0
    sql = text("""
      insert into public.cross_plan_genotype_alleles (plan_id, transgene_base_code, allele_number, zygosity_planned)
      values (:pid, :bc, :num, :zyg)
      on conflict (plan_id, transgene_base_code, allele_number) do update
        set zygosity_planned = excluded.zygosity_planned
    """)
    n = 0
    with ENGINE.begin() as cx:
        for r in rows:
            cx.execute(sql, dict(pid=plan_id, bc=r["base_code"], num=int(r["allele_number"]), zyg=r.get("zygosity_planned")))
            n += 1
    return n

def _upsert_plan_treatments(plan_id: str, rows: List[dict]) -> int:
    if not rows: return 0
    sql = text("""
      insert into public.cross_plan_treatments
        (id, plan_id, treatment_name, amount, units, timing_note, rna_id, plasmid_id, injection_mix, treatment_notes)
      values
        (:id, :pid, :name, :amt, :units, :note, :rna_id, :plasmid_id, :mix, :treat_notes)
      on conflict do nothing
    """)
    n = 0
    with ENGINE.begin() as cx:
        for r in rows:
            cx.execute(sql, dict(
                id=str(uuid.uuid4()),
                pid=plan_id,
                name=r.get("treatment_name"),
                amt=r.get("amount"),
                units=r.get("units"),
                note=r.get("timing_note"),
                rna_id=r.get("rna_id"),
                plasmid_id=r.get("plasmid_id"),
                mix=r.get("injection_mix"),
                treat_notes=r.get("treatment_notes"),
            ))
            n += 1
    return n

# ---------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------
if "geno_rows" not in st.session_state:  st.session_state.geno_rows = []
if "tx_rows"   not in st.session_state:  st.session_state.tx_rows   = []
if "fish_swap" not in st.session_state:  st.session_state.fish_swap = False
if "mom_code"  not in st.session_state:  st.session_state.mom_code  = None
if "dad_code"  not in st.session_state:  st.session_state.dad_code  = None

# ---------------------------------------------------------------------
# Header inputs
# ---------------------------------------------------------------------
user_default = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
created_by   = st.text_input("Created by", value=user_default)
plan_date    = st.date_input("Cross date", value=date.today()+timedelta(days=1), min_value=date.today()-timedelta(days=7))

# ---------------------------------------------------------------------
# Step 1 — Mom/Dad selection (fish-first)
# ---------------------------------------------------------------------
st.subheader("Step 1 — Select parents (fish)")

fish_df = _load_fish_overview()
if fish_df.empty:
    st.info("No fish in overview.")
    st.stop()

# Filter + table
fq = st.text_input("Filter fish (code/name/nickname/genotype/background)", "")
base = fish_df.copy()
if fq.strip():
    f = fq.lower().strip()
    mask = (
        base["fish_code"].str.lower().str.contains(f)
        | base["name"].fillna("").str.lower().str.contains(f)
        | base["nickname"].fillna("").str.lower().str.contains(f)
        | base["genotype"].fillna("").str.lower().str.contains(f)
        | base["genetic_background"].fillna("").str.lower().str.contains(f)
    )
    base = base.loc[mask].copy()

base["✓ Select"] = False
view = base[["✓ Select","fish_code","name","nickname","genotype","genetic_background","stage","date_birth","age_days","created_at"]]
cfg = {"✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False)}
for c in view.columns:
    if c != "✓ Select":
        cfg[c] = st.column_config.TextColumn(disabled=True)

sel = st.data_editor(view, use_container_width=True, hide_index=True, column_config=cfg, num_rows="fixed", key="fish_picker")
picked = [r["fish_code"] for _, r in sel.iterrows() if r["✓ Select"]][:2]

# Keep selections stable across reruns, support swap
if not st.session_state.fish_swap:
    if len(picked) >= 1: st.session_state.mom_code = picked[0]
    if len(picked) >= 2: st.session_state.dad_code = picked[1]
else:
    st.session_state.fish_swap = False

mom_code = st.session_state.mom_code
dad_code = st.session_state.dad_code

c1, c2, c3 = st.columns([1,1,5])
with c1:
    if st.button("Swap Mom/Dad", use_container_width=True, disabled=not (mom_code and dad_code)):
        st.session_state.mom_code, st.session_state.dad_code = dad_code, mom_code
        st.session_state.fish_swap = True
        mom_code, dad_code = st.session_state.mom_code, st.session_state.dad_code
with c2:
    if st.button("Clear Mom/Dad", use_container_width=True):
        st.session_state.mom_code = None
        st.session_state.dad_code = None
        mom_code, dad_code = None, None

st.markdown(f"**Mom (A) — fish:** {mom_code or '—'}")
st.markdown(f"**Dad (B) — fish:** {dad_code or '—'}")

# ---------------------------------------------------------------------
# Step 2 — Genotype inheritance from parents
# ---------------------------------------------------------------------
st.subheader("Step 2 — Genotype inheritance")

par_df = _load_fish_alleles_by_codes([c for c in [mom_code, dad_code] if c])
if par_df.empty:
    st.info("Pick parent fish above to preview their genotype elements.")
else:
    def _who(code: str) -> str:
        if code and mom_code and code == mom_code: return "mom"
        if code and dad_code and code == dad_code: return "dad"
        return "?"

    view = par_df.copy()
    view["parent"] = view["fish_code"].apply(_who)
    view["inherit"] = True
    show = view.rename(columns={
        "fish_code":"fish","transgene_base_code":"base_code","allele_number":"allele","allele_nickname":"nickname"
    })[["inherit","parent","fish","base_code","allele","zygosity","nickname"]]

    sel_tbl = st.data_editor(
        show, use_container_width=True, hide_index=True, num_rows="fixed",
        column_config={
            "inherit": st.column_config.CheckboxColumn("inherit", default=True),
            "parent": st.column_config.TextColumn(disabled=True),
            "fish":   st.column_config.TextColumn(disabled=True),
            "base_code": st.column_config.TextColumn(disabled=True),
            "allele": st.column_config.NumberColumn(disabled=True),
            "zygosity": st.column_config.TextColumn(disabled=True),
            "nickname": st.column_config.TextColumn(disabled=True),
        },
        key="parent_alleles",
    )

    c_apply, c_clear = st.columns([1,1])
    with c_apply:
        if st.button("Use selected parental alleles in plan", type="primary", use_container_width=True):
            chosen = []
            for _, r in sel_tbl.iterrows():
                if r.get("inherit"):
                    chosen.append(dict(base_code=r["base_code"], allele_number=int(r["allele"]), zygosity_planned=None))
            st.session_state.geno_rows = chosen
            st.success(f"Applied {len(chosen)} allele(s) to the plan.")
    with c_clear:
        if st.button("Clear planned genotype list", use_container_width=True):
            st.session_state.geno_rows = []
            st.info("Cleared planned genotype list.")

if st.session_state.geno_rows:
    st.caption("**Planned genotype rows (will be saved):**")
    st.dataframe(pd.DataFrame(st.session_state.geno_rows), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------
# Step 3 — Optional treatments (RNAs / Plasmids)
# ---------------------------------------------------------------------
st.subheader("Step 3 — Optional treatments")

# Tabs
rna_tab, pla_tab = st.tabs(["RNAs", "Plasmids"])

with rna_tab:
    rna_df = _load_rna_registry()
    if rna_df.empty:
        st.caption("_No RNAs in registry yet._")
    else:
        rflt = st.text_input("Filter RNAs (code/nickname/vendor/lot)", key="rna_filter")
        base = rna_df.copy()
        if rflt.strip():
            f = rflt.lower().strip()
            def _contains(s): return s.fillna("").astype(str).str.lower().str.contains(f)
            mask = _contains(base["rna_code"]) | _contains(base["rna_nickname"]) | _contains(base["vendor"]) | _contains(base["lot_number"])
            base = base.loc[mask].copy()

        base["✓ Select"] = False
        disp = base.rename(columns={"rna_code":"RNA code","rna_nickname":"nickname"})[["✓ Select","RNA code","nickname","vendor","lot_number","notes","created_at"]]
        cfg = {"✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False)}
        for c in disp.columns:
            if c != "✓ Select": cfg[c] = st.column_config.TextColumn(disabled=True)

        sel_rna = st.data_editor(disp, use_container_width=True, hide_index=True, column_config=cfg, num_rows="fixed", key="rna_picker")

        mix_rna   = st.text_input("Injection mix (applies to added RNAs)", key="mix_rna")
        notes_rna = st.text_input("Treatment notes (applies to added RNAs)", key="notes_rna")

        c1, c2 = st.columns([1,1])
        with c1:
            if st.button("Add selected RNAs", type="primary", use_container_width=True):
                picked_rows = sel_rna[sel_rna["✓ Select"]]
                before = len(st.session_state.tx_rows)
                for _, row in picked_rows.iterrows():
                    st.session_state.tx_rows.append(dict(
                        treatment_name=f"RNA:{row['RNA code']}{(' '+row['nickname']) if row['nickname'] else ''}",
                        amount=None, units=None,
                        timing_note=f"vendor={row['vendor']} lot={row['lot_number']}".strip(),
                        rna_id=rna_df.loc[rna_df["rna_code"]==row["RNA code"]].iloc[0]["id"],
                        plasmid_id=None,
                        injection_mix=(mix_rna or None),
                        treatment_notes=(notes_rna or None),
                    ))
                st.success(f"Added {len(st.session_state.tx_rows)-before} RNA treatment(s).")
        with c2:
            with st.expander("Add / edit an RNA entry"):
                rc1, rc2, rc3 = st.columns([1,1,1])
                with rc1:
                    r_code = st.text_input("RNA code *", key="rna_code_in")
                    r_nick = st.text_input("Nickname", key="rna_nick_in")
                with rc2:
                    r_vendor = st.text_input("Vendor", key="rna_vendor_in")
                    r_lot    = st.text_input("Lot number", key="rna_lot_in")
                with rc3:
                    r_notes  = st.text_input("Notes", key="rna_notes_in")
                if st.button("Save RNA entry", disabled=not bool((r_code or "").strip())):
                    _upsert_rna(r_code, r_nick, r_vendor, r_lot, r_notes, created_by)
                    st.success(f"Saved RNA: {r_code}")
                    st.experimental_rerun()

with pla_tab:
    pla_df = _load_plasmid_registry()
    if pla_df.empty:
        st.caption("_No plasmids in registry yet._")
    else:
        pflt = st.text_input("Filter plasmids (code/nickname/backbone/insert/vendor/lot)", key="plasmid_filter")
        base = pla_df.copy()
        if pflt.strip():
            f = pflt.lower().strip()
            def _contains(s): return s.fillna("").astype(str).str.lower().str.contains(f)
            mask = (_contains(base["plasmid_code"]) | _contains(base["plasmid_nickname"])
                    | _contains(base["backbone"])   | _contains(base["insert_desc"])
                    | _contains(base["vendor"])     | _contains(base["lot_number"]))
            base = base.loc[mask].copy()

        base["✓ Select"] = False
        disp = base.rename(columns={"plasmid_code":"Plasmid code","plasmid_nickname":"nickname"})[[
            "✓ Select","Plasmid code","nickname","backbone","insert_desc","vendor","lot_number","notes","created_at"
        ]]
        cfg = {"✓ Select": st.column_config.CheckboxColumn("✓ Select", default=False)}
        for c in disp.columns:
            if c != "✓ Select": cfg[c] = st.column_config.TextColumn(disabled=True)

        sel_pla = st.data_editor(disp, use_container_width=True, hide_index=True, column_config=cfg, num_rows="fixed", key="plasmid_picker")

        mix_pla   = st.text_input("Injection mix (applies to added plasmids)", key="mix_pla")
        notes_pla = st.text_input("Treatment notes (applies to added plasmids)", key="notes_pla")

        c1, c2 = st.columns([1,1])
        with c1:
            if st.button("Add selected plasmids", type="primary", use_container_width=True):
                picked_rows = sel_pla[sel_pla["✓ Select"]]
                before = len(st.session_state.tx_rows)
                for _, row in picked_rows.iterrows():
                    st.session_state.tx_rows.append(dict(
                        treatment_name=f"Plasmid:{row['Plasmid code']}{(' '+row['nickname']) if row['nickname'] else ''}",
                        amount=None, units=None,
                        timing_note=f"backbone={row['backbone']} insert={row['insert_desc']} vendor={row['vendor']} lot={row['lot_number']}".strip(),
                        rna_id=None,
                        plasmid_id=pla_df.loc[pla_df["plasmid_code"]==row["Plasmid code"]].iloc[0]["id"],
                        injection_mix=(mix_pla or None),
                        treatment_notes=(notes_pla or None),
                    ))
                st.success(f"Added {len(st.session_state.tx_rows)-before} plasmid treatment(s).")
        with c2:
            with st.expander("Add / edit a plasmid entry"):
                pc1, pc2, pc3 = st.columns([1,1,1])
                with pc1:
                    p_code = st.text_input("Plasmid code *", key="pla_code_in")
                    p_nick = st.text_input("Nickname", key="pla_nick_in")
                with pc2:
                    p_back = st.text_input("Backbone", key="pla_back_in")
                    p_ins  = st.text_input("Insert description", key="pla_ins_in")
                with pc3:
                    p_vendor = st.text_input("Vendor", key="pla_vendor_in")
                    p_lot    = st.text_input("Lot number", key="pla_lot_in")
                p_notes = st.text_area("Notes", key="pla_notes_in")
                if st.button("Save plasmid entry", disabled=not bool((p_code or "").strip())):
                    _upsert_plasmid(p_code, p_nick, p_back, p_ins, p_vendor, p_lot, p_notes, created_by)
                    st.success(f"Saved plasmid: {p_code}")
                    st.experimental_rerun()

st.markdown("**Selected treatments for this plan**")
if st.session_state.tx_rows:
    txdf = pd.DataFrame(st.session_state.tx_rows)
    if "rna_id" in txdf.columns or "plasmid_id" in txdf.columns:
        txdf = txdf.assign(reagent=lambda d: d.apply(lambda r: ("RNA" if r.get("rna_id") else ("Plasmid" if r.get("plasmid_id") else "")), axis=1))
        cols = [c for c in ["reagent","treatment_name","injection_mix","treatment_notes","amount","units","timing_note"] if c in txdf.columns]
    else:
        cols = [c for c in ["treatment_name","injection_mix","treatment_notes","amount","units","timing_note"] if c in txdf.columns]
    st.dataframe(txdf[cols], hide_index=True, use_container_width=True)
    if st.button("Clear all treatments", use_container_width=True):
        st.session_state.tx_rows = []
        st.info("Cleared treatments.")
else:
    st.caption("_No treatments selected yet._")

# ---------------------------------------------------------------------
# Step 4 — Preview
# ---------------------------------------------------------------------
st.subheader("Step 4 — Preview")
cols = st.columns(2)
with cols[0]:
    st.markdown("**Parents**")
    st.write(f"Mom (fish): {mom_code or '—'}")
    st.write(f"Dad (fish): {dad_code or '—'}")
with cols[1]:
    st.markdown("**Genotype plan**")
    if st.session_state.geno_rows:
        st.write(", ".join([f"{r['base_code']}[{r['allele_number']}] {r.get('zygosity_planned') or ''}".strip()
                            for r in st.session_state.geno_rows]))
    else:
        st.write("—")

st.markdown("**Treatments**")
if st.session_state.tx_rows:
    def _fmt_t(t: dict) -> str:
        parts = [t["treatment_name"]]
        if t.get("injection_mix"):   parts.append(f"(mix={t['injection_mix']})")
        if t.get("treatment_notes"): parts.append(f"[{t['treatment_notes']}]")
        if t.get("timing_note"):     parts.append(f"{{{t['timing_note']}}}")
        return " ".join(parts)
    st.write(" • ".join(_fmt_t(t) for t in st.session_state.tx_rows))
else:
    st.write("—")

st.divider()

# ---------------------------------------------------------------------
# Step 4½ — Name this cross  (auto name + reliable nickname behavior)
# ---------------------------------------------------------------------
st.subheader("Step 4½ — Name this cross")

def _suggest_cross_name() -> str:
    """Deterministic, human-readable name from current selections."""
    mom = mom_code or "—"
    dad = dad_code or "—"

    # Genotype list in stable order: base[allele]
    geno_rows = st.session_state.get("geno_rows", []) or []
    geno_parts = [
        f"{(r.get('base_code') or '').strip()}[{int(r.get('allele_number'))}]"
        for r in geno_rows
        if r.get("base_code") and r.get("allele_number") is not None
    ]
    geno_txt = ", ".join(geno_parts)

    # Treatment short labels from treatment_name (after ':')
    tx_rows = st.session_state.get("tx_rows", []) or []
    tx_labels = []
    for t in tx_rows:
        nm = (t.get("treatment_name") or "").strip()
        short = nm.split(":")[-1].strip() if ":" in nm else nm
        if short:
            tx_labels.append(short)
    tx_txt = "; ".join(tx_labels)

    parts = [f"{mom} × {dad}"]
    if geno_txt: parts.append(geno_txt)
    if tx_txt:   parts.append(tx_txt)
    return "; ".join(parts)

# Compute the current auto name from live selections
auto_title = _suggest_cross_name()
st.markdown(f"**Auto name:** {auto_title}")

# ---------- Nickname state machine ----------
# Fields in session:
#   plan_nick ................. current nickname string
#   plan_nick_mode ............ 'auto' or 'user'
#   plan_auto_title_prev ...... last auto title we computed (to break '— × —' lock)
st.session_state.setdefault("plan_nick", "")
st.session_state.setdefault("plan_nick_mode", "auto")     # 'auto' or 'user'
st.session_state.setdefault("plan_auto_title_prev", None)

# If we were in USER mode but the nickname still equals the previous auto title,
# that means the user never truly edited it; switch back to AUTO so it can update.
if (st.session_state["plan_nick_mode"] == "user"
    and st.session_state["plan_auto_title_prev"] is not None
    and st.session_state["plan_nick"] == st.session_state["plan_auto_title_prev"]):
    st.session_state["plan_nick_mode"] = "auto"

# AUTO mode: always sync nickname to auto_title
if st.session_state["plan_nick_mode"] == "auto":
    st.session_state["plan_nick"] = auto_title

# Render editable nickname
prev_nick = st.session_state["plan_nick"]
new_nick = st.text_input(
    "Cross nickname",
    value=prev_nick,
    key="plan_nick_input_stable",
)

# Detect user edits and toggle mode
if new_nick != prev_nick:
    # If user cleared it or made it exactly equal to auto, go back to AUTO mode
    if not new_nick.strip() or new_nick.strip() == auto_title:
        st.session_state["plan_nick_mode"] = "auto"
        st.session_state["plan_nick"] = auto_title
    else:
        st.session_state["plan_nick_mode"] = "user"
        st.session_state["plan_nick"] = new_nick

# Optional note field (kept as-is)
st.session_state.setdefault("plan_note", "")
st.session_state["plan_note"] = st.text_area(
    "Optional note",
    value=st.session_state["plan_note"],
    key="plan_note_input_stable",
)

# Remember current auto title for the next rerun
st.session_state["plan_auto_title_prev"] = auto_title

st.caption("Nickname auto-follows the generated name until you edit it. Clear it to return to auto-follow.")
st.divider()

# =====================================================================
# Step 4¾ — Potential matches (parents + genotype + treatments)
# =====================================================================
st.subheader("Step 4¾ — Potential matches")

# Resolve parent IDs once (also reused in Step 5)
mom_id = _fish_id_by_code(mom_code)
dad_id = _fish_id_by_code(dad_code)

# FYI: duplicate definitions on the same date (informational only)
if mom_id and dad_id:
    with ENGINE.begin() as cx:
        dup = cx.execute(text("""
            select count(*) from public.cross_plans
            where plan_date = :d
              and mother_fish_id = :mf
              and father_fish_id = :ff
        """), {"d": plan_date, "mf": mom_id, "ff": dad_id}).scalar()
    if dup and dup > 0:
        st.info(f"FYI: {int(dup)} existing definition(s) for these parents on {plan_date}. Saving will add another.")

# Current signatures
cur_geno_sig = _geno_signature(st.session_state.get("geno_rows", []))
cur_tx_sig   = _tx_signature(st.session_state.get("tx_rows", []))

# Fetch previous definitions for these parents (includes human-readable + signatures)
matches_df = _find_plan_matches(mom_id, dad_id)

if matches_df.empty:
    st.caption("No saved cross definitions for these parents yet.")
    st.session_state["reuse_plan_id"] = None
else:
    # Exact = same parents + same genotype + same treatments (date ignored)
    matches_df["is_match"] = (
        matches_df["geno_sig"].fillna("") == cur_geno_sig
    ) & (
        matches_df["tx_sig"].fillna("")   == cur_tx_sig
    )

    exact  = matches_df[matches_df["is_match"]].copy()
    others = matches_df[~matches_df["is_match"]].copy()

    if not exact.empty:
        st.caption("Exact matches by parents + genotype + treatments (date ignored):")

        # Build table with Reuse checkbox FIRST
        table = exact[[
            "id","plan_title","plan_nickname","created_by","genotype_plan","treatments_plan","plan_date","created_at"
        ]].rename(columns={
            "plan_title":"Name",
            "plan_nickname":"Nickname",
            "created_by":"By",
            "genotype_plan":"Genotype",
            "treatments_plan":"Treatments",
            "plan_date":"Date",
            "created_at":"Created",
        }).reset_index(drop=True)

        # Convert Date/Created to readable strings if driver returned epoch ms
        def _to_dt_col(s: pd.Series) -> pd.Series:
            if pd.api.types.is_datetime64_any_dtype(s):
                dt = s
            else:
                try:
                    dt = pd.to_datetime(s, unit="ms", utc=True, errors="coerce")
                except Exception:
                    dt = pd.to_datetime(s, utc=True, errors="coerce")
            return dt.dt.tz_convert(None)

        try:
            table["Date"]    = _to_dt_col(table["Date"]).dt.strftime("%Y-%m-%d")
            table["Created"] = _to_dt_col(table["Created"]).dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            # If already plain strings, leave as-is
            pass

        table["Reuse"] = False  # default unchecked
        ordered = ["Reuse","Name","Nickname","By","Genotype","Treatments","Date","Created"]
        disp = table.set_index("id")[ordered]

        sel_tbl = st.data_editor(
            disp,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "Reuse":      st.column_config.CheckboxColumn("Reuse", default=False, help="Select one to reuse"),
                "Name":       st.column_config.TextColumn(disabled=True),
                "Nickname":   st.column_config.TextColumn(disabled=True),
                "By":         st.column_config.TextColumn(disabled=True),
                "Genotype":   st.column_config.TextColumn(disabled=True),
                "Treatments": st.column_config.TextColumn(disabled=True),
                "Date":       st.column_config.TextColumn(disabled=True),
                "Created":    st.column_config.TextColumn(disabled=True),
            },
            key="reuse_table_v3",
        )

        # Single-select: accept the first checked row
        reuse_ids = [idx for idx, r in sel_tbl.iterrows() if r.get("Reuse")]
        st.session_state["reuse_plan_id"] = reuse_ids[0] if reuse_ids else None

    else:
        st.caption("No exact matches by genotype + treatments. Here are other definitions for these parents:")
        show_others = others[[
            "plan_title","plan_nickname","created_by","genotype_plan","treatments_plan","plan_date","created_at"
        ]].rename(columns={
            "plan_title":"Name","plan_nickname":"Nickname","created_by":"By",
            "genotype_plan":"Genotype","treatments_plan":"Treatments",
            "plan_date":"Date","created_at":"Created",
        })
        # Try to format dates if needed
        for col, fmt in (("Date","%Y-%m-%d"), ("Created","%Y-%m-%d %H:%M")):
            try:
                show_others[col] = pd.to_datetime(show_others[col], unit="ms", utc=True, errors="ignore").dt.tz_convert(None).dt.strftime(fmt)
            except Exception:
                pass
        st.dataframe(show_others, hide_index=True, use_container_width=True)
        st.session_state["reuse_plan_id"] = None

st.divider()

# =====================================================================
# Step 5 — Save
# =====================================================================
st.subheader("Step 5 — Save")

# Two actions: save NEW or use EXISTING (if chosen)
c_save, c_use = st.columns([1,1])

_require_ok = (created_by and plan_date and mom_code and dad_code and mom_code != dad_code)

with c_save:
    save_btn = st.button(
        "Save NEW cross definition",
        type="primary",
        use_container_width=True,
        disabled=not _require_ok
    )
with c_use:
    use_btn = st.button(
        "Use EXISTING definition",
        use_container_width=True,
        disabled=not bool(st.session_state.get("reuse_plan_id"))
    )

if not _require_ok:
    st.info("Provide **Created by**, **date**, and two **different** parent fish to enable saving a NEW definition.")

# Reuse (no DB write; guide to page 07)
if use_btn and st.session_state.get("reuse_plan_id"):
    st.success(f"Using existing cross {st.session_state['reuse_plan_id']}. Go to page **07 — Schedule Cross Runs** and select this ID.")

# Save NEW definition
if save_btn:
    pid = _insert_cross_plan(
        plan_date=plan_date,
        created_by=created_by,
        note=(st.session_state.get("plan_note") or "").strip() or None,
        mother_fish_id=_fish_id_by_code(mom_code),
        father_fish_id=_fish_id_by_code(dad_code),
        plan_title=_suggest_cross_name(),  # use the auto-generated name at save time
        plan_nickname=(st.session_state.get("plan_nick") or "").strip() or _suggest_cross_name(),
    )

    if not pid:
        st.error("Could not create plan.")
    else:
        n_g = _upsert_plan_genotypes(pid, st.session_state.get("geno_rows", []))
        n_t = _upsert_plan_treatments(pid, st.session_state.get("tx_rows", []))
        st.success(f"Saved cross {pid}  •  genotype rows: {n_g}  •  treatments: {n_t}")