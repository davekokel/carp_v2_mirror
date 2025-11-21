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
  -- labels without fallback logic
  cl.clutch_code AS clutch_label,
  CASE
    WHEN cr.cross_run_code IS NOT NULL AND cr.cross_date IS NOT NULL THEN
      cr.cross_run_code || ' @ ' || cr.cross_date::text
    ELSE NULL
  END AS cross_label
FROM public.clutches cl
LEFT JOIN public.crosses      cr ON cr.id = cl.cross_id
LEFT JOIN public.fish_instance ff ON ff.id = cr.female_fish_id
LEFT JOIN public.fish_instance mf ON mf.id = cr.male_fish_id;

COMMIT;
