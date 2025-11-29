# carp_app/ui/pages/230_⚙️_assign_fish_to_plates_slots.py
# ⚙️ Assign clutches to imaging plates & slots (v11 imaging schema)

from __future__ import annotations

import sys, pathlib, os, re, io
from typing import Dict, Tuple, Set, List, Any
from uuid import uuid4
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

# --- repo wiring --------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from carp_app.ui.auth_gate import require_auth
from carp_app.ui.email_otp_gate import require_email_otp
try:
    from carp_app.ui.auth_gate import require_app_unlock
except Exception:
    def require_app_unlock(): ...
from carp_app.ui.lib.page_engine import engine as _engine

# --- auth / page --------------------------------------------------------------
sb, session, user = require_auth()
require_email_otp()
require_app_unlock()

st.set_page_config(
    page_title="CARP — ⚙️ Assign clutches to plates & slots",
    page_icon="⚙️",
    layout="wide",
)
st.title("⚙️ Assign clutches to plates & slots (v11 imaging)")

def eng() -> Engine:
    return _engine()

# --- imaging schema objects ---------------------------------------------------
T_IMAGING_PLATES = "public.imaging_plates"
T_IMAGING_SLOTS  = "public.imaging_slots"
T_IMAGING_MEMB   = "public.imaging_clutch_memberships"
V_CLUTCH_STAR    = "public.v11_clutch_star"

# plate-type / microscope-specific orientations
PLATE_ORIENTATIONS: Dict[str, List[str]] = {
    "mosaic": [
        "dorsal_head",
        "dorsal_spine",
        "lateral_yolk_left",
        "lateral_yolk_right",
    ],
    "isoar": [
        "dorsal",
        "lateral",
    ],
}
DEFAULT_ORIENTATIONS = [
    "dorsal",
    "lateral",
]

# --- helpers ------------------------------------------------------------------
def _exists_table(q: str) -> bool:
    s, n = q.split(".", 1)
    with eng().begin() as cx:
        r = pd.read_sql(
            text(
                """
          SELECT 1 FROM information_schema.tables
          WHERE table_schema=:s AND table_name=:n LIMIT 1
        """
            ),
            cx,
            params={"s": s, "n": n},
        )
    return not r.empty

def _exists_view(q: str) -> bool:
    s, n = q.split(".", 1)
    with eng().begin() as cx:
        r = pd.read_sql(
            text(
                """
          SELECT 1 FROM information_schema.views WHERE table_schema=:s AND table_name=:n
          UNION ALL
          SELECT 1 FROM pg_catalog.pg_matviews WHERE schemaname=:s AND matviewname=:n
          LIMIT 1
        """
            ),
            cx,
            params={"s": s, "n": n},
        )
    return not r.empty

def _csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def _parse_well_token(tok: str) -> Tuple[int, int] | None:
    m = re.fullmatch(r"([A-Za-z])\s*(\d{1,2})", tok.strip())
    if not m:
        return None
    row = m.group(1).upper()
    col = int(m.group(2))
    return (ord(row) - 64, col)

def _expand_range(a: str, b: str) -> Set[Tuple[int, int]]:
    a_rc = _parse_well_token(a)
    b_rc = _parse_well_token(b)
    if not a_rc or not b_rc:
        return set()
    r1, c1 = a_rc
    r2, c2 = b_rc
    rr = range(min(r1, r2), max(r1, r2) + 1)
    cc = range(min(c1, c2), max(c1, c2) + 1)
    return {(r, c) for r in rr for c in cc}

def _parse_selection(expr: str) -> Set[Tuple[int, int]]:
    out: set[Tuple[int, int]] = set()
    if not expr or not expr.strip():
        return out
    parts = [p.strip() for p in re.split(r"[,\s]+", expr) if p.strip()]
    for p in parts:
        # allow both A01:A06 and A01-A06 as ranges
        if ":" in p or "-" in p:
            sep = ":" if ":" in p else "-"
            a, b = p.split(sep, 1)
            out |= _expand_range(a, b)
        else:
            rc = _parse_well_token(p)
            if rc:
                out.add(rc)
    return out

def _cells_to_expr(cells: Set[Tuple[int, int]]) -> str:
    if not cells:
        return ""
    return ",".join(f"{chr(64+r)}{str(c).zfill(2)}" for r, c in sorted(cells))

def _skey(plate_id: str, suffix: str) -> str:
    return f"plate:{plate_id}:{suffix}"

def _get_map(plate_id: str, key: str, default):
    return st.session_state.get(_skey(plate_id, key), default)

def _set_map(plate_id: str, key: str, val):
    st.session_state[_skey(plate_id, key)] = val

def _generate_slot_grid_size(microscope_type: str) -> Tuple[int, int]:
    mt = (microscope_type or "").strip().lower()
    if mt == "mosaic":
        return (1, 6)   # Bruker: 1×6
    if mt == "isoar":
        return (5, 5)   # Mattek: 5×5
    return (3, 3)       # fallback for unknown types

def _auto_generate_slots(plate_id: str, microscope_type: str) -> pd.DataFrame:
    rows, cols = _generate_slot_grid_size(microscope_type)
    with eng().begin() as cx:
        for r in range(1, rows + 1):
            for c in range(1, cols + 1):
                slot_label = f"{chr(64 + r)}{str(c).zfill(2)}"
                slot_index = (r - 1) * cols + c
                cx.execute(
                    text(
                        f"""
                INSERT INTO {T_IMAGING_SLOTS}
                  (id, plate_id, slot_index, slot_label, well_row, well_col, created_at)
                VALUES
                  (gen_random_uuid(), CAST(:pid AS uuid), :idx, :label, :r, :c, now())
                """
                    ),
                    {"pid": plate_id, "idx": slot_index, "label": slot_label, "r": r, "c": c},
                )
    with eng().begin() as cx:
        return pd.read_sql(
            text(
                f"""
          SELECT
            id::text AS slot_id,
            slot_label,
            well_row,
            well_col,
            orientation
          FROM {T_IMAGING_SLOTS}
          WHERE plate_id = CAST(:pid AS uuid)
          ORDER BY well_row, well_col
          """
            ),
            cx,
            params={"pid": plate_id},
        )

def _create_imaging_plate(date_mount: date, microscope_type: str, created_by: str) -> Tuple[str, str]:
    """
    Create a new imaging plate row and return (plate_id, plate_code).
    plate_code pattern: PL-YYYYMMDD-XXXX.
    """
    plate_code = f"PL-{date_mount.strftime('%Y%m%d')}-{uuid4().hex[:4]}"
    with eng().begin() as cx:
        plate_id = cx.execute(
            text(
                f"""
          INSERT INTO {T_IMAGING_PLATES}
            (id, plate_code, experiment_date, instrument, created_at, created_by)
          VALUES
            (gen_random_uuid(), :code, :d, :instr, now(), :who)
          RETURNING id::text
        """
            ),
            cx,
            params={"code": plate_code, "d": date_mount, "instr": microscope_type, "who": created_by},
        ).scalar()
    return str(plate_id), str(plate_code)

# --- sanity: check schema ----------------------------------------------------
miss = []
for obj in [T_IMAGING_PLATES, T_IMAGING_SLOTS, T_IMAGING_MEMB]:
    if not _exists_table(obj):
        miss.append(obj)
if not _exists_view(V_CLUTCH_STAR):
    miss.append(V_CLUTCH_STAR)

if miss:
    st.error("Required object not found: " + ", ".join(miss))
    st.stop()

# --- 1) Create imaging plate -------------------------------------------------
st.subheader("1) Create imaging plate")

today = pd.Timestamp.today().date()
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    date_mount = st.date_input("Mount / experiment date", value=today, key="mount_date")
with c2:
    microscope_type_sel = st.selectbox(
        "Microscope type",
        options=["mosaic", "isoar"],
        index=0,
    )
with c3:
    st.caption("New plates are created in public.imaging_plates with auto-generated plate_code.")

creator = (
    getattr(user, "email", None)
    or os.getenv("USER")
    or os.getenv("USERNAME")
    or "system"
)

if st.button("➕ Create new imaging plate", type="primary", use_container_width=True):
    plate_id_new, plate_code_new = _create_imaging_plate(date_mount, microscope_type_sel, creator)
    slots_new = _auto_generate_slots(plate_id_new, microscope_type_sel)
    st.session_state["_assign_plate_id"] = plate_id_new
    st.session_state["_assign_plate_code"] = plate_code_new
    st.success(
        f"Created imaging plate {plate_code_new} ({microscope_type_sel}) with {len(slots_new)} slots."
    )

plate_id = st.session_state.get("_assign_plate_id")
plate_code = st.session_state.get("_assign_plate_code")

if not plate_id:
    st.info("Create a new imaging plate above to continue.")
    st.stop()

# reload plate + slots
with eng().begin() as cx:
    plate_row = pd.read_sql(
        text(
            f"""
      SELECT
        id::text         AS plate_id,
        plate_code,
        experiment_date,
        COALESCE(scope_name, instrument, '') AS microscope_type
      FROM {T_IMAGING_PLATES}
      WHERE id = CAST(:pid AS uuid)
      LIMIT 1
      """
        ),
        cx,
        params={"pid": plate_id},
    ).iloc[0]

with eng().begin() as cx:
    slots = pd.read_sql(
        text(
            f"""
      SELECT
        id::text AS slot_id,
        slot_label,
        well_row,
        well_col,
        orientation
      FROM {T_IMAGING_SLOTS}
      WHERE plate_id = CAST(:pid AS uuid)
      ORDER BY well_row, well_col
      """
        ),
        cx,
        params={"pid": plate_id},
    )

if slots.empty:
    slots = _auto_generate_slots(plate_id, microscope_type_sel)

microscope_type = (plate_row["microscope_type"] or "").strip().lower()
ORIENTATIONS = PLATE_ORIENTATIONS.get(microscope_type, DEFAULT_ORIENTATIONS)

st.caption(
    f"Current plate: {plate_row['plate_code']} • date={plate_row['experiment_date']} • "
    f"microscope={microscope_type or 'n/a'} • orientations={', '.join(ORIENTATIONS)}"
)

slots = slots.copy()
slots["well_row"] = slots["well_row"].fillna(1).astype(int)
slots["well_col"] = slots["well_col"].fillna(1).astype(int)

n_rows = int(slots["well_row"].max())
n_cols = int(slots["well_col"].max())
st.caption(f"Plate layout: {n_rows}×{n_cols}")

all_cells = {(int(r), int(c)) for r, c in zip(slots["well_row"], slots["well_col"])}

# --- 2) Pick treated clutches ------------------------------------------------
st.subheader("2) Pick treated clutches (from v11_clutch_star)")

clutch_q = st.text_input("Search clutches (code/genotype/treatment)", "")

with eng().begin() as cx:
    where = ["(COALESCE(treat_codes,'') <> '' OR COALESCE(treatment_code,'') <> '')"]
    params: Dict[str, Any] = {}
    if clutch_q.strip():
        params["q"] = f"%{clutch_q.strip()}%"
        where.append(
            """(
              COALESCE(clutch_code,'')            ILIKE :q OR
              COALESCE(genotype_pretty,'')        ILIKE :q OR
              COALESCE(genotype_basecode_code,'') ILIKE :q OR
              COALESCE(treat_codes,'')            ILIKE :q
            )"""
        )
    wsql = "WHERE " + " AND ".join(where) if where else ""
    clutches = pd.read_sql(
        text(
            f"""
      SELECT
        clutch_id,
        clutch_code,
        clutch_date,
        genotype_pretty,
        genotype_basecode_code,
        treat_codes,
        all_fluor_tag_rollup,
        all_organelle_fluor_rollup
      FROM {V_CLUTCH_STAR}
      {wsql}
      ORDER BY clutch_date DESC NULLS LAST, clutch_code
      LIMIT 500
      """
        ),
        cx,
        params=params,
    )

if clutches.empty:
    st.info("No treated clutches match your search.")
    selected_clutches: List[Dict[str, Any]] = []
else:
    cdf = clutches.copy()
    cdf.insert(0, "✓", False)
    clutch_pick = st.data_editor(
        cdf,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        height=260,
        column_config={
            "✓":                          st.column_config.CheckboxColumn("✓", default=False),
            "clutch_code":                st.column_config.TextColumn("Clutch", disabled=True),
            "clutch_date":                st.column_config.DateColumn("Date", disabled=True),
            "genotype_pretty":            st.column_config.TextColumn("Genotype", disabled=True, width="large"),
            "genotype_basecode_code":     st.column_config.TextColumn("Basecodes", disabled=True, width="large"),
            "treat_codes":                st.column_config.TextColumn("Treat codes", disabled=True, width="large"),
            "all_fluor_tag_rollup":       st.column_config.TextColumn("Tx → fluor::tag(pos)", disabled=True, width="large"),
            "all_organelle_fluor_rollup": st.column_config.TextColumn("Tx → organelle-fluor", disabled=True, width="large"),
        },
        key="assign_clutch_picker_v11",
    )
    selected_clutches = (
        clutch_pick.loc[clutch_pick["✓"] == True].to_dict(orient="records")
        if "✓" in clutch_pick.columns
        else []
    )

st.caption(f"Selected clutches: {len(selected_clutches)}")

# --- 3) Assign clutches to wells ---------------------------------------------
st.subheader("3) Assign clutches to wells")
st.caption("Example syntax: A01:A03, B01:B02")

clutch_map: Dict[str, str] = _get_map(plate_id, "clutch_map", {})

if not selected_clutches:
    st.info("Select one or more clutches above.")
else:
    # existing memberships on this plate
    with eng().begin() as cx:
        memb_df = pd.read_sql(
            text(
                f"""
        SELECT
          s.well_row,
          s.well_col
        FROM {T_IMAGING_MEMB} m
        JOIN {T_IMAGING_SLOTS} s ON s.id = m.slot_id
        WHERE s.plate_id = CAST(:pid AS uuid)
        """
            ),
            cx,
            params={"pid": plate_id},
        )
    existing_memberships: Set[Tuple[int, int]] = set()
    if not memb_df.empty:
        existing_memberships = {
            (int(r), int(c)) for r, c in zip(memb_df["well_row"], memb_df["well_col"])
        }

    staged_cells: Set[Tuple[int, int]] = set()
    for expr in clutch_map.values():
        if expr.strip():
            staged_cells |= _parse_selection(expr)

    remaining_cells = all_cells - existing_memberships - staged_cells
    st.caption(
        f"Remaining wells (no clutch yet): {_cells_to_expr(remaining_cells) or '(none)'}"
    )

    # ensure keys for selected clutches
    for c in selected_clutches:
        code = c["clutch_code"]
        clutch_map.setdefault(code, "")

    cols_map = st.columns(2)
    for i, c in enumerate(selected_clutches):
        code = c["clutch_code"]
        key = f"clutch_map_{code}"
        default_expr = clutch_map.get(code, "")
        with cols_map[i % 2]:
            r = st.columns([3, 1])
            with r[0]:
                val = st.text_input(f"{code} — wells", key=key, value=default_expr)
                if val != clutch_map.get(code, ""):
                    clutch_map[code] = val
                    _set_map(plate_id, "clutch_map", clutch_map)
            with r[1]:
                if st.button(
                    "All empty wells",
                    key=f"clutch_all_{code}",
                    disabled=(len(remaining_cells) == 0),
                ):
                    clutch_map[code] = _cells_to_expr(remaining_cells)
                    _set_map(plate_id, "clutch_map", clutch_map)
                    st.rerun()

    _set_map(plate_id, "clutch_map", clutch_map)

# --- 4) Assign orientations to wells -----------------------------------------
st.subheader("4) Assign orientations to wells")
st.caption("Example syntax: A01:A03, B01:B02")

ori_map: Dict[str, str] = _get_map(plate_id, "ori_map", {})
for ori in ORIENTATIONS:
    ori_map.setdefault(ori, "")
_set_map(plate_id, "ori_map", ori_map)

existing_ori_cells: Set[Tuple[int, int]] = set()
for r, c, o in zip(slots["well_row"], slots["well_col"], slots["orientation"]):
    if str(o or "").strip():
        existing_ori_cells.add((int(r), int(c)))

staged_ori: Set[Tuple[int, int]] = set()
for expr in ori_map.values():
    if expr.strip():
        staged_ori |= _parse_selection(expr)

remaining_ori = all_cells - existing_ori_cells - staged_ori
st.caption(f"Remaining wells (no orientation yet): {_cells_to_expr(remaining_ori) or '(none)'}")

cols_ori = st.columns(2)
for i, ori in enumerate(ORIENTATIONS):
    key = f"ori_map_{ori}"
    default_expr = ori_map.get(ori, "")
    with cols_ori[i % 2]:
        r = st.columns([3, 1])
        with r[0]:
            val = st.text_input(f"{ori} — wells", key=key, value=default_expr)
            if val != ori_map.get(ori, ""):
                ori_map[ori] = val
                _set_map(plate_id, "ori_map", ori_map)
        with r[1]:
            if st.button(
                "All unoriented wells",
                key=f"ori_all_{ori}",
                disabled=(len(remaining_ori) == 0),
            ):
                ori_map[ori] = _cells_to_expr(remaining_ori)
                _set_map(plate_id, "ori_map", ori_map)
                st.rerun()

# --- 5) Preview layout -------------------------------------------------------
st.subheader("5) Preview layout")

preview = slots[["slot_label", "well_row", "well_col", "orientation"]].copy()

# existing memberships → clutch_code
with eng().begin() as cx:
    memb_df2 = pd.read_sql(
        text(
            f"""
      SELECT
        s.well_row,
        s.well_col,
        c.clutch_code
      FROM {T_IMAGING_MEMB} m
      JOIN {T_IMAGING_SLOTS} s ON s.id = m.slot_id
      JOIN public.clutches c    ON c.id = m.clutch_id
      WHERE s.plate_id = CAST(:pid AS uuid)
      """
        ),
        cx,
        params={"pid": plate_id},
    )

preview["clutch_code"] = ""
if not memb_df2.empty:
    for r, c, code in zip(
        memb_df2["well_row"], memb_df2["well_col"], memb_df2["clutch_code"]
    ):
        mask = (preview["well_row"] == int(r)) & (preview["well_col"] == int(c))
        preview.loc[mask, "clutch_code"] = code

# overlay staged clutch assignments
for code, expr in (clutch_map or {}).items():
    if not (code and expr.strip()):
        continue
    for (r, c) in _parse_selection(expr):
        mask = (preview["well_row"] == int(r)) & (preview["well_col"] == int(c))
        preview.loc[mask, "clutch_code"] = code

# overlay staged orientations
for ori, expr in (ori_map or {}).items():
    if not (ori and expr.strip()):
        continue
    for (r, c) in _parse_selection(expr):
        mask = (preview["well_row"] == int(r)) & (preview["well_col"] == int(c))
        preview.loc[mask, "orientation"] = ori

st.dataframe(
    preview[["slot_label", "clutch_code", "orientation"]],
    hide_index=True,
    use_container_width=True,
    height=260,
)

# --- 6) Save mappings --------------------------------------------------------
st.subheader("6) Save mappings")

def _apply_mappings(
    plate_id: str,
    clutch_map: Dict[str, str],
    ori_map: Dict[str, str],
) -> Tuple[int, int, int]:
    """
    Apply clutch and orientation mappings to imaging_clutch_memberships + imaging_slots.
    Returns (n_clutch_updates, n_orientation_updates, n_orientation_overwrites).
    """
    n_c = n_o = n_over = 0

    with eng().begin() as cx:
        # slots: (row,col) -> slot_id
        slots_df = pd.read_sql(
            text(
                f"""
          SELECT id::text AS slot_id, well_row, well_col
          FROM {T_IMAGING_SLOTS}
          WHERE plate_id = CAST(:pid AS uuid)
        """
            ),
            cx,
            params={"pid": plate_id},
        )
        slot_map: Dict[Tuple[int, int], str] = {
            (int(r), int(c)): sid
            for r, c, sid in zip(slots_df["well_row"], slots_df["well_col"], slots_df["slot_id"])
        }

        # existing memberships
        memb_df = pd.read_sql(
            text(
                f"""
          SELECT
            m.clutch_id::text,
            s.id::text AS slot_id
          FROM {T_IMAGING_MEMB} m
          JOIN {T_IMAGING_SLOTS} s ON s.id = m.slot_id
          WHERE s.plate_id = CAST(:pid AS uuid)
        """
            ),
            cx,
            params={"pid": plate_id},
        )
        existing_memb = {
            (sid, cid) for cid, sid in zip(memb_df["clutch_id"], memb_df["slot_id"])
        }

        # existing orientations
        slots_ori_df = pd.read_sql(
            text(
                f"""
          SELECT id::text AS slot_id, orientation
          FROM {T_IMAGING_SLOTS}
          WHERE plate_id = CAST(:pid AS uuid)
        """
            ),
            cx,
            params={"pid": plate_id},
        )
        existing_ori = {
            sid: (o if o is not None else "")
            for sid, o in zip(slots_ori_df["slot_id"], slots_ori_df["orientation"])
        }

        # helper: clutch_code -> clutch_id
        def clutch_id_of(code: str) -> str | None:
            if not code:
                return None
            return cx.execute(
                text(
                    "SELECT id::text FROM public.clutches WHERE clutch_code=:c LIMIT 1"
                ),
                {"c": code},
            ).scalar()

        who = (
            getattr(user, "email", None)
            or os.getenv("USER")
            or os.getenv("USERNAME")
            or "system"
        )

        # apply clutch mappings
        for code, expr in (clutch_map or {}).items():
            if not (code and expr.strip()):
                continue
            cid = clutch_id_of(code)
            if not cid:
                raise RuntimeError(f"Unknown clutch_code: {code}")
            for (r, c) in _parse_selection(expr):
                sid = slot_map.get((r, c))
                if not sid:
                    continue
                if (sid, cid) in existing_memb:
                    continue
                cx.execute(
                    text(
                        f"""
                  INSERT INTO {T_IMAGING_MEMB}
                    (id, clutch_id, slot_id, role, embryo_count, mount_notes, created_at, created_by)
                  VALUES
                    (gen_random_uuid(), CAST(:cid AS uuid), CAST(:sid AS uuid),
                     NULL, NULL, NULL, now(), :who)
                """
                    ),
                    {"cid": cid, "sid": sid, "who": who},
                )
                existing_memb.add((sid, cid))
                n_c += 1

        # apply orientation mappings
        for ori, expr in (ori_map or {}).items():
            if not (ori and expr.strip()):
                continue
            for (r, c) in _parse_selection(expr):
                sid = slot_map.get((r, c))
                if not sid:
                    continue
                prev = existing_ori.get(sid, "")
                if prev and prev != ori:
                    n_over += 1
                if prev != ori:
                    cx.execute(
                        text(
                            f"""
                      UPDATE {T_IMAGING_SLOTS}
                      SET orientation = :ori
                      WHERE id = CAST(:sid AS uuid)
                    """
                        ),
                        {"ori": ori, "sid": sid},
                    )
                    existing_ori[sid] = ori
                    n_o += 1

    return n_c, n_o, n_over

if st.button("💾 Save mappings", type="primary", use_container_width=True):
    clutch_map = _get_map(plate_id, "clutch_map", {})
    ori_map = _get_map(plate_id, "ori_map", {})
    try:
        n_c, n_o, n_over = _apply_mappings(plate_id, clutch_map, ori_map)
        st.success(
            f"Saved mappings: clutches→{n_c}, orientations→{n_o}, overwrote {n_over} existing orientation(s)."
        )
    except Exception as e:
        st.error(f"Save failed: {e}")

# --- 7) Export layout ---------------------------------------------------------
st.divider()
st.subheader("Export plate layout CSV")

with eng().begin() as cx:
    export_df = pd.read_sql(
        text(
            f"""
      SELECT
        p.plate_code,
        p.experiment_date,
        COALESCE(p.scope_name, p.instrument, '') AS microscope_type,
        s.slot_label,
        s.well_row,
        s.well_col,
        s.orientation,
        c.clutch_code
      FROM {T_IMAGING_SLOTS} s
      JOIN {T_IMAGING_PLATES} p ON p.id = s.plate_id
      LEFT JOIN {T_IMAGING_MEMB} m ON m.slot_id = s.id
      LEFT JOIN public.clutches c   ON c.id = m.clutch_id
      WHERE p.id = CAST(:pid AS uuid)
      ORDER BY s.well_row, s.well_col
      """
        ),
        cx,
        params={"pid": plate_id},
    )

st.download_button(
    "⬇︎ Download plate layout CSV",
    data=_csv_bytes(export_df),
    file_name=f"{plate_row['plate_code']}_layout.csv",
    mime="text/csv",
    type="secondary",
    use_container_width=True,
)