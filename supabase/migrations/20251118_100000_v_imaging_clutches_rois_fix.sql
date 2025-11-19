BEGIN;

CREATE OR REPLACE VIEW public.v_imaging_clutches_rois AS
SELECT
    c.id                      AS clutch_id,
    c.clutch_code,
    c.clutch_date,
    c.estimated_egg_count,
    c.notes                   AS clutch_notes,

    -- normalized mount/slot info
    n.sheet_row_index,
    n.date_mount,
    n.mount_id,
    n.slot_index_global,
    n.plate_index,
    n.slot_index,
    n.experimental_plate_id,
    n.experimental_slot_id,
    n.data_location,

    -- treatment info at clutch level
    t.id                      AS treatment_id,
    t.treat_code,
    t.treat_text,
    t.kind_code,
    t.notes                   AS treatment_notes,

    -- ROI-level info (now should actually be populated)
    r.id                      AS imaging_roi_id,
    r.slot_id,
    r.roi_index,
    r.roi_name,
    r.data_path,
    r.channel_info,
    r.notes                   AS roi_notes,
    r.created_at              AS roi_created_at,

    -- canned ROI marker rollups from v_roi_overview
    r.fluors_rollup           AS roi_fluors_rollup,
    r.markers_rollup          AS roi_markers_rollup

FROM public.clutches c
JOIN public.v_imaging_clutch_memberships_norm n
  ON n.clutch_id = c.id
LEFT JOIN public.join_clutch_treatments jct
  ON jct.clutch_id = c.id
LEFT JOIN public.treatments t
  ON t.id = jct.treatment_id
LEFT JOIN public.v_roi_overview r
  ON n.data_location IS NOT NULL
 AND r.data_path IS NOT NULL
 AND r.data_path LIKE n.data_location || '%'

WHERE c.clutch_code LIKE 'IMG_CLT_%';

COMMIT;
