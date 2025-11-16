BEGIN;

CREATE OR REPLACE VIEW public.v_fish_overview AS
SELECT
  fish_code_display,
  fish_code_raw,
  nickname,
  birthday,
  genetic_background,
  line_building_stage,
  genotype_pretty,
  markers,
  fluors,
  tags,
  fusions,
  n_fusions,
  dyes,
  created_at,
  transgene_canonical,
  transgene_nickname
FROM public.v_fish_overview_old;

COMMIT;
