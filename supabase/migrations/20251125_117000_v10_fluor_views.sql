BEGIN;

-- v10 line-level fluors via constructs+fusions
CREATE OR REPLACE VIEW public.v10_line_fluors AS
SELECT
  fl.id                  AS line_id,
  fl.line_code,
  fl.nickname,
  fl.genetic_background,
  fl.line_building_stage,
  string_agg(DISTINCT flr.fluor_code, ', ' ORDER BY flr.fluor_code) AS fluor_codes,
  string_agg(DISTINCT flr.fluor_name, ', ' ORDER BY flr.fluor_name) AS fluor_names,
  string_agg(DISTINCT tg2.tag_code,   ', ' ORDER BY tg2.tag_code)   AS tag_codes
FROM public.fish_lines fl
LEFT JOIN public.join_line_alleles jla
  ON jla.line_id = fl.id
LEFT JOIN public.transgene_alleles ta
  ON ta.allele_number = jla.allele_number
LEFT JOIN public.transgenes tg
  ON tg.transgene_base_code = ta.transgene_base_code
LEFT JOIN public.constructs c
  ON c.construct_code = tg.transgene_base_code
LEFT JOIN public.construct_fusions cf
  ON cf.construct_id = c.id
LEFT JOIN public.fusions f
  ON f.id = cf.fusion_id
LEFT JOIN public.fluors flr
  ON flr.id = f.fluor_id
LEFT JOIN public.tags tg2
  ON tg2.id = f.tag_id
GROUP BY fl.id;

-- v10 treatment-mix-level fluors via constructs+fusions
CREATE OR REPLACE VIEW public.v10_treatment_mix_fluors AS
SELECT
  tm.id          AS mix_id,
  t.id           AS treatment_id,
  t.treat_code,
  t.kind_code,
  tm.mix_code,
  string_agg(DISTINCT flr.fluor_code, ', ' ORDER BY flr.fluor_code) AS fluor_codes,
  string_agg(DISTINCT flr.fluor_name, ', ' ORDER BY flr.fluor_name) AS fluor_names,
  string_agg(DISTINCT tg2.tag_code,   ', ' ORDER BY tg2.tag_code)   AS tag_codes
FROM public.treatment_mixes tm
JOIN public.treatments t
  ON t.id = tm.treatment_id
LEFT JOIN public.treatment_mix_constructs tmc
  ON tmc.mix_id = tm.id
LEFT JOIN public.constructs c
  ON c.id = tmc.construct_id
LEFT JOIN public.construct_fusions cf
  ON cf.construct_id = c.id
LEFT JOIN public.fusions f
  ON f.id = cf.fusion_id
LEFT JOIN public.fluors flr
  ON flr.id = f.fluor_id
LEFT JOIN public.tags tg2
  ON tg2.id = f.tag_id
GROUP BY
  tm.id,
  t.id,
  t.treat_code,
  t.kind_code,
  tm.mix_code;

COMMIT;
