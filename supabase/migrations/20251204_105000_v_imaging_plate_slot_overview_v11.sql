BEGIN;

-- Drop the old view if it exists
DROP VIEW IF EXISTS public.v_imaging_plate_slot_overview;

-- Recreate using v11 clutch/treatment/label stack
CREATE VIEW public.v_imaging_plate_slot_overview AS
WITH base_slots AS (
  SELECT
    p.id::text                         AS plate_id,
    p.plate_code,
    p.experiment_date,
    p.experiment_name,
    COALESCE(p.plate_note, p.notes)    AS plate_note,
    s.id::text                         AS slot_id,
    s.slot_label,
    s.slot_index,
    COALESCE(s.slot_note, s.notes)     AS slot_note
  FROM public.imaging_plates p
  JOIN public.imaging_slots s
    ON s.plate_id = p.id
),
roi_counts AS (
  SELECT
    ira.slot_id::text                  AS slot_id,
    COUNT(*)::bigint                   AS n_rois
  FROM public.imaging_roi_annotations ira
  GROUP BY ira.slot_id
),
membership AS (
  -- We treat the NULL/primary membership as the "main" clutch for this slot.
  SELECT
    icm.slot_id::text                  AS slot_id,
    c.clutch_code,
    tc.treated_clutch_code,
    t.treat_code                       AS treatment_code,
    t.treat_text                       AS treatment_text
  FROM public.imaging_clutch_memberships icm
  LEFT JOIN public.clutches c
    ON c.id = icm.clutch_id
  LEFT JOIN public.treated_clutches_v11 tc
    ON tc.id = icm.treated_clutch_id
  LEFT JOIN public.treatments t
    ON t.id = tc.treatment_id
  WHERE icm.role IS NULL OR icm.role = 'primary'
),
labels AS (
  SELECT
    cls.clutch_code,
    cls.treated_clutch_code,
    cls.genotype_code,
    cls.genotype_basecodes,
    cls.genotype_pretty,
    cls.genotype_tg_style,
    cls.genotype_fluortag_style,
    cls.genotype_fluororganelle_style,
    cls.label_tg_style,
    cls.label_fluortag_style,
    cls.label_fluororganelle_style
  FROM public.v11_clutch_label_star cls
)
SELECT
  bs.plate_id,
  bs.plate_code,
  bs.experiment_date,
  bs.experiment_name,
  bs.plate_note,
  bs.slot_id,
  bs.slot_label,
  bs.slot_index,
  bs.slot_note,
  COALESCE(rc.n_rois, 0)              AS n_rois,
  m.clutch_code,
  m.treated_clutch_code,
  m.treatment_code,
  m.treatment_text,
  l.genotype_code,
  l.genotype_basecodes,
  l.genotype_pretty,
  l.genotype_tg_style,
  l.genotype_fluortag_style,
  l.genotype_fluororganelle_style,
  l.label_tg_style,
  l.label_fluortag_style,
  l.label_fluororganelle_style
FROM base_slots bs
LEFT JOIN roi_counts rc
  ON rc.slot_id = bs.slot_id
LEFT JOIN membership m
  ON m.slot_id = bs.slot_id
LEFT JOIN LATERAL (
  SELECT l.*
  FROM labels l
  WHERE l.clutch_code = m.clutch_code
    AND (
      m.treated_clutch_code IS NULL
      OR COALESCE(l.treated_clutch_code, '') = COALESCE(m.treated_clutch_code, '')
    )
  ORDER BY
    (COALESCE(l.treated_clutch_code, '') = COALESCE(m.treated_clutch_code, '')) DESC,
    l.treated_clutch_code NULLS LAST
  LIMIT 1
) l ON true
ORDER BY
  bs.experiment_date DESC NULLS LAST,
  bs.plate_code,
  bs.slot_index;

COMMIT;
