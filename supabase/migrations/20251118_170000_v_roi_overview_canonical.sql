BEGIN;

-- Drop experimental imaging chain/marker views that depend on v_roi_overview.
-- These were used during legacy wrangling and will be replaced by cleaner views.
DROP VIEW IF EXISTS public.v_imaging_all_rois_markers_complete_roi_only CASCADE;
DROP VIEW IF EXISTS public.v_imaging_all_rois_markers_complete        CASCADE;
DROP VIEW IF EXISTS public.v_imaging_all_rois_markers                  CASCADE;
DROP VIEW IF EXISTS public.v_imaging_clutches_rois_inherited           CASCADE;
DROP VIEW IF EXISTS public.v_imaging_clutches_rois                     CASCADE;

-- Now we can safely replace v_roi_overview itself.
DROP VIEW IF EXISTS public.v_roi_overview CASCADE;

-- Minimal canonical ROI overview: one row per imaging ROI, joined to slot/plate/fish.
-- Genotype/marker fields are placeholders for now; they can be filled via a later view.
CREATE VIEW public.v_roi_overview AS
SELECT
  r.id                      AS imaging_roi_id,
  r.slot_id,
  r.roi_index,
  r.roi_name,
  r.roi_dir,
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

  NULL::text                AS genotype_code,
  NULL::text                AS genotype_name,
  NULL::text                AS genotype_base_codes,
  NULL::text                AS genotype_alleles_pretty,
  NULL::text                AS genotype_pretty,
  NULL::text                AS genotype_marker_fluors,
  NULL::text                AS genotype_marker_tags

FROM public.imaging_rois   AS r
JOIN public.imaging_slots  AS s ON s.id = r.slot_id
JOIN public.plates         AS p ON p.id = s.plate_id
JOIN public.fish_instance  AS f ON f.id = s.fish_id;

COMMIT;
