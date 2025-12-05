# carp_app/ui/pages/230_⚙️_assign_fish_to_plates_slots.py
# ⚙️ Assign clutches to imaging plates & slots (v11 imaging schema)

from __future__ import annotations

import sys, pathlib, os, re, io
from typing import Dict, Tuple, Set, List, Any, Optional
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

PLATE_ORIENTATIONS: Dict[str, List[str]] = {
    "mosaic": ["dorsal_head", "dorsal_spine", "lateral_yolk_left", "lateral_yolk_right"],
    "isoar": ["dorsal", "lateral"],
}
DEFAULT_ORIENTATIONS = ["dorsal", "lateral"]

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


def _generate_slot_grid_size(microscope_type: str) -> Tuple[int, int]:
    mt = (microscope_type or "").strip().lower()
    if mt == "mosaic":
        return (1, 6)
    if mt == "isoar":
        return (5, 5)
    return (3, 3)


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
    PLATE-YYMMDD-NN with NN per-day.
    """
    yymmdd = date_mount.strftime("%y%m%d")
    prefix = f"PLATE-{yymmdd}-"
    with eng().begin() as cx:
        existing = pd.read_sql(
            text(
                """
                SELECT plate_code
                FROM public.imaging_plates
                WHERE plate_code LIKE :prefix
                """
            ),
            cx,
            params={"prefix": prefix + "%"},
        )
        used = set()
        for pc in existing["plate_code"]:
            parts = str(pc).split("-")
            if len(parts) >= 3 and parts[-1].isdigit():
                used.add(int(parts[-1]))
        n = 1
        while n in used:
            n += 1
        plate_code = f"{prefix}{n:02d}"
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
            {"code": plate_code, "d": date_mount, "instr": microscope_type, "who": created_by},
        ).scalar()
    return str(plate_id), str(plate_code)


# --- sanity -------------------------------------------------------------------
miss = []
for obj in [T_IMAGING_PLATES, T_IMAGING_SLOTS, T_IMAGING_MEMB]:
    if not _exists_table(obj):
        miss.append(obj)
if miss:
    st.error("Required object not found: " + ", ".join(miss))
    st.stop()

# ════════════════════════════════════════════════════════
# STEP 0 — CHOOSE PLATE (SELECT OR CREATE)
# ════════════════════════════════════════════════════════
st.subheader("0) Choose imaging plate", anchor=False)

mode = st.radio(
    "Plate mode",
    ["Select existing plate", "Create new plate"],
    horizontal=True,
    key="plate_mode",
)

# reuse previously selected/created plate across reruns
plate_id: Optional[str] = st.session_state.get("assign_plate_id")
plate_code: Optional[str] = st.session_state.get("assign_plate_code")

if mode == "Select existing plate":
    with eng().begin() as cx:
        df_plates = pd.read_sql(
            text(
                """
                SELECT
                  id::text        AS plate_id,
                  plate_code,
                  experiment_date,
                  COALESCE(scope_name, instrument, '') AS scope_name,
                  experiment_name
                FROM public.imaging_plates
                ORDER BY experiment_date DESC NULLS LAST, plate_code DESC
                LIMIT 200
                """
            ),
            cx,
        )
    if df_plates.empty:
        st.info("No imaging plates found yet.")
        st.stop()
    view = df_plates.copy()
    view.insert(0, "✓ Select", False)
    grid = st.data_editor(
        view[
            ["✓ Select", "plate_code", "experiment_date", "experiment_name", "scope_name"]
        ],
        key="assign_existing_plates",
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        column_config={
            "✓ Select":       st.column_config.CheckboxColumn("✓", default=False),
            "plate_code":     st.column_config.TextColumn("Plate", disabled=True),
            "experiment_date": st.column_config.DateColumn("Date", disabled=True),
            "experiment_name": st.column_config.TextColumn("Experiment", disabled=True),
            "scope_name":     st.column_config.TextColumn("Scope", disabled=True),
        },
    )
    mask = grid["✓ Select"] == True if "✓ Select" in grid.columns else pd.Series(False, index=grid.index)
    if mask.any():
        idx = grid.index[mask][0]
        row = df_plates.loc[idx]
        plate_id = row["plate_id"]
        plate_code = row["plate_code"]
        st.session_state["assign_plate_id"] = plate_id
        st.session_state["assign_plate_code"] = plate_code

elif mode == "Create new plate":
    today = pd.Timestamp.today().date()
    c1, c2 = st.columns([1, 1])
    with c1:
        date_mount = st.date_input("Mount / experiment date", value=today, key="mount_date")
    with c2:
        microscope_type_sel = st.selectbox(
            "Microscope type",
            options=["mosaic", "isoar"],
            index=0,
        )
    creator = (
        getattr(user, "email", None)
        or os.getenv("USER")
        or os.getenv("USERNAME")
        or "system"
    )
    if st.button("➕ Create imaging plate", type="primary"):
        plate_id, plate_code = _create_imaging_plate(date_mount, microscope_type_sel, creator)
        _ = _auto_generate_slots(plate_id, microscope_type_sel)
        st.session_state["assign_plate_id"] = plate_id
        st.session_state["assign_plate_code"] = plate_code
        st.success(f"Created {plate_code} with default slots.")

# guard: if we still don't have a plate, stop here
if not plate_id:
    st.caption("Select or create a plate above to continue.")
    st.stop()

assert plate_id is not None and plate_code is not None

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
    slots = _auto_generate_slots(plate_id, plate_row["microscope_type"] or "mosaic")

slots = slots.copy()
slots["well_row"] = slots["well_row"].fillna(1).astype(int)
slots["well_col"] = slots["well_col"].fillna(1).astype(int)
n_rows = int(slots["well_row"].max())
n_cols = int(slots["well_col"].max())

st.caption(
    f"Current plate: {plate_row['plate_code']} • date={plate_row['experiment_date']} • "
    f"microscope={plate_row['microscope_type'] or 'n/a'} • layout={n_rows}×{n_cols}"
)

all_cells = {(int(r), int(c)) for r, c in zip(slots["well_row"], slots["well_col"])}


# ════════════════════════════════════════════════════════
# STEP 1 — PICK TREATED CLUTCHES (WITH GENOTYPE + MARKERS)
# ════════════════════════════════════════════════════════
st.subheader("1) Pick treated clutches", anchor=False)

clutch_q = st.text_input(
    "Search treated clutches (code / parent clutch / treatment / genotype / markers)",
    "",
)

with eng().begin() as cx:
    df_groups = pd.read_sql(
        text(
            """
            WITH treated AS (
              SELECT
                tc.id::uuid                  AS treated_clutch_id,
                tc.treated_clutch_code,
                c.id::uuid                   AS clutch_id,
                c.clutch_code,
                c.clutch_date,

                g.genotype_basecodes::text   AS genotype_basecodes,
                g.genotype_pretty::text      AS genotype_pretty,

                t.treat_code                 AS treatment_code,
                ts.all_fluor_tag_rollup,
                ts.all_organelle_fluor_rollup,

                -- what the UI will type into the wells
                tc.treated_clutch_code       AS assign_code
              FROM public.treated_clutches_v11 tc
              JOIN public.clutches c
                ON c.id = tc.clutch_id
              LEFT JOIN public.genotypes_v11 g
                ON g.id = c.genotype_v11_id
              LEFT JOIN public.treatments t
                ON t.id = tc.treatment_id
              LEFT JOIN public.v11_treatment_star ts
                ON ts.treatment_id = t.id::text
              WHERE c.clutch_date >= (current_date - INTERVAL '14 days')
                AND COALESCE(c.source_system, '') <> 'legacy_imaging'
            ),
            untreated AS (
                SELECT
                    NULL::uuid                    AS treated_clutch_id,
                    NULL::text                    AS treated_clutch_code,
                    c.id::uuid                    AS clutch_id,
                    c.clutch_code,
                    c.clutch_date,

                    g.genotype_basecodes::text    AS genotype_basecodes,
                    g.genotype_pretty::text       AS genotype_pretty,

                    NULL::text                    AS treatment_code,
                    ''::text                      AS all_fluor_tag_rollup,
                    ''::text                      AS all_organelle_fluor_rollup,

                    -- for untreated, assign using the parent clutch code
                    c.clutch_code                 AS assign_code
                FROM public.clutches c
                LEFT JOIN public.genotypes_v11 g
                    ON g.id = c.genotype_v11_id
                WHERE c.clutch_date >= (current_date - INTERVAL '14 days')
                    AND COALESCE(c.source_system, '') <> 'legacy_imaging'
                ),
            all_groups AS (
              SELECT * FROM treated
              UNION ALL
              SELECT * FROM untreated
            )
            SELECT
              treated_clutch_id::text,
              treated_clutch_code,
              clutch_id::text,
              clutch_code,
              clutch_date,
              genotype_pretty,
              genotype_basecodes,
              treatment_code,
              all_fluor_tag_rollup,
              all_organelle_fluor_rollup,
              assign_code
            FROM all_groups
            WHERE (
                 :q IS NULL
              OR assign_code                    ILIKE :ql
              OR clutch_code                    ILIKE :ql
              OR COALESCE(treatment_code,'')    ILIKE :ql
              OR COALESCE(genotype_pretty,'')   ILIKE :ql
              OR COALESCE(genotype_basecodes,'') ILIKE :ql
              OR COALESCE(all_fluor_tag_rollup,'')       ILIKE :ql
              OR COALESCE(all_organelle_fluor_rollup,'') ILIKE :ql
            )
            ORDER BY clutch_date DESC, assign_code
            LIMIT 500;
            """
        ),
        cx,
        params={
            "q": clutch_q.strip() or None,
            "ql": f"%{clutch_q.strip()}%" if clutch_q.strip() else None,
        },
    )

if df_groups.empty:
    st.info("No clutches (treated or untreated) in the last 2 weeks match your search.")
    selected_groups: List[Dict[str, Any]] = []
else:
    t_view = df_groups.fillna("").copy()
    t_view.insert(0, "✓ Select", False)
    t_grid = st.data_editor(
        t_view[
            [
                "✓ Select",
                "assign_code",
                "treated_clutch_code",
                "clutch_code",
                "clutch_date",
                "treatment_code",
                "genotype_pretty",
                "genotype_basecodes",
                "all_fluor_tag_rollup",
                "all_organelle_fluor_rollup",
            ]
        ],
        key="treated_clutch_picker",
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        height=260,
        column_config={
            "✓ Select":              st.column_config.CheckboxColumn("✓", default=False),
            "assign_code":           st.column_config.TextColumn("Code (treated or parent)", disabled=True),
            "treated_clutch_code":   st.column_config.TextColumn("Treated clutch", disabled=True),
            "clutch_code":           st.column_config.TextColumn("Parent clutch", disabled=True),
            "clutch_date":           st.column_config.DateColumn("Date", disabled=True),
            "treatment_code":        st.column_config.TextColumn("Treatment", disabled=True),
            "genotype_pretty":       st.column_config.TextColumn("Genotype (pretty)", disabled=True, width="large"),
            "genotype_basecodes":    st.column_config.TextColumn("Genotype basecodes", disabled=True, width="large"),
            "all_fluor_tag_rollup":  st.column_config.TextColumn("fluor::tag(tag_pos)", disabled=True, width="large"),
            "all_organelle_fluor_rollup": st.column_config.TextColumn("organelle-fluor", disabled=True, width="large"),
        },
    )
    mask = t_grid["✓ Select"] == True if "✓ Select" in t_grid.columns else pd.Series(False, index=t_grid.index)
    selected_groups = df_groups.loc[mask].to_dict(orient="records") if mask.any() else []

st.caption(f"Selected groups (treated or plain clutches): {len(selected_groups)}")


# ════════════════════════════════════════════════════════
# STEP 2 — ASSIGN TREATED CLUTCHES TO WELLS
# ════════════════════════════════════════════════════════
st.subheader("2) Assign treated clutches to wells", anchor=False)
st.caption("Example syntax: A01:A03, B01:B02")

with eng().begin() as cx:
    existing_m = pd.read_sql(
        text(
            f"""
            SELECT
              s.well_row,
              s.well_col,
              tc.treated_clutch_code
            FROM {T_IMAGING_MEMB} m
            JOIN public.imaging_slots s
              ON s.id = m.slot_id
            JOIN public.treated_clutches_v11 tc
              ON tc.id = m.treated_clutch_id
            WHERE s.plate_id = CAST(:pid AS uuid)
            """
        ),
        cx,
        params={"pid": plate_id},
    )

initial_map: Dict[str, str] = {}
if not existing_m.empty:
    by_tc = existing_m.groupby("treated_clutch_code")
    for tcode, sub in by_tc:
        cells = {(int(r), int(c)) for r, c in zip(sub["well_row"], sub["well_col"])}
        initial_map[tcode] = _cells_to_expr(cells)

clutch_map: Dict[str, str] = {}
if not selected_groups:
    st.info("Select treated clutches or plain clutches above to assign.")
else:
    cols = st.columns(2)
    for i, g in enumerate(selected_groups):
        code = g["assign_code"]
        default_expr = initial_map.get(code, "")
        label = g["treated_clutch_code"] or g["clutch_code"]
        with cols[i % 2]:
            clutch_map[code] = st.text_input(
                f"{label} — wells",
                value=default_expr,
                key=f"tcells_{code}",
            )


# ════════════════════════════════════════════════════════
# STEP 3 — ASSIGN ORIENTATIONS
# ════════════════════════════════════════════════════════
st.subheader("3) Assign orientations to wells", anchor=False)
st.caption("Example syntax: A01:A03, B01:B02")

ori_map: Dict[str, str] = {}
ori_cols = st.columns(2)
for i, ori in enumerate(PLATE_ORIENTATIONS.get(plate_row["microscope_type"], DEFAULT_ORIENTATIONS)):
    with ori_cols[i % 2]:
        ori_map[ori] = st.text_input(f"{ori} — wells", key=f"ori_{ori}")


# ════════════════════════════════════════════════════════
# STEP 4 — PREVIEW
# ════════════════════════════════════════════════════════
st.subheader("4) Preview layout", anchor=False)

preview = slots[["slot_label", "well_row", "well_col", "orientation"]].copy()
preview["treated_clutch_code"] = ""
preview["clutch_code"] = ""

with eng().begin() as cx:
    memb_df2 = pd.read_sql(
        text(
            f"""
      SELECT
        s.well_row,
        s.well_col,
        c.clutch_code,
        tc.treated_clutch_code
      FROM {T_IMAGING_MEMB} m
      JOIN public.imaging_slots s ON s.id = m.slot_id
      JOIN public.clutches c      ON c.id = m.clutch_id
      LEFT JOIN public.treated_clutches_v11 tc
        ON tc.id = m.treated_clutch_id
      WHERE s.plate_id = CAST(:pid AS uuid)
      """
        ),
        cx,
        params={"pid": plate_id},
    )

if not memb_df2.empty:
    for r, c, tcode, ccode in zip(
        memb_df2["well_row"],
        memb_df2["well_col"],
        memb_df2["treated_clutch_code"],
        memb_df2["clutch_code"],
    ):
        mask = (preview["well_row"] == int(r)) & (preview["well_col"] == int(c))
        if str(tcode or "").strip():
            preview.loc[mask, "treated_clutch_code"] = tcode
        preview.loc[mask, "clutch_code"] = ccode

for tcode, expr in (clutch_map or {}).items():
    if not (tcode and expr.strip()):
        continue
    for (r, c) in _parse_selection(expr):
        mask = (preview["well_row"] == int(r)) & (preview["well_col"] == int(c))
        preview.loc[mask, "treated_clutch_code"] = tcode

for ori, expr in (ori_map or {}).items():
    if not (ori and expr.strip()):
        continue
    for (r, c) in _parse_selection(expr):
        mask = (preview["well_row"] == int(r)) & (preview["well_col"] == int(c))
        preview.loc[mask, "orientation"] = ori

st.dataframe(
    preview[["slot_label", "treated_clutch_code", "clutch_code", "orientation"]],
    hide_index=True,
    use_container_width=True,
    height=260,
)


# ════════════════════════════════════════════════════════
# STEP 5 — SAVE
# ════════════════════════════════════════════════════════
st.subheader("5) Save mappings", anchor=False)

def _apply_mappings(
    plate_id: str,
    clutch_map: Dict[str, str],
    ori_map: Dict[str, str],
) -> Tuple[int, int, int]:
    n_c = n_o = n_over = 0

    with eng().begin() as cx:
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
            for r, c, sid in zip(
                slots_df["well_row"], slots_df["well_col"], slots_df["slot_id"]
            )
        }

        memb_df = pd.read_sql(
            text(
                f"""
          SELECT
            m.clutch_id::text,
            m.treated_clutch_id::text,
            s.id::text AS slot_id
          FROM {T_IMAGING_MEMB} m
          JOIN public.imaging_slots s ON s.id = m.slot_id
          WHERE s.plate_id = CAST(:pid AS uuid)
        """
            ),
            cx,
            params={"pid": plate_id},
        )
        existing_memb: set[Tuple[str, str]] = {
            (sid, cid)
            for cid, tcid, sid in zip(
                memb_df["clutch_id"],
                memb_df["treated_clutch_id"],
                memb_df["slot_id"],
            )
        }

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
        existing_ori: Dict[str, str] = {
            sid: (o or "")
            for sid, o in zip(slots_ori_df["slot_id"], slots_ori_df["orientation"])
        }

        def treated_mapping_of(code: str) -> Tuple[Optional[str], Optional[str]]:
            if not code:
                return None, None
            row = cx.execute(
                text(
                    """
                    SELECT
                      tc.id::text AS treated_clutch_id,
                      c.id::text  AS clutch_id
                    FROM public.treated_clutches_v11 tc
                    JOIN public.clutches c
                      ON c.id = tc.clutch_id
                    WHERE tc.treated_clutch_code = :code
                    LIMIT 1
                    """
                ),
                {"code": code},
            ).fetchone()
            if row:
                return row._mapping["treated_clutch_id"], row._mapping["clutch_id"]

            clutch_id = cx.execute(
                text(
                    """
                    SELECT id::text
                    FROM public.clutches
                    WHERE clutch_code = :code
                    LIMIT 1
                    """
                ),
                {"code": code},
            ).scalar()
            return None, clutch_id

        who = (
            getattr(user, "email", None)
            or os.getenv("USER")
            or os.getenv("USERNAME")
            or "system"
        )

        for code, expr in (clutch_map or {}).items():
            if not (code and expr.strip()):
                continue
            treated_id, cid = treated_mapping_of(code)
            if not cid:
                raise RuntimeError(f"Unknown treated/parent clutch code: {code}")

            for (r, c) in _parse_selection(expr):
                sid = slot_map.get((r, c))
                if not sid:
                    continue
                key = (sid, cid)
                if key in existing_memb:
                    continue
                cx.execute(
                    text(
                        f"""
                  INSERT INTO {T_IMAGING_MEMB}
                    (id, clutch_id, treated_clutch_id, slot_id, role, embryo_count, mount_notes, created_at, created_by)
                  VALUES (
                    gen_random_uuid(),
                    CAST(:cid AS uuid),
                    CAST(:tcid AS uuid),
                    CAST(:sid AS uuid),
                    NULL,
                    NULL,
                    NULL,
                    now(),
                    :who
                  )
                """
                    ),
                    {"cid": cid, "tcid": treated_id, "sid": sid, "who": who},
                )
                existing_memb.add(key)
                n_c += 1

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



if st.button("💾 Save mappings", type="primary"):
    try:
        n_c, n_o, n_over = _apply_mappings(plate_id, clutch_map, ori_map)
        st.success(
            f"Saved mappings for plate {plate_code}: "
            f"treated clutches→{n_c}, orientations→{n_o}, overwrote {n_over} existing orientation(s)."
        )
    except Exception as e:
        st.error(f"Save failed: {type(e).__name__}: {e}")


st.divider()
st.subheader("Export plate layout CSV", anchor=False)
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
        c.clutch_code,
        tc.treated_clutch_code
      FROM {T_IMAGING_SLOTS} s
      JOIN {T_IMAGING_PLATES} p ON p.id = s.plate_id
      LEFT JOIN {T_IMAGING_MEMB} m ON m.slot_id = s.id
      LEFT JOIN public.clutches c   ON c.id = m.clutch_id
      LEFT JOIN public.treated_clutches_v11 tc
        ON tc.id = m.treated_clutch_id
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
    file_name=f"{plate_code}_layout.csv",
    type="secondary",
    use_container_width=True,
)