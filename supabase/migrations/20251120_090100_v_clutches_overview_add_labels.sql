BEGIN;

CREATE OR REPLACE VIEW public.v_clutches_overview AS
SELECT
  cl.id AS clutch_id,
  cl.clutch_code,
  cl.clutch_date,
  cl.estimated_egg_count,
  cl.cross_id,
  cl.observed_genotype_code,
  cr.cross_date,
  cr.expected_genotype_code,
  ff.fish_code AS female_fish_code,
  mf.fish_code AS male_fish_code,
  cl.notes,
  cl.source_system,
  cl.import_batch_id,
  cl.created_at,
  -- new derived labels appended at the end
  COALESCE(
    cl.clutch_code,
    'CL-' || left(cl.id::text, 8)
  ) AS clutch_label,
  CASE
    WHEN cr.id IS NULL THEN NULL
    ELSE
      COALESCE(cr.cross_run_code, 'CR-' || left(cr.id::text, 8))
      || ' @ '
      || COALESCE(cr.cross_date::text, '')
  END AS cross_label
FROM public.clutches cl
LEFT JOIN public.crosses      cr ON cr.id = cl.cross_id
LEFT JOIN public.fish_instance ff ON ff.id = cr.female_fish_id
LEFT JOIN public.fish_instance mf ON mf.id = cr.male_fish_id;

COMMIT;
