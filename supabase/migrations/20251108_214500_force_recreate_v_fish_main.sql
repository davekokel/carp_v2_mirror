BEGIN;

DROP VIEW IF EXISTS public.v_fish_main;

CREATE VIEW public.v_fish_main AS
SELECT
  f.fish_code,
  f.nickname,
  f.dob,
  COALESCE(f.genetic_background,'')  AS genetic_background,
  COALESCE(f.line_building_stage,'') AS line_building_stage,
  jfta.transgene_base_code,
  jfta.allele_number,
  ta.allele_name,
  ta.allele_nickname,
  COALESCE(NULLIF(ta.allele_name,''), jfta.transgene_base_code||'-'||LPAD(jfta.allele_number::text,2,'0')) AS transgene_pretty_nickname,
  jfta.transgene_base_code AS transgene_pretty_name,
  u.genotype_pretty,
  r.fluors,
  r.tags,
  r.dyes
FROM public.fish f
LEFT JOIN public.join_fish_transgene_alleles jfta
  ON jfta.fish_id = f.id
LEFT JOIN public.transgene_alleles ta
  ON ta.transgene_base_code = jfta.transgene_base_code
 AND ta.allele_number      = jfta.allele_number
LEFT JOIN public.v_fish_unified u
  ON u.fish_code = f.fish_code
LEFT JOIN public.v_fluorescent_marker_rollup r
  ON r.fish_code = f.fish_code;

COMMIT;
