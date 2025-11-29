BEGIN;

DROP VIEW IF EXISTS public.v11_fish_instance_star_enriched;

CREATE VIEW public.v11_fish_instance_star_enriched AS
SELECT
  s.fish_instance_id,
  s.fish_code,
  s.line_id,
  s.line_instance_code,
  s.birthday,
  s.fish_notes,
  s.fish_created_at,
  s.line_code,
  s.line_nickname,
  s.genetic_background,
  s.line_building_stage,
  s.line_created_at,
  s.fish_group_id,
  s.group_code,
  s.group_instance_code,
  s.genotype_pretty,
  s.fluor_codes,
  s.tag_codes,
  s.organelle_fluors,
  s.tank_id,
  s.tank_code,
  s.tank_status,
  s.tank_created_at,
  s.treatment_code,

  -- basecodes as before
  s.genotype_basecode_code,

  -- NEW: allele-level genotype codes from line rollups
  COALESCE(s.genotype_transgene_allele_code,
           la.allele_canonical_rollup) AS genotype_transgene_allele_code,

  s.treatments_and_transgenes,
  s.all_fluor_tag_rollup,
  s.all_organelle_fluor_rollup,

  -- counts
  CASE
    WHEN s.fluor_codes IS NULL OR btrim(s.fluor_codes) = '' THEN 0
    ELSE array_length(string_to_array(s.fluor_codes, ','), 1)
  END AS n_fluors,
  CASE
    WHEN s.genotype_basecode_code IS NULL OR btrim(s.genotype_basecode_code) = '' THEN 0
    ELSE array_length(string_to_array(s.genotype_basecode_code, ';'), 1)
  END AS n_transgenes

FROM public.v11_fish_instance_star s
LEFT JOIN public.v11_line_allele_rollups la
  ON la.line_id = s.line_id;

COMMIT;
