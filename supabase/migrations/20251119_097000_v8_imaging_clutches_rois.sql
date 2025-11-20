BEGIN;

-- v8: canonical clutch → slot → ROI view

DROP VIEW IF EXISTS public.v_imaging_clutches_rois;

CREATE VIEW public.v_imaging_clutches_rois AS
SELECT
  -- clutch
  c.id::uuid                      AS clutch_id,
  c.clutch_code,
  c.clutch_date,
  c.estimated_egg_count,
  c.genotype_cross_label,
  c.genotype_base_codes           AS clutch_genotype_base_codes,
  c.genotype_allele_codes         AS clutch_genotype_alleles,
  c.genotype_pretty               AS clutch_genotype_pretty,
  c.source_system                 AS clutch_source_system,
  c.import_batch_id               AS clutch_import_batch_id,
  c.notes                         AS clutch_notes,

  -- membership (clutch ↔ slot)
  icm.id::uuid                    AS membership_id,
  icm.slot_id,
  icm.role                        AS membership_role,
  icm.embryo_count,
  icm.mount_notes,
  icm.created_at                  AS membership_created_at,
  icm.created_by                  AS membership_created_by,

  -- slot
  s.id::uuid                      AS imaging_slot_id,
  s.slot_index,
  s.slot_label,
  s.well_row,
  s.well_col,
  s.notes                         AS slot_notes,
  s.created_at                    AS slot_created_at,

  -- plate
  p.id::uuid                      AS imaging_plate_id,
  p.plate_code,
  p.experiment_date,
  p.experiment_name,
  p.instrument,
  p.format_code,
  p.notes                         AS plate_notes,
  p.created_at                    AS plate_created_at,
  p.created_by                    AS plate_created_by,

  -- ROI (may be NULL if membership has no ROI yet)
  r.roi_code,
  r.roi_index_within_slot         AS roi_index,
  r.roi_name,
  r.fish                          AS fish_code,
  r.date_experiment               AS roi_experiment_label,
  NULLIF(r.date_born, '')::date   AS roi_birthday,
  r.parent_female,
  r.parent_male,
  r.genotype_pretty               AS roi_genotype_pretty,
  r.genotype_base_codes           AS roi_genotype_base_codes,
  r.genotype_allele_codes         AS roi_genotype_alleles,
  r.genotype_marker_fluor_codes,
  r.genotype_marker_tag_codes,
  r.treatment_plasmid_base_codes,
  r.treatment_rna_base_codes,
  r.treatment_marker_fluor_codes,
  r.treatment_marker_tag_codes,
  r.all_marker_fluor_codes,
  r."Date born"                   AS roi_raw_date_born_text,
  r."ZF female genotype"          AS roi_raw_female_genotype,
  r."ZF male genotype"            AS roi_raw_male_genotype,
  r.roi_dir                       AS data_path,
  r."Data location"               AS roi_data_location

FROM public.imaging_clutch_memberships icm
JOIN public.clutches        c ON c.id = icm.clutch_id
JOIN public.imaging_slots   s ON s.id = icm.slot_id
JOIN public.imaging_plates  p ON p.id = s.plate_id
LEFT JOIN public.imaging_roi_annotations r
  ON r.slot_id = icm.slot_id;

COMMIT;
