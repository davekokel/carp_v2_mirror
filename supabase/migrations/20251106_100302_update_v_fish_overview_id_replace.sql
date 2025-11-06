BEGIN;
CREATE OR REPLACE VIEW public.v_fish_overview_id
(fish_code, nickname, birthday, genetic_background, line_building_stage,
 allele_count, allele_codes, allele_nicknames, transgenes, genotype_rollup,
 fusion_rollup, fluor_rollup, tag_rollup, dye_rollup, created_at)
AS
SELECT
  f.fish_code,
  f.nickname,
  f.dob                                    AS birthday,
  COALESCE(f.genetic_background,'')        AS genetic_background,
  COALESCE(f.line_building_stage,'')       AS line_building_stage,
  COALESCE(g.allele_count,0)               AS allele_count,
  COALESCE(g.allele_codes,'')              AS allele_codes,
  COALESCE(g.allele_nicknames,'')          AS allele_nicknames,
  COALESCE(g.transgenes,'')                AS transgenes,
  COALESCE(g.genotype_rollup,'')           AS genotype_rollup,
  COALESCE(m.fusion_rollup,'')             AS fusion_rollup,
  COALESCE(m.fluor_rollup,'')              AS fluor_rollup,
  COALESCE(m.tag_rollup,'')                AS tag_rollup,
  COALESCE(m.dye_rollup,'')                AS dye_rollup,
  f.created_at
FROM public.fish f
LEFT JOIN public.v_fish_genotype_rollup_by_ids g ON g.fish_id = f.id
LEFT JOIN public.v_fish_marker_rollup_by_ids   m ON m.fish_id = f.id;
COMMIT;
