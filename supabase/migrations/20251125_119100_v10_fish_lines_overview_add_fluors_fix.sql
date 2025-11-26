BEGIN;

CREATE OR REPLACE VIEW public.v10_fish_lines_overview AS
SELECT
  fl.id                  AS line_id,
  fl.line_code,
  fl.nickname,
  fl.genetic_background,
  fl.line_building_stage,
  fl.created_at,
  string_agg(
    'Tg(' || tr.transgene_base_code || ')' || ta.allele_name,
    '; ' ORDER BY tr.transgene_base_code, ta.allele_number
  )                      AS genotype_pretty,
  vlf.fluor_codes,
  vlf.tag_codes
FROM public.fish_lines fl
LEFT JOIN public.join_line_alleles jla
       ON jla.line_id = fl.id
LEFT JOIN public.constructs c
       ON c.id = jla.construct_id
LEFT JOIN public.transgenes tr
       ON tr.transgene_base_code = c.construct_code
LEFT JOIN public.transgene_alleles ta
       ON ta.transgene_base_code = tr.transgene_base_code
      AND ta.allele_number       = jla.allele_number
LEFT JOIN public.v10_line_fluors vlf
       ON vlf.line_id = fl.id
GROUP BY
  fl.id,
  fl.line_code,
  fl.nickname,
  fl.genetic_background,
  fl.line_building_stage,
  fl.created_at,
  vlf.fluor_codes,
  vlf.tag_codes;

COMMIT;
