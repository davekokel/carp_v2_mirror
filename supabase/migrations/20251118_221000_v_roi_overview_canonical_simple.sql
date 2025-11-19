BEGIN;

DROP VIEW IF EXISTS public.v_roi_overview;

CREATE VIEW public.v_roi_overview AS
SELECT
  roi_code,
  plate_id_filled,
  slot_id_filled,
  date_experiment,
  fish                         AS fish_code,
  roi_name,
  parent_female,
  parent_male,
  date_born                    AS birthday,
  NULL::text                   AS genetic_background,
  all_marker_fluor_codes,
  roi_dir                      AS data_path
FROM public.imaging_roi_annotations;

COMMIT;
