BEGIN;

DROP VIEW IF EXISTS public.v11_imaging_plate_slot_overview CASCADE;

CREATE VIEW public.v11_imaging_plate_slot_overview AS
WITH roi_counts AS (
    SELECT
        a.slot_id,
        COUNT(*) AS n_rois
    FROM public.imaging_roi_annotations a
    GROUP BY a.slot_id
)
SELECT
    p.id          AS plate_id,
    p.plate_code,
    p.experiment_date,
    p.experiment_name,
    p.scope_name,
    p.scope_settings,
    p.plate_note,

    s.id          AS slot_id,
    s.slot_label,
    s.slot_index,
    s.slot_note,

    COALESCE(rc.n_rois, 0) AS n_rois,

    -- clutch-level
    g.clutch_code,

    -- treatment-level
    g.treatment_id,
    g.treat_code,
    g.treat_text,

    -- genotype-level
    g.genotype_v11_id,
    g.genotype_code,
    g.genotype_pretty,
    g.genotype_basecodes

FROM public.imaging_plates p
LEFT JOIN public.imaging_slots s
  ON s.plate_id = p.id

LEFT JOIN roi_counts rc
  ON rc.slot_id = s.id

LEFT JOIN public.imaging_clutch_memberships cm
  ON cm.slot_id = s.id

LEFT JOIN public.v11_clutch_star g
  ON g.clutch_id = cm.clutch_id

ORDER BY
    p.plate_code,
    s.slot_index;

COMMENT ON VIEW public.v11_imaging_plate_slot_overview IS
'v11 imaging overview: plate/slot with ROI count, clutch_code, treat_code, genotype_pretty, genotype_basecodes';

COMMIT;
