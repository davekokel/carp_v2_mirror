BEGIN;

DROP VIEW IF EXISTS public.v11_treatment_star;

CREATE VIEW public.v11_treatment_star AS
WITH mix_constructs AS (
  SELECT
    tm.treatment_id,
    tmc.construct_id
  FROM public.treatment_mixes tm
  JOIN public.treatment_mix_constructs tmc
    ON tmc.mix_id = tm.id
),
base_codes AS (
  SELECT
    mc.treatment_id,
    string_agg(
      DISTINCT c.construct_code,
      '; ' ORDER BY c.construct_code
    ) AS genotype_basecode_code
  FROM mix_constructs mc
  JOIN public.constructs c
    ON c.id = mc.construct_id
  GROUP BY mc.treatment_id
),
fusion_bits AS (
  SELECT
    mc.treatment_id,
    fl.fluor_code,
    tg.tag_code,
    tg.localization,
    f.tag_pos
  FROM mix_constructs mc
  JOIN public.construct_fusions cf
    ON cf.construct_id = mc.construct_id
  JOIN public.fusions f
    ON f.id = cf.fusion_id
  JOIN public.fluors fl
    ON fl.id = f.fluor_id
  JOIN public.tags tg
    ON tg.id = f.tag_id
),
fluor_tag_rollup AS (
  SELECT
    treatment_id,
    string_agg(
      DISTINCT format('%s::%s(%s)', fluor_code, tag_code, tag_pos),
      '; ' ORDER BY fluor_code, tag_code, tag_pos
    ) AS all_fluor_tag_rollup
  FROM fusion_bits
  GROUP BY treatment_id
),
organelle_fluor_rollup AS (
  SELECT
    treatment_id,
    string_agg(
      DISTINCT format('%s-%s', localization, fluor_code),
      '; ' ORDER BY localization, fluor_code
    ) AS all_organelle_fluor_rollup
  FROM (
    SELECT
      treatment_id,
      NULLIF(trim(localization), '') AS localization,
      fluor_code
    FROM fusion_bits
  ) s
  WHERE localization IS NOT NULL
  GROUP BY treatment_id
)
SELECT
  t.id::text                             AS treatment_id,
  t.treat_code                           AS treatment_code,
  COALESCE(bc.genotype_basecode_code,'') AS genotype_basecode_code,
  NULL::text                             AS genotype_transgene_allele_code,
  COALESCE(ft.all_fluor_tag_rollup,'')       AS all_fluor_tag_rollup,
  COALESCE(ofr.all_organelle_fluor_rollup,'') AS all_organelle_fluor_rollup,
  t.kind_code,
  t.treat_text,
  t.created_at
FROM public.treatments t
LEFT JOIN base_codes           bc  ON bc.treatment_id  = t.id
LEFT JOIN fluor_tag_rollup     ft  ON ft.treatment_id  = t.id
LEFT JOIN organelle_fluor_rollup ofr ON ofr.treatment_id = t.id;

COMMIT;
