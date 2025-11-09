# carp_app/ui/pages/026_🐣_new_fish_from_treated_clutch.py
from __future__ import annotations

import sys, pathlib, os, re
from typing import List
from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import ARRAY, TEXT

# ── repo path ────────────────────────────────────────────────────────────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── auth + engine ────────────────────────────────────────────────────────────
from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:  # fallback for dev shells
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine
from carp_app.lib.time import utc_now

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🐣 New fish from treated clutch", page_icon="🐣", layout="wide")
st.title("🐣 New fish from treated clutch")

# ── objects/views ────────────────────────────────────────────────────────────
V_TCLUTCH = "public.v_treated_clutches"

# ── helpers ──────────────────────────────────────────────────────────────────
def _fusion_context_for_bases(bases: List[str]) -> pd.DataFrame:
    """
    Given base codes (plasmid codes), return per-base fusion context:
    fusion_names, fluor list, tag list.
    """
    if not bases:
        return pd.DataFrame(columns=["base_code","fusion_names","fluors","tags"])
    with engine().begin() as cx:
        q = text("""
          WITH bases AS (
            SELECT unnest(:bases) AS base_code
          )
          SELECT
            b.base_code,
            COALESCE(string_agg(DISTINCT f.fusion_name, ', ' ORDER BY f.fusion_name), '') AS fusion_names,
            COALESCE(string_agg(DISTINCT fl.fluor_name, ', ' ORDER BY fl.fluor_name), '') AS fluors,
            COALESCE(string_agg(DISTINCT tg.tag_name,   ', ' ORDER BY tg.tag_name),   '') AS tags
          FROM bases b
          LEFT JOIN public.plasmids p               ON p.code = b.base_code
          LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
          LEFT JOIN public.fusions f                ON f.id = jpf.fusion_id
          LEFT JOIN public.fluors  fl               ON fl.id = f.fluor_id
          LEFT JOIN public.tags    tg               ON tg.id = f.tag_id
          GROUP BY b.base_code
        """).bindparams(bindparam("bases", value=bases, type_=ARRAY(TEXT())))
        df = pd.read_sql(q, cx)
    return df

def _exists_view(qname: str) -> bool:
    s, n = qname.split(".", 1)
    q = text("""
      SELECT 1 FROM information_schema.views WHERE table_schema=:s AND table_name=:n
      UNION ALL SELECT 1 FROM pg_catalog.pg_matviews WHERE schemaname=:s AND matviewname=:n
      LIMIT 1
    """)
    with engine().begin() as cx:
        return cx.execute(q, {"s": s, "n": n}).first() is not None

def _safe_read(sql, params=None) -> pd.DataFrame:
    with engine().begin() as cx:
        return pd.read_sql(sql if hasattr(sql, "compile") else text(sql), cx, params=params or {})

def _canon_nick(s: str) -> str:
    s = (s or "").strip()
    return re.sub(r"\.0+$", "", s) if re.fullmatch(r"\d+(?:\.0+)?", s) else s

def _norm_str(v) -> str:
    if v is None: return ""
    s = str(v).strip().lower()
    return " ".join(s.split())

def _identity_key(row: pd.Series) -> str:
    parts = [
        str(row.get("birthday") or "").strip(),
        _norm_str(row.get("genetic_background")),
        _norm_str(row.get("line_building_stage")),
        _norm_str(row.get("nickname")),
    ]
    return " | ".join(parts)

def _ensure_ft_markers(ft_code: str, created_by: str):
    with engine().begin() as cx:
        cx.execute(text("""
          INSERT INTO public.treatments_fluorescent (ft_code, ft_text, created_by)
          VALUES (:c, ''::text, :by) ON CONFLICT (ft_code) DO NOTHING
        """), {"c": ft_code, "by": created_by})
        cx.execute(text("SELECT public.ensure_ft_markers_from_transgene(:ft)"), {"ft": ft_code})

# Parse base/name pairs like "BASE(nick)" from genotype strings
_BASE_NAME_RE = re.compile(r"\b([A-Za-z0-9\-]+)\s*\(\s*([^)]+?)\s*\)")
# Parse base codes (treatment bases etc): p<letters><digits> or UPPER-UPPER pattern with -digits
_BASE_ONLY_RE = re.compile(r"\b(?:p[A-Za-z]{2,}\d{2,}|[A-Z]{2,}-\d{1,})\b")

def parse_transgenes_from_genotype(s: str) -> List[tuple[str,str]]:
    out: List[tuple[str,str]] = []
    if not s: return out
    for m in _BASE_NAME_RE.finditer(s):
        base, nick = m.group(1).strip(), m.group(2).strip()
        if base: out.append((base, nick))
    return out

def parse_bases_from_text(s: str) -> List[str]:
    if not s: return []
    return sorted(set(_BASE_ONLY_RE.findall(s)))

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Pick a treated clutch (group row)
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("1) Pick a treated clutch")

if not _exists_view(V_TCLUTCH):
    st.error(f"Missing view: {V_TCLUTCH}"); st.stop()

c1, c2 = st.columns([3,1])
with c1:
    q = st.text_input("Search (treated_clutch_code / clutch_code / genotype / tx)", "")
with c2:
    lim = int(st.number_input("Limit", min_value=50, max_value=2000, value=300, step=50))

params = {"lim": lim}
where = []
if q.strip():
    params["q"] = f"%{q.strip()}%"
    where.append("""
      (treated_clutch_code ILIKE :q OR clutch_code ILIKE :q OR
       COALESCE(clutch_genotype_pretty,'') ILIKE :q OR
       COALESCE(treatments_names_group,'') ILIKE :q OR
       COALESCE(treatment_genotype_group,'') ILIKE :q)
    """)
wsql = ("WHERE " + " AND ".join(where)) if where else ""

groups = _safe_read(text(f"""
  SELECT treated_clutch_code, clutch_code, clutch_birthday,
         COALESCE(clutch_genotype_pretty,'')    AS clutch_genotype_pretty,
         COALESCE(treatments_names_group,'')    AS treatments_names_group,
         COALESCE(treatment_genotype_group,'')  AS treatment_genotype_group
  FROM {V_TCLUTCH}
  {wsql}
  ORDER BY clutch_birthday DESC NULLS LAST, treated_clutch_code
  LIMIT :lim
"""), params)

groups.insert(0, "✓", False)
pick = st.data_editor(
    groups,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed", height=260,
    column_config={
        "✓": st.column_config.CheckboxColumn("✓", default=False),
        "treated_clutch_code": st.column_config.TextColumn("treated_clutch_code", disabled=True),
        "clutch_code": st.column_config.TextColumn("clutch_code", disabled=True),
        "clutch_birthday": st.column_config.DateColumn("birthday", disabled=True, format="YYYY-MM-DD"),
        "clutch_genotype_pretty": st.column_config.TextColumn("offspring genotype", disabled=True, width="large"),
        "treatments_names_group": st.column_config.TextColumn("treatments", disabled=True, width="large"),
        "treatment_genotype_group": st.column_config.TextColumn("tx → genotype", disabled=True, width="large"),
    },
    key="new_fish_from_tclutch_picker",
)

chosen = pick.loc[pick["✓"]].head(1)
if chosen.empty:
    st.info("Select a treated clutch group to continue.")
    st.stop()

g = chosen.iloc[0]
g_code  = str(g["treated_clutch_code"])
c_code  = str(g["clutch_code"] or "")
g_bday  = g["clutch_birthday"]
g_og    = str(g["clutch_genotype_pretty"] or "")
g_tx    = str(g["treatment_genotype_group"] or "")
st.success(f"Selected group **{g_code}** (clutch **{c_code or '—'}**)")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Inherit fields (checkbox tables)
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("2) Inherit fields")
st.caption("Pick exactly one option in each table (defaults pre-selected).")

# Background suggestions
with engine().begin() as cx:
    bg_df = pd.read_sql(text("""
      WITH b AS (
        SELECT COALESCE(NULLIF(genetic_background,''),'(blank)') AS bg
        FROM public.fish
      )
      SELECT DISTINCT bg, (bg='(blank)') AS is_blank
      FROM b
      ORDER BY is_blank, bg
    """), cx)
bg_opts = bg_df["bg"].astype(str).tolist() if not bg_df.empty else ["(blank)"]

cA, cB, cC = st.columns(3)

# Birthday chooser
with cA:
    st.markdown("**Birthday**")
    bday_rows = pd.DataFrame([
        {"✓": True,  "option": "clutch_birthday", "date": pd.to_datetime(g_bday).date() if pd.notna(g_bday) else date.today()},
        {"✓": False, "option": "today",            "date": date.today()},
    ])
    bday_sel = st.data_editor(
        bday_rows, hide_index=True, use_container_width=True, num_rows="fixed",
        column_config={
            "✓":     st.column_config.CheckboxColumn("✓", default=False),
            "option":st.column_config.TextColumn("option", disabled=True),
            "date":  st.column_config.DateColumn("date", disabled=True, format="YYYY-MM-DD"),
        },
        key="inherit_bday_table",
    )
    pick_bday = bday_sel.loc[bday_sel["✓"]].head(1)
    birthday_value = pick_bday["date"].iloc[0] if not pick_bday.empty else bday_rows["date"].iloc[0]

# Background chooser
with cB:
    st.markdown("**Genetic background**")
    bg_rows = pd.DataFrame({"✓":[False]*len(bg_opts), "background": bg_opts})
    if "casper" in bg_rows["background"].values:
        bg_rows.loc[bg_rows["background"].eq("casper"), "✓"] = True
    else:
        bg_rows.loc[bg_rows.index.min(), "✓"] = True
    bg_sel = st.data_editor(
        bg_rows, hide_index=True, use_container_width=True, num_rows="fixed", height=220,
        column_config={
            "✓":         st.column_config.CheckboxColumn("✓", default=False),
            "background":st.column_config.TextColumn("background", disabled=True),
        },
        key="inherit_bg_table",
    )
    pick_bg = bg_sel.loc[bg_sel["✓"]].head(1)
    bg_value = pick_bg["background"].iloc[0] if not pick_bg.empty else bg_rows["background"].iloc[0]
    bg_value = "" if bg_value == "(blank)" else bg_value

# Stage chooser with fixed options + custom
with cC:
    st.markdown("**Line-building stage**")
    stage_fixed = [
        "injected",
        "Founder (P0)",
        "F1 incross",
        "F1 outcross",
        "F2",
        "Stable",
        "(custom)"
    ]
    stg_rows = pd.DataFrame({"✓":[False]*len(stage_fixed), "stage": stage_fixed})
    # default to Founder (P0)
    stg_rows.loc[stg_rows["stage"].eq("Founder (P0)"), "✓"] = True
    stg_sel = st.data_editor(
        stg_rows, hide_index=True, use_container_width=True, num_rows="fixed", height=220,
        column_config={
            "✓":    st.column_config.CheckboxColumn("✓", default=False),
            "stage":st.column_config.TextColumn("stage", disabled=True),
        },
        key="inherit_stage_table",
    )
    pick_stage = stg_sel.loc[stg_sel["✓"]].head(1)
    stage_value = pick_stage["stage"].iloc[0] if not pick_stage.empty else "Founder (P0)"
    custom_stage = st.text_input("Custom stage (if '(custom)' selected)", value="")
    if stage_value == "(custom)":
        stage_value = custom_stage.strip()

st.markdown("—")

# Alleles to inherit
st.subheader("Alleles to inherit")

# Parse alleles from clutch genotype (base + nickname)
clutch_tgs = parse_transgenes_from_genotype(g_og)  # [(base, nick), ...]
clutch_bases = [b for (b, _) in clutch_tgs]
# Parse treatment bases (base only)
tx_bases = parse_bases_from_text(g_tx)

# Fetch fusion context once for all bases we might show
ctx = _fusion_context_for_bases(sorted(set(clutch_bases + tx_bases)))

# Build clutch table (inherit existing alleles)
if clutch_tgs:
    tg_rows = pd.DataFrame(
        [{"✓": True, "base_code": b, "allele_nickname": n} for (b, n) in clutch_tgs]
    )
    tg_rows = tg_rows.merge(ctx, how="left", on="base_code")
else:
    tg_rows = pd.DataFrame(columns=["✓","base_code","allele_nickname","fusion_names","fluors","tags"])

tg_sel = st.data_editor(
    tg_rows if not tg_rows.empty else pd.DataFrame([{"✓": False, "base_code":"", "allele_nickname":"", "fusion_names":"", "fluors":"", "tags":""}]),
    hide_index=True, use_container_width=True, num_rows="dynamic",
    column_config={
        "✓":               st.column_config.CheckboxColumn("✓", default=False),
        "base_code":       st.column_config.TextColumn("Transgene base", disabled=True),
        "allele_nickname": st.column_config.TextColumn("Allele nickname", disabled=True),
        "fusion_names":    st.column_config.TextColumn("Fusions", disabled=True),
        "fluors":          st.column_config.TextColumn("Fluors", disabled=True),
        "tags":            st.column_config.TextColumn("Tags", disabled=True),
    },
    key="inherit_clutch_alleles_table",
)
inherit_clutch = tg_sel.loc[tg_sel.get("✓", pd.Series(False)).fillna(False)]

# Build treatment table (select bases to create a NEW allele, no nickname)
if tx_bases:
    tx_rows = pd.DataFrame([{"✓": False, "base_code": b} for b in tx_bases])
    tx_rows = tx_rows.merge(ctx, how="left", on="base_code")
else:
    tx_rows = pd.DataFrame(columns=["✓","base_code","fusion_names","fluors","tags"])

tx_sel = st.data_editor(
    tx_rows if not tx_rows.empty else pd.DataFrame([{"✓": False, "base_code": "", "fusion_names":"", "fluors":"", "tags":""}]),
    hide_index=True, use_container_width=True, num_rows="dynamic",
    column_config={
        "✓":          st.column_config.CheckboxColumn("✓", default=False),
        "base_code":  st.column_config.TextColumn("Treatment base code", disabled=True),
        "fusion_names": st.column_config.TextColumn("Fusions", disabled=True),
        "fluors":       st.column_config.TextColumn("Fluors", disabled=True),
        "tags":         st.column_config.TextColumn("Tags", disabled=True),
    },
    key="inherit_treatment_bases_table",
)
inherit_tx = tx_sel.loc[tx_sel.get("✓", pd.Series(False)).fillna(False)]

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Preview (auto-fields & tank)
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("3) Preview (auto-fields & tank)")

# Exactly one fish
seed = pd.DataFrame([{
    "✓ Create": True,
    "nickname": "",
    "birthday": pd.to_datetime(birthday_value).date() if hasattr(birthday_value, "date") else birthday_value,
    "genetic_background": bg_value,
    "line_building_stage": stage_value,
    "description": "",
    "zygosity": "",
}])

st.caption("Edit any fields below (exactly one fish will be created).")
editor = st.data_editor(
    seed, hide_index=True, use_container_width=True, num_rows="fixed",
    column_config={
        "✓ Create":            st.column_config.CheckboxColumn("✓", default=True),
        "birthday":            st.column_config.DateColumn("birthday", format="YYYY-MM-DD"),
        "genetic_background":  st.column_config.TextColumn("genetic_background"),
        "line_building_stage": st.column_config.TextColumn("line_building_stage"),
        "description":         st.column_config.TextColumn("description"),
        "zygosity":            st.column_config.SelectboxColumn("zygosity", options=["","het","hom","unk"]),
    },
    key="new_fish_from_tclutch_editor_single",
)

todo = editor.loc[editor["✓ Create"]].copy()
if todo.empty:
    st.info("Nothing selected to create."); st.stop()

todo["identity_key"]     = todo.apply(_identity_key, axis=1)
auto_tank = st.checkbox("Auto-create active tank for fish", value=True)
todo["will_create_tank"] = "yes" if auto_tank else "no"
st.dataframe(
    todo[["✓ Create","nickname","birthday","genetic_background","line_building_stage","zygosity","identity_key","will_create_tank"]],
    hide_index=True, use_container_width=True, height=140
)

# Note (stored on fish.notes)
creation_note = st.text_input("Note (optional — stored on fish.notes)", value="")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Save
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("4) Save")

creator = getattr(user, "email", None) or (user.get("email") if isinstance(user, dict) else None) \
          or os.getenv("USER") or os.getenv("USERNAME") or "system"
seed_batch_id = f"from_tclutch:{g_code}"

def _create_rows(rows: pd.DataFrame) -> List[Dict[str,str]]:
    out: List[Dict[str,str]] = []
    with engine().begin() as cx:
        fn_upsert = text("""
          select * from public.upsert_fish_by_identity(
            :p_seed_batch_id,:p_identity_key,:p_dob,:p_name_human,
            :p_bg,:p_nick,:p_stage,:p_desc,:p_notes,:p_by
          )
        """)
        for _, r in rows.iterrows():
            ident = r.get("identity_key")
            params = {
                "p_seed_batch_id": seed_batch_id,
                "p_identity_key":  ident,
                "p_dob":           r.get("birthday"),
                "p_name_human":    None,
                "p_bg":            (r.get("genetic_background") or None),
                "p_nick":          (_canon_nick(r.get("nickname")) or None),
                "p_stage":         (r.get("line_building_stage") or None),
                "p_desc":          (r.get("description") or None),
                "p_notes":         (creation_note or None),
                "p_by":            creator,
            }
            got = cx.execute(fn_upsert, params).mappings().first() or {}
            fid = got.get("id") or got.get("fish_id")
            fc  = (got.get("fish_code") or "").strip()
            if not fid:
                continue

            # ensure an active tank
            if auto_tank and fc:
                cx.execute(text("SELECT public.ensure_active_tank_for_fish(:fc)"), {"fc": fc})

            # Link selected alleles from clutch genotype (base + nickname)
            for _, a in inherit_clutch.iterrows():
                base = str(a.get("base_code") or "").strip()
                nick = _canon_nick(str(a.get("allele_nickname") or "").strip())
                if base:
                    up = cx.execute(text("""
                      SELECT out_base AS base, out_number AS num
                      FROM public.upsert_transgene_allele(:b, :n)
                    """), {"b": base, "n": (nick if nick else None)}).mappings().first()
                    if up:
                        cx.execute(text("""
                          INSERT INTO public.join_fish_transgene_alleles
                            (fish_id, transgene_base_code, allele_number, zygosity)
                          VALUES (:fid,:b,:num,NULL)
                          ON CONFLICT DO NOTHING
                        """), {"fid": fid, "b": up["base"], "num": up["num"]})
                        # ensure FT markers + link fish→FT so rollups populate
                        cx.execute(text("""
                          INSERT INTO public.treatments_fluorescent (ft_code, ft_text, created_by)
                          VALUES (:ft, ''::text, :by)
                          ON CONFLICT (ft_code) DO NOTHING
                        """), {"ft": base, "by": creator})
                        cx.execute(text("""
                          INSERT INTO public.join_fish_fluorescent_treatments (fish_id, ft_code)
                          VALUES (:fid, :ft)
                          ON CONFLICT DO NOTHING
                        """), {"fid": fid, "ft": base})
                        cx.execute(text("SELECT public.ensure_ft_markers_from_transgene(:ft)"), {"ft": base})

            # Create new allele(s) from treatment bases (no nickname)
            for _, t in inherit_tx.iterrows():
                base = str(t.get("base_code") or "").strip()
                if base:
                    up = cx.execute(text("""
                      SELECT out_base AS base, out_number AS num
                      FROM public.upsert_transgene_allele(:b, NULL)
                    """), {"b": base}).mappings().first()
                    if up:
                        cx.execute(text("""
                          INSERT INTO public.join_fish_transgene_alleles
                            (fish_id, transgene_base_code, allele_number, zygosity)
                          VALUES (:fid,:b,:num,NULL)
                          ON CONFLICT DO NOTHING
                        """), {"fid": fid, "b": up["base"], "num": up["num"]})
                        # ensure FT markers + link fish→FT for treatment base
                        cx.execute(text("""
                          INSERT INTO public.treatments_fluorescent (ft_code, ft_text, created_by)
                          VALUES (:ft, ''::text, :by)
                          ON CONFLICT (ft_code) DO NOTHING
                        """), {"ft": base, "by": creator})
                        cx.execute(text("""
                          INSERT INTO public.join_fish_fluorescent_treatments (fish_id, ft_code)
                          VALUES (:fid, :ft)
                          ON CONFLICT DO NOTHING
                        """), {"fid": fid, "ft": base})
                        cx.execute(text("SELECT public.ensure_ft_markers_from_transgene(:ft)"), {"ft": base})

            out.append({"fish_code": fc, "id": fid})
    return out

if st.button("💾 Create selected fish", type="primary", use_container_width=True):
    try:
        created = _create_rows(todo)
        if not created:
            st.warning("Nothing created.")
        else:
            st.success(f"Created {len(created)} fish.")
            st.session_state["last_created_fish_codes"] = [r["fish_code"] for r in created if r.get("fish_code")]
    except Exception as e:
        st.error(f"Create failed: {e}")

# Post-create preview
st.subheader("Preview created fish (latest)")
codes = st.session_state.get("last_created_fish_codes", [])
if not codes:
    st.caption("No recent creations yet.")
else:
    dfv = _safe_read(text("""
      WITH core AS (
        SELECT
          vm.fish_code,
          MAX(vm.genotype_pretty)      AS genotype_pretty,
          MAX(COALESCE(vm.fluors,''))  AS fluors,
          MAX(COALESCE(vm.tags,''))    AS tags
        FROM public.v_fish_main vm
        WHERE vm.fish_code = ANY(:codes)
        GROUP BY vm.fish_code
      )
      SELECT
        c.fish_code,
        COALESCE(f.nickname,'')            AS nickname,
        f.dob                               AS birthday,
        COALESCE(f.genetic_background,'')   AS genetic_background,
        COALESCE(f.line_building_stage,'')  AS line_building_stage,
        c.genotype_pretty,
        c.fluors,
        c.tags,
        ''::text                            AS dyes
      FROM core c
      LEFT JOIN public.fish f ON f.fish_code = c.fish_code
      ORDER BY c.fish_code
    """), {"codes": codes})
    st.dataframe(dfv, hide_index=True, use_container_width=True)
    st.download_button(
        "⬇︎ Download created fish (CSV)",
        data=dfv.to_csv(index=False).encode("utf-8"),
        file_name=f"created_fish_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv",
        type="secondary", mime="text/csv"
    )