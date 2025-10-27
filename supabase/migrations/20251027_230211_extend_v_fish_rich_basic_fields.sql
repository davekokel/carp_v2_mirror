CREATE OR REPLACE VIEW public.v_fish_rich AS
SELECT
  f.fish_uuid::uuid               AS fish_uuid,
  f.fish_code::text               AS fish_code,
  COALESCE(f.fish_name, '')::text AS fish_name,
  COALESCE(f.fish_nickname, '')::text AS fish_nickname,
  COALESCE(f.genetic_background, '')::text AS genetic_background,
  COALESCE(f.line_building_stage, '')::text AS line_building_stage,
  COALESCE(f.date_birth::text, '')::text AS date_birth,
  NULL::text                      AS genotype_text
FROM public.fish f;
