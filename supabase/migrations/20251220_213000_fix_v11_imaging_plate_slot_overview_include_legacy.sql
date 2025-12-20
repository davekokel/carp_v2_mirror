BEGIN;

CREATE OR REPLACE VIEW public.v11_imaging_plate_slot_overview AS
WITH slot_stats AS (
  SELECT
    s.id AS slot_id,
    count(ira.id) AS n_rois
  FROM public.imaging_slots s
  LEFT JOIN public.imaging_roi_annotations ira ON ira.slot_id = s.id
  GROUP BY s.id
),
base AS (
  SELECT
    p.id AS plate_id,
    p.plate_code,
    p.experiment_date,
    COALESCE(p.experiment_name, '') AS experiment_name,
    COALESCE(p.plate_note, '') AS plate_note,

    s.id AS slot_id,
    s.slot_label,
    s.slot_index,
    COALESCE(s.slot_note, '') AS slot_note,
    COALESCE(ss.n_rois, 0::bigint) AS n_rois,

    c.clutch_code,
    t.treat_code,
    t.treat_text,
    g.genotype_code,
    g.genotype_pretty
  FROM public.imaging_plates p
  JOIN public.imaging_slots s ON s.plate_id = p.id
  LEFT JOIN slot_stats ss ON ss.slot_id = s.id
  LEFT JOIN public.imaging_clutch_memberships m ON m.slot_id = s.id
  LEFT JOIN public.clutches c ON c.id = m.clutch_id
  LEFT JOIN public.treated_clutches_v11 tc ON tc.id = m.treated_clutch_id
  LEFT JOIN public.treatments t ON t.id = tc.treatment_id
  LEFT JOIN public.genotypes_v11 g ON g.id = c.genotype_v11_id
)
SELECT
  plate_id::text AS plate_id,
  plate_code,
  experiment_date,
  experiment_name,
  plate_note,
  slot_id::text AS slot_id,
  slot_label,
  slot_index,
  slot_note,
  n_rois,
  clutch_code,
  treat_code,
  treat_text,
  genotype_code,
  genotype_pretty
FROM base;

COMMIT;
