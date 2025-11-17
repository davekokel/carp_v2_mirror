BEGIN;

DROP VIEW IF EXISTS public.v_rois_overview;

CREATE VIEW public.v_rois_overview AS
WITH roi_file_counts AS (
  SELECT
    rf.roi_id,
    COUNT(*) AS n_files
  FROM public.imaging_roi_files AS rf
  GROUP BY rf.roi_id
)
SELECT
  r.id            AS roi_id,
  r.slot_id,
  s.slot_label,
  s.experiment_nickname,
  s.plate_id,
  p.plate_code,

  s.fish_id,
  f.fish_code,
  f.genotype_pretty,
  f.genotype_alleles_pretty,
  f.genotype_alleles_priority_pretty,
  f.genotype_base_codes,
  f.genotype_fluors,
  f.treatment_base_codes,
  f.treatment_fluors,
  f.all_base_codes,
  f.all_fluors,

  r.roi_index,
  r.roi_name,
  r.data_path,
  r.channel_info,
  r.notes       AS roi_notes,
  r.created_at  AS roi_created_at,

  COALESCE(rfc.n_files, 0) AS n_files

FROM public.imaging_rois AS r
JOIN public.imaging_slots AS s
  ON s.id = r.slot_id
LEFT JOIN public.plates AS p
  ON p.id = s.plate_id
LEFT JOIN public.v_fish_overview AS f
  ON f.fish_id = s.fish_id
LEFT JOIN roi_file_counts AS rfc
  ON rfc.roi_id = r.id;

COMMIT;
