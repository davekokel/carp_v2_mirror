BEGIN;

DROP VIEW IF EXISTS public.v11_imaging_plate_slot_overview CASCADE;

WITH slot_base AS (
  SELECT
    p.id::text             AS plate_id,
    p.plate_code,
    p.experiment_date,
    p.experiment_name,
    p.scope_name,
    p.scope_settings,
    p.plate_note,

    s.id::text             AS slot_id,
    s.slot_label,
    s.slot_index,
    s.slot_note
  FROM public.imaging_slots s
  JOIN public.imaging_plates p
    ON p.id = s.plate_id
),

roi_counts AS (
  SELECT
    r.slot_id::text AS slot_id,
    COUNT(*)        AS n_rois
  FROM public.imaging_roi_annotations r
  GROUP BY r.slot_id
),

clutch_memberships AS (
  SELECT
    m.slot_id::text         AS slot_id,
    c.clutch_code,
    cs.treatment_id,
    cs.treat_code,
    cs.treat_text,
    cs.genotype_v11_id,
    cs.genotype_code,
    cs.genotype_pretty
  FROM public.imaging_clutch_memberships m
  LEFT JOIN public.clutches c
    ON c.id = m.clutch_id
  LEFT JOIN public.v11_clutch_star cs
    ON cs.clutch_id = c.id
)

SELECT
  sb.*,
  COALESCE(rc.n_rois, 0)::int          AS n_rois,
  cm.clutch_code,
  cm.treatment_id,
  cm.treat_code,
  cm.treat_text,
  cm.genotype_v11_id,
  cm.genotype_code,
  cm.genotype_pretty

FROM slot_base sb
LEFT JOIN roi_counts rc
  ON rc.slot_id = sb.slot_id
LEFT JOIN clutch_memberships cm
  ON cm.slot_id = sb.slot_id

ORDER BY sb.experiment_date DESC NULLS LAST,
         sb.plate_code,
         sb.slot_index,
         sb.slot_label;

COMMIT;
