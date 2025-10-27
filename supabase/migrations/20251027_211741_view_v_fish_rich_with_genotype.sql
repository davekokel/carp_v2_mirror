-- Ensure v_fish_rich has fish_uuid + genotype_text before v_cross_clutch_instances runs
CREATE OR REPLACE VIEW public.v_fish_rich AS
SELECT
  f.fish_uuid::uuid AS fish_uuid,
  f.fish_code::text AS fish_code,
  NULL::text        AS genotype_text
FROM public.fish f;
