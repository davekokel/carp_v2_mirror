BEGIN;

-- 1) Add plate/slot columns to the annotations table if they don't exist yet
ALTER TABLE public.imaging_roi_annotations
  ADD COLUMN IF NOT EXISTS plate_id_filled text,
  ADD COLUMN IF NOT EXISTS slot_id_filled  text;

-- 2) Recreate v_roi_overview to expose these columns
DROP VIEW IF EXISTS public.v_imaging_clutches_rois CASCADE;
DROP VIEW IF EXISTS public.v_roi_overview;

CREATE VIEW public.v_roi_overview AS
SELECT
  r.id                      AS imaging_roi_id,
  r.roi_index,
  r.roi_name,
  r.data_path,
  r.channel_info,
  r.notes                   AS roi_notes,
  r.created_at              AS roi_created_at,

  s.id                      AS slot_id,
  s.plate_id,
  s.slot_label,
  s.experiment_nickname,
  s.notes                   AS slot_notes,
  s.created_at              AS slot_created_at,

  p.plate_code,
  p.description             AS plate_description,
  p.created_at              AS plate_created_at,

  f.id                      AS fish_id,
  f.fish_code,
  f.fish_group_id,
  f.birthday,
  f.genetic_background,
  f.line_building_stage,
  f.nickname                AS fish_nickname,
  f.notes                   AS fish_notes,
  f.created_at              AS fish_created_at,

  -- Annotations from imaging_roi_annotations
  a.parent_female,
  a.parent_male,
  a.genotype_pretty,
  a.genotype_base_codes,
  a.genotype_allele_codes,
  a.genotype_marker_fluor_codes,
  a.genotype_marker_tag_codes,
  a.treatment_plasmid_base_codes,
  a.treatment_rna_base_codes,
  a.treatment_dye_base_codes,
  a.treatment_marker_fluor_codes,
  a.treatment_marker_tag_codes,
  a.all_marker_fluor_codes,
  a.plate_id_filled,
  a.slot_id_filled,
  a.source_system          AS annotation_source_system,
  a.import_batch_id        AS annotation_import_batch_id

FROM public.imaging_rois AS r
LEFT JOIN public.imaging_slots AS s
       ON s.id = r.slot_id
LEFT JOIN public.plates AS p
       ON p.id = s.plate_id
LEFT JOIN public.fish_instance AS f
       ON f.id = s.fish_id
LEFT JOIN public.imaging_roi_annotations AS a
       ON a.roi_dir = r.data_path;

COMMIT;
