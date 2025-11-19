BEGIN;

DROP VIEW IF EXISTS public.v_imaging_clutches_rois;

CREATE VIEW public.v_imaging_clutches_rois AS
SELECT
  c.id                       AS clutch_id,
  c.clutch_code,
  c.clutch_date,
  m.date_born,
  m.zf_female_genotype_text,
  m.zf_male_genotype_text,

  m.experimental_plate_id,
  m.experimental_slot_id,
  m.plate_index,
  m.slot_index,
  m.slot_index_global,
  m.data_location,

  r.roi_code                 AS imaging_roi_id,
  ROW_NUMBER() OVER (
    PARTITION BY c.id
    ORDER BY r.plate_id_filled, r.slot_id_filled, r.roi_code
  )                          AS roi_index,
  r.roi_name,
  r.data_path,
  r.plate_id_filled          AS plate_code,
  r.slot_id_filled           AS slot_label,
  r.fish_code,
  NULL::text                 AS fish_nickname,
  r.birthday,
  r.genetic_background,

  NULL::text                 AS genotype_pretty,
  NULL::text                 AS genotype_base_codes,
  NULL::text                 AS genotype_alleles_pretty,
  NULL::text                 AS genotype_marker_fluors,
  NULL::text                 AS genotype_marker_tags,

  NULL::text                 AS treat_code,
  NULL::text                 AS treat_text,
  NULL::text                 AS treatment_plasmid_base_codes,
  NULL::text                 AS treatment_rna_base_codes,
  NULL::text                 AS treatment_dye_base_codes,
  NULL::text                 AS treatment_marker_fluor_codes,
  NULL::text                 AS treatment_marker_tag_codes
FROM public.clutches AS c
JOIN public.v_imaging_clutch_memberships_norm AS m
  ON m.clutch_id = c.id
JOIN public.v_roi_overview AS r
  ON r.plate_id_filled = m.experimental_plate_id
 AND r.slot_id_filled  = m.experimental_slot_id;

COMMIT;
