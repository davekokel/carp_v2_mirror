DROP VIEW IF EXISTS public.v_fish CASCADE;
CREATE VIEW public.v_fish AS
SELECT
  f.fish_uuid        AS fish_uuid,
  f.fish_code,
  f.genetic_background,
  f.name,
  f.nickname,
  f.line_building_stage,
  f.created_at,
  f.created_by,
  f.date_birth,
  f.updated_at
FROM public.fish f;
