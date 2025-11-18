BEGIN;

CREATE OR REPLACE VIEW public.v_fish_overview_pretty AS
SELECT
  fish_id,
  fish_code,
  birthday,
  genetic_background,
  line_building_stage,
  nickname,
  notes,
  created_at,
  COALESCE(genotype_pretty, genetic_background) AS genotype_pretty,
  genotype_alleles_pretty,
  genotype_alleles_priority_pretty,
  genotype_base_codes,
  genotype_fluors,
  treatment_base_codes,
  treatment_rna_codes,
  treatment_fluors,
  all_base_codes,
  all_fluors
FROM public.v_fish_overview;

COMMIT;
