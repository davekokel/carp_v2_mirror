# carp_app/ui/pages/023_🧫_assign_fish_to_plates.py
from __future__ import annotations

import sys, pathlib, os, re, io
from typing import Dict, Tuple, Set, List

import pandas as pd
import streamlit as st
from sqlalchemy import text

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine

sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(page_title="🧫 Plates — assign fish & orientations", page_icon="🧫", layout="wide")
st.title("🧫 Plates — assign fish & orientations")

# DB objects
V_LAYOUT    = "public.v_plate_layout"
T_FORMATS   = "public.plate_formats"
T_PLATES    = "public.plates"
T_SLOTS     = "public.plate_slots"
V_TCL_OV    = "public.v_treated_clutches_overview"

ORIENTATIONS = [
    "dorsal_head_top",
    "lateral_head_left",
    "lateral_head_right",
    "head_down_dorsal_top",
]

def _exists_table(q: str) -> bool:
    s, n = q.split(".", 1)
    with engine().begin() as cx:
        r = pd.read_sql(text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema=:s AND table_name=:n LIMIT 1"""), cx, params={"s": s, "n": n})
    return not r.empty

def _exists_view(q: str) -> bool:
    s, n = q.split(".", 1)
    with engine().begin() as cx:
        r = pd.read_sql(text("""
            SELECT 1 FROM information_schema.views WHERE table_schema=:s AND table_name=:n
            UNION ALL
            SELECT 1 FROM pg_catalog.pg_matviews WHERE schemaname=:s AND matviewname=:n
            LIMIT 1"""), cx, params={"s": s, "n": n})
    return not r.empty

def _formats() -> pd.DataFrame:
    if not _exists_table(T_FORMATS):
        return pd.DataFrame(columns=["code","name","n_rows","n_cols"])
    with engine().begin() as cx:
        return pd.read_sql(text(f"SELECT code, name, n_rows, n_cols FROM {T_FORMATS} ORDER BY code"), cx)

def _ensure_plate_slots(plate_code: str) -> None:
    sql = text(f"""
    WITH p AS (SELECT id, format_code FROM {T_PLATES} WHERE plate_code=:pc LIMIT 1),
         f AS (SELECT pf.n_rows, pf.n_cols FROM {T_FORMATS} pf JOIN p ON pf.code=p.format_code),
         grid AS (
           SELECT p.id AS plate_id, r AS row_idx, c AS col_idx
           FROM p, f,
                generate_series(1,(SELECT n_rows FROM f)) AS r,
                generate_series(1,(SELECT n_cols FROM f)) AS c
         )
    INSERT INTO {T_SLOTS}(plate_id,row_idx,col_idx)
    SELECT g.plate_id, g.row_idx, g.col_idx
    FROM grid g
    LEFT JOIN {T_SLOTS} s
      ON s.plate_id=g.plate_id AND s.row_idx=g.row_idx AND s.col_idx=g.col_idx
    WHERE s.plate_id IS NULL;""")
    with engine().begin() as cx:
        cx.execute(sql, {"pc": plate_code})

def _create_plate(format_code: str, created_by: str) -> str:
    """
    Let DB trigger generate short plate_code (format001, format002, ...).
    nickname is set later (Step 5) via UPDATE.
    """
    sql = text(f"""
      INSERT INTO {T_PLATES} (format_code, nickname, created_by)
      VALUES (:fmt, NULL, :by)
      RETURNING plate_code
    """)
    with engine().begin() as cx:
        code = cx.execute(sql, {"fmt": format_code, "by": created_by}).scalar()
    plate_code = str(code)
    _ensure_plate_slots(plate_code)
    return plate_code

def _load_layout(plate_code: str) -> pd.DataFrame:
    if not _exists_view(V_LAYOUT):
        return pd.DataFrame(columns=[
            "plate_code","plate_nickname","format_code","n_rows","n_cols",
            "row_idx","col_idx","row_letter","well_label",
            "treated_clutch_code","orientation","created_at"
        ])
    sql = text(f"""
      SELECT plate_code, plate_nickname, format_code, n_rows, n_cols,
             row_idx, col_idx, row_letter, well_label,
             treated_clutch_id, treated_clutch_code, orientation, created_at
      FROM {V_LAYOUT}
      WHERE plate_code=:p
      ORDER BY row_idx, col_idx
    """)
    with engine().begin() as cx:
        df = pd.read_sql(sql, cx, params={"p": plate_code})
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")
    return df

def _load_or_seed_layout(plate_code: str) -> pd.DataFrame:
    df = _load_layout(plate_code)
    if df.empty and _exists_table(T_SLOTS):
        _ensure_plate_slots(plate_code)
        df = _load_layout(plate_code)
    return df

def _fetch_treated_groups(q: str, limit: int = 500) -> pd.DataFrame:
    """
    Pull treated clutch groups from v_treated_clutches_overview,
    with useful genotype + fusions rollups for picking.
    """
    if not _exists_view(V_TCL_OV):
        return pd.DataFrame(
            columns=[
                "treated_clutch_code",
                "clutch_code",
                "offspring_genotype",
                "mom_genotype",
                "dad_genotype",
                "mom_fusions",
                "dad_fusions",
                "tx_names",
                "group_created_at",
            ]
        )

    where = []
    p: Dict[str, Any] = {}
    if q.strip():
        p["q"] = f"%{q.strip()}%"
        # UPDATED: use new treatment_names_rollup from the view
        where.append(
            """
          (
            treated_clutch_code           ILIKE :q OR
            clutch_code                   ILIKE :q OR
            COALESCE(mom_genotype,'')     ILIKE :q OR
            COALESCE(dad_genotype,'')     ILIKE :q OR
            COALESCE(mom_fusions,'')      ILIKE :q OR
            COALESCE(dad_fusions,'')      ILIKE :q OR
            COALESCE(treatment_names_rollup,'') ILIKE :q
          )
        """
        )
    wsql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = text(
        f"""
      SELECT
        treated_clutch_code,
        clutch_code,

        -- offspring genotype = mom × dad (for quick visual)
        TRIM(
          BOTH ' × ' FROM (
            COALESCE(NULLIF(mom_genotype,''), '?') || ' × ' ||
            COALESCE(NULLIF(dad_genotype,''), '?')
          )
        ) AS offspring_genotype,

        COALESCE(mom_genotype,'')           AS mom_genotype,
        COALESCE(dad_genotype,'')           AS dad_genotype,
        COALESCE(mom_fusions,'')            AS mom_fusions,
        COALESCE(dad_fusions,'')            AS dad_fusions,

        -- UPDATED: treatment_names_rollup from the view
        COALESCE(treatment_names_rollup,'') AS tx_names,

        group_created_at
      FROM {V_TCL_OV}
      {wsql}
      ORDER BY group_created_at DESC NULLS LAST, treated_clutch_code
      LIMIT :lim
    """
    )
    p["lim"] = int(limit)
    with engine().begin() as cx:
        df = pd.read_sql(sql, cx, params=p)

    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype("string").fillna("")

    return df[
        [
            "treated_clutch_code",
            "clutch_code",
            "offspring_genotype",
            "mom_genotype",
            "dad_genotype",
            "mom_fusions",
            "dad_fusions",
            "tx_names",
            "group_created_at",
        ]
    ]

def _csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def _parse_well_token(tok: str) -> Tuple[int,int] | None:
    m = re.fullmatch(r"([A-Za-z])\s*(\d{1,2})", tok.strip())
    if not m: return None
    row = m.group(1).upper()
    col = int(m.group(2))
    return (ord(row)-64, col)

def _expand_range(a: str, b: str) -> Set[Tuple[int,int]]:
    a_rc = _parse_well_token(a); b_rc = _parse_well_token(b)
    if not a_rc or not b_rc: return set()
    r1,c1 = a_rc; r2,c2 = b_rc
    rr = range(min(r1,r2), max(r1,r2)+1)
    cc = range(min(c1,c2), max(c1,c2)+1)
    return {(r,c) for r in rr for c in cc}

def _parse_selection(expr: str) -> Set[Tuple[int,int]]:
    out:set[Tuple[int,int]] = set()
    if not expr or not expr.strip(): return out
    parts = [p.strip() for p in re.split(r"[,\s]+", expr) if p.strip()]
    for p in parts:
        if ":" in p:
            a,b = p.split(":",1)
            out |= _expand_range(a,b)
        else:
            rc = _parse_well_token(p)
            if rc: out.add(rc)
    return out

def _skey(plate_code:str, suffix:str)->str:
    return f"plate:{plate_code}:{suffix}"

def _get_map(plate_code:str, key:str, default):
    return st.session_state.get(_skey(plate_code,key), default)

def _set_map(plate_code:str, key:str, val):
    st.session_state[_skey(plate_code,key)] = val

# 1) Select a plate name/format
st.subheader("1) Select a plate name/format")
fmts = _formats()
if fmts.empty:
    st.warning("No plate formats found. Seed `public.plate_formats` and rerun."); st.stop()

fmt_labels = [f"{r.code} · {r.n_rows}×{r.n_cols}" for r in fmts.itertuples()]
default_fmt = st.session_state.get("_last_fmt", fmt_labels[0])
fmt_label = st.selectbox("Format", fmt_labels, index=fmt_labels.index(default_fmt) if default_fmt in fmt_labels else 0)
fmt_code = fmt_label.split(" · ", 1)[0]
st.session_state["_last_fmt"] = fmt_label

creator = os.getenv("USER") or os.getenv("USERNAME") or getattr(user, "email","") or "system"

if st.button("➕ Create plate", type="primary"):
    plate_code = _create_plate(fmt_code, creator)
    st.success(f"Created plate: **{plate_code}**")
    st.session_state["_created_plate"] = plate_code

plate_code = st.session_state.get("_created_plate")
if not plate_code:
    st.info("Create a plate to proceed."); st.stop()

# load layout for this plate
layout = _load_or_seed_layout(plate_code)
if layout.empty:
    st.error("No layout rows for this plate (format missing n_rows/n_cols or `v_plate_layout` missing)."); st.stop()
rows, cols = int(layout["n_rows"].iloc[0]), int(layout["n_cols"].iloc[0])
plate_nickname_initial = str(layout.get("plate_nickname","").iloc[0] if "plate_nickname" in layout.columns else "")
full_all_expr = f"A01:{chr(64+rows)}{str(cols).zfill(2)}"
st.caption(f"{plate_code} • {layout['format_code'].iloc[0]} • {rows}×{cols}")

# 2) Pick treated_clutch_code(s)
st.subheader("2) Pick treated_clutch_code(s)")
group_q = st.text_input("Search treated clutches (code / clutch / genotype / tx)", "")
groups = _fetch_treated_groups(group_q, 500)

sel_codes_key = _skey(plate_code,"sel_codes")
persisted_codes: List[str] = st.session_state.get(sel_codes_key, [])
picked_codes: List[str] = []

if groups.empty:
    st.info("No treated groups match your search.")
else:
    gdf = groups.copy()
    gdf.insert(0,"✓", False)
    gsel = st.data_editor(
        gdf,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        height=260,
        column_config={
            "✓":                   st.column_config.CheckboxColumn("✓", default=False),
            "treated_clutch_code": st.column_config.TextColumn("treated_clutch_code", disabled=True),
            "clutch_code":         st.column_config.TextColumn("clutch_code", disabled=True),
            "offspring_genotype":  st.column_config.TextColumn("offspring genotype", disabled=True),
            "mom_genotype":        st.column_config.TextColumn("mom genotype", disabled=True),
            "dad_genotype":        st.column_config.TextColumn("dad genotype", disabled=True),
            "mom_fusions":         st.column_config.TextColumn("mom fusions", disabled=True),
            "dad_fusions":         st.column_config.TextColumn("dad fusions", disabled=True),
            "tx_names":            st.column_config.TextColumn("tx (names)", disabled=True),
        },
        key="tclutch_picker_v4",
    )
    now_picked = gsel.loc[gsel["✓"] == True, "treated_clutch_code"].astype(str).tolist()
    picked_codes = now_picked if now_picked else persisted_codes
    st.session_state[sel_codes_key] = picked_codes

# 3) Assign fish to wells (per treated_clutch_code)
st.subheader("3) Assign fish to wells (per treated_clutch_code)")
st.caption("Enter ranges like A01:C03, B05. **All wells** fills all remaining empty wells.")
def _all_cells(r:int,c:int)->Set[Tuple[int,int]]: return {(ri,ci) for ri in range(1,r+1) for ci in range(1,c+1)}
def _cells_to_expr(cells:Set[Tuple[int,int]])->str:
    if not cells: return ""
    return ",".join(f"{chr(64+r)}{str(c).zfill(2)}" for r,c in sorted(cells))

code_map: Dict[str,str] = _get_map(plate_code,"code_map",{})
for c in picked_codes: code_map.setdefault(c,"")

all_cells = _all_cells(rows, cols)
filled_db_codes = set(tuple(x) for x in layout.loc[layout["treated_clutch_code"]!="",["row_idx","col_idx"]].itertuples(index=False,name=None))
staged_codes = set()
for _,expr in (code_map or {}).items():
    if expr.strip(): staged_codes |= _parse_selection(expr)
remaining_for_codes = all_cells - filled_db_codes - staged_codes
st.caption(f"Remaining wells for codes: {_cells_to_expr(remaining_for_codes) or '(none)'}")

if picked_codes:
    cols_dyn = st.columns(2)
    for i, code in enumerate(picked_codes):
        key = f"map_code_{code}"
        desired = code_map.get(code,"")
        if key not in st.session_state: st.session_state[key] = desired
        elif st.session_state[key] != desired: st.session_state[key] = desired
        with cols_dyn[i % 2]:
            r = st.columns([3,1])
            with r[0]:
                val = st.text_input(f"{code} — wells", key=key)
                if val != code_map.get(code,""):
                    code_map[code]=val; _set_map(plate_code,"code_map",code_map)
            with r[1]:
                if st.button("All wells", key=f"all_code_{code}", disabled=(len(remaining_for_codes)==0)):
                    code_map[code] = _cells_to_expr(remaining_for_codes)
                    _set_map(plate_code,"code_map",code_map); st.rerun()
    _set_map(plate_code,"code_map",code_map)
else:
    st.info("Select at least one treated_clutch_code above.")

# 4) Assign orientation(s) to wells (per orientation)
st.subheader("4) Assign orientation(s) to wells (per orientation)")
st.caption("Enter ranges like A01:C03. **All wells** fills all remaining unoriented wells.")
sel_oris_key = _skey(plate_code,"sel_oris")
persisted_oris: List[str] = st.session_state.get(sel_oris_key, [])
ori_df = pd.DataFrame({"orientation": ORIENTATIONS}); ori_df.insert(0,"✓", False)
ori_sel = st.data_editor(
    ori_df, hide_index=True, use_container_width=True, num_rows="fixed", height=160,
    column_config={"✓": st.column_config.CheckboxColumn("✓", default=False),
                   "orientation": st.column_config.TextColumn("orientation", disabled=True)},
    key="ori_picker_v2")
now_oris = ori_sel.loc[ori_sel["✓"]==True,"orientation"].astype(str).tolist()
picked_oris = now_oris if now_oris else persisted_oris; st.session_state[sel_oris_key]=picked_oris

ori_map: Dict[str,str] = _get_map(plate_code,"ori_map",{})
for o in picked_oris: ori_map.setdefault(o,"")

filled_db_ori = set(tuple(x) for x in layout.loc[layout["orientation"]!="",["row_idx","col_idx"]].itertuples(index=False,name=None))
staged_ori = set()
for _,expr in (ori_map or {}).items():
    if expr.strip(): staged_ori |= _parse_selection(expr)
remaining_for_ori = _all_cells(rows, cols) - filled_db_ori - staged_ori
st.caption(f"Remaining wells for orientations: {_cells_to_expr(remaining_for_ori) or '(none)'}")

if picked_oris:
    cols_o = st.columns(2)
    for i, ori in enumerate(picked_oris):
        key = f"map_ori_{ori}"
        desired = ori_map.get(ori,"")
        if key not in st.session_state: st.session_state[key]=desired
        elif st.session_state[key]!=desired: st.session_state[key]=desired
        with cols_o[i % 2]:
            r = st.columns([3,1])
            with r[0]:
                val = st.text_input(f"{ori} — wells", key=key)
                if val != ori_map.get(ori,""):
                    ori_map[ori]=val; _set_map(plate_code,"ori_map",ori_map)
            with r[1]:
                if st.button("All wells", key=f"all_ori_{ori}", disabled=(len(remaining_for_ori)==0)):
                    ori_map[ori] = _cells_to_expr(remaining_for_ori)
                    _set_map(plate_code,"ori_map",ori_map); st.rerun()
    _set_map(plate_code,"ori_map",ori_map)
else:
    st.info("Select one or more orientations above.")

# 5) Optional — plate nickname
st.subheader("5) Optional — plate nickname")
plate_nickname = st.text_input("Plate nickname (stored as plates.nickname)", value=plate_nickname_initial)

# Preview — staged
st.subheader("Preview (staged)")
preview = layout[["well_label","treated_clutch_code","orientation","row_idx","col_idx"]].copy()
for code,expr in (code_map or {}).items():
    if not (code and expr.strip()): continue
    for (r,c) in _parse_selection(expr):
        preview.loc[(preview["row_idx"]==r)&(preview["col_idx"]==c),"treated_clutch_code"]=code
for ori,expr in (ori_map or {}).items():
    if not (ori and expr.strip()): continue
    for (r,c) in _parse_selection(expr):
        preview.loc[(preview["row_idx"]==r)&(preview["col_idx"]==c),"orientation"]=ori
st.dataframe(preview[["well_label","treated_clutch_code","orientation"]], hide_index=True, use_container_width=True, height=240)

# 6) Save plate
st.subheader("6) Save plate")
def _apply_mappings(plate_code:str, code_map:Dict[str,str], ori_map:Dict[str,str])->Tuple[int,int,int]:
    with engine().begin() as cx:
        pid = cx.execute(text(f"SELECT id::text FROM {T_PLATES} WHERE plate_code=:p LIMIT 1"), {"p":plate_code}).scalar()
        if not pid: raise RuntimeError("Unknown plate_code")
        cur = pd.read_sql(text(f"SELECT row_idx,col_idx,treated_clutch_id,orientation FROM {T_SLOTS} WHERE plate_id=:pid"),
                          cx, params={"pid":pid})
        cur_map = {(int(r.row_idx),int(r.col_idx)):(str(r.treated_clutch_id) if r.treated_clutch_id else None,
                                                   (str(r.orientation) if r.orientation else None))
                   for r in cur.itertuples(index=False)}
        def tcid_of(code:str)->str|None:
            if not code: return None
            return cx.execute(text("SELECT id::text FROM public.treated_clutches WHERE treated_clutch_code=:c LIMIT 1"),
                              {"c":code}).scalar()
        n_code=n_ori=n_over=0
        for code,expr in (code_map or {}).items():
            if not (code and expr.strip()): continue
            _tcid = tcid_of(code); 
            if not _tcid: raise RuntimeError(f"Unknown treated_clutch_code: {code}")
            for (r,c) in _parse_selection(expr):
                prev = cur_map.get((r,c))
                if prev and prev[0] and prev[0]!=_tcid: n_over+=1
                cx.execute(text(f"UPDATE {T_SLOTS} SET treated_clutch_id=:tc WHERE plate_id=:pid AND row_idx=:r AND col_idx=:c"),
                           {"tc":_tcid,"pid":pid,"r":int(r),"c":int(c)})
                cur_map[(r,c)]=(_tcid, prev[1] if prev else None); n_code+=1
        for ori,expr in (ori_map or {}).items():
            if not (ori and expr.strip()): continue
            for (r,c) in _parse_selection(expr):
                prev = cur_map.get((r,c))
                if prev and prev[1] and prev[1]!=ori: n_over+=1
                cx.execute(text(f"UPDATE {T_SLOTS} SET orientation=:o WHERE plate_id=:pid AND row_idx=:r AND col_idx=:c"),
                           {"o":ori,"pid":pid,"r":int(r),"c":int(c)})
                cur_map[(r,c)]=(prev[0] if prev else None, ori); n_ori+=1
    return n_code,n_ori,n_over

def _update_plate_nickname(plate_code:str, nickname:str)->None:
    with engine().begin() as cx:
        cx.execute(text(f"UPDATE {T_PLATES} SET nickname=NULLIF(:nm,'') WHERE plate_code=:pc"),
                   {"nm":nickname,"pc":plate_code})

if st.button("💾 Save plate", type="primary", use_container_width=True):
    try:
        if plate_nickname != plate_nickname_initial:
            _update_plate_nickname(plate_code, plate_nickname)
        n_code,n_ori,n_over = _apply_mappings(plate_code, _get_map(plate_code,"code_map",{}), _get_map(plate_code,"ori_map",{}))
        st.success(f"Saved: codes→{n_code}, orientations→{n_ori} (overwrites: {n_over}).")
        _set_map(plate_code,"code_map",{}); _set_map(plate_code,"ori_map",{})
        layout = _load_or_seed_layout(plate_code)
    except Exception as e:
        st.error(f"Save failed: {e}")

st.divider()
st.subheader("Export")
dl_df = _load_or_seed_layout(plate_code)[["plate_code","plate_nickname","format_code","well_label","treated_clutch_code","orientation"]].copy()
st.download_button(
    "⬇︎ Download layout CSV",
    data=_csv_bytes(dl_df),
    file_name=f"{plate_code}_layout.csv",
    mime="text/csv",
    type="secondary",
    use_container_width=True
)