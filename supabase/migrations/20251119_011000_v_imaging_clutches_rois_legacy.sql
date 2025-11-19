BEGIN;

DROP VIEW IF EXISTS public.v_imaging_clutches_rois;

CREATE VIEW public.v_imaging_clutches_rois AS
SELECT
  c.id                             AS clutch_id,
  c.clutch_code,
  c.clutch_date,
  c.estimated_egg_count,
  c.source_system                  AS clutch_source_system,
  c.import_batch_id                AS clutch_import_batch_id,

  m.id                             AS membership_id,
  m.date_born                      AS membership_date_born,
  m.zf_female_genotype_text,
  m.zf_male_genotype_text,
  m.data_location,

  r.roi_code                       AS imaging_roi_id,
  r.plate_id_filled                AS plate_code,
  r.slot_id_filled                 AS slot_label,
  r.fish_code,
  r.roi_name,
  r.parent_female                  AS roi_parent_female,
  r.parent_male                    AS roi_parent_male,
  r.birthday                       AS roi_birthday,
  r.all_marker_fluor_codes,
  r.data_path

FROM public.clutches                    AS c
JOIN public.imaging_clutch_memberships  AS m
  ON m.clutch_id = c.id
JOIN public.v_roi_overview              AS r
  ON r.data_path = m.data_location
WHERE
  c.source_system = 'legacy_imaging'
  AND m.source_system = 'legacy_imaging';

COMMIT;
