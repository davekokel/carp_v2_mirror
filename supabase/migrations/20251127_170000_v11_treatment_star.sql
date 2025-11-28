BEGIN;

CREATE OR REPLACE VIEW public.v11_treatment_star AS
WITH mix_base AS (
  SELECT
    tm.treatment_id,
    string_agg(
      DISTINCT c.construct_code,
      '; ' ORDER BY c.construct_code
    ) AS all_base_codes
  FROM public.treatment_mixes tm
  LEFT JOIN public.treatment_mix_constructs tmc
         ON tmc.mix_id = tm.id
  LEFT JOIN public.constructs c
         ON c.id = tmc.construct_id
  GROUP BY tm.treatment_id
),
fluor_base AS (
  -- assumes v10_treatment_mix_fluors already encodes fluor/tag
  -- the way you like; we just alias it into the star view
  SELECT
    treatment_id,
    fluor_codes AS all_fluor_tag_rollup,
    tag_codes   AS all_organelle_fluor_rollup
  FROM public.v10_treatment_mix_fluors
)
SELECT
  t.id::text                         AS treatment_id,
  t.treat_code                       AS treatment_code,

  -- standard genotype-ish fields for treatments
  COALESCE(mb.all_base_codes, '')    AS genotype_basecode_code,
  NULL::text                         AS genotype_transgene_allele_code,

  -- standard display rollups
  CASE
    WHEN COALESCE(mb.all_base_codes, '') = ''
      THEN t.treat_code
    ELSE t.treat_code || ' > ' || mb.all_base_codes
  END                                AS treatments_and_transgenes,
  COALESCE(fb.all_fluor_tag_rollup, '')       AS all_fluor_tag_rollup,
  COALESCE(fb.all_organelle_fluor_rollup, '') AS all_organelle_fluor_rollup,

  -- extra metadata that is often handy in UIs
  t.kind_code,
  t.treat_text,
  t.created_at
FROM public.treatments t
LEFT JOIN mix_base   mb ON mb.treatment_id = t.id
LEFT JOIN fluor_base fb ON fb.treatment_id = t.id;

COMMIT;
