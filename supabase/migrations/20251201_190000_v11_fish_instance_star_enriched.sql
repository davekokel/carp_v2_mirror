BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_instance_star_enriched AS
SELECT
  fis.fish_instance_id,
  fis.fish_code,
  fis.line_id,
  fis.line_instance_code,
  fis.birthday,
  fis.fish_notes,
  fis.fish_created_at,
  fis.line_code,
  fis.line_nickname,
  fis.genetic_background,
  fis.line_building_stage,
  fis.line_created_at,
  fis.fish_group_id,
  fis.group_code,
  fis.group_instance_code,
  fis.genotype_pretty,

  -- enriched markers from line-level view when per-fish columns are empty
  COALESCE(NULLIF(fis.fluor_codes, ''), lf.fluor_codes) AS fluor_codes,
  COALESCE(NULLIF(fis.tag_codes,   ''), lf.tag_codes)   AS tag_codes,
  fis.organelle_fluors,

  fis.tank_id,
  fis.tank_code,
  fis.tank_status,
  fis.tank_created_at,
  fis.treatment_code,
  fis.genotype_basecode_code,
  fis.genotype_transgene_allele_code,
  fis.treatments_and_transgenes,
  fis.all_fluor_tag_rollup,
  fis.all_organelle_fluor_rollup
FROM public.v11_fish_instance_star fis
LEFT JOIN public.v10_line_fluors lf
  ON lf.line_id = fis.line_id;

COMMIT;
