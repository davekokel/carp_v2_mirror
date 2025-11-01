-- Fix v_fish to align with baseline table columns (no fish_name column in public.fish)
-- Keep a stable contract: fish_code, fish_name, fish_nickname, genetic_background, created_at
CREATE OR REPLACE VIEW public.v_fish AS
SELECT
  f.fish_code::text                               AS fish_code,
  ''::text                                        AS fish_name,
  ''::text                                        AS fish_nickname,
  ''::text                                        AS genetic_background,
  COALESCE(f.created_at, now())                   AS created_at
FROM public.fish f;
