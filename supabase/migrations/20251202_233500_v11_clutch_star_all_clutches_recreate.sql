BEGIN;

CREATE OR REPLACE VIEW public.v11_clutch_star AS
WITH tbase AS (
  SELECT
    c.id                        AS clutch_id,
    c.clutch_code,
    c.clutch_date,
    c.estimated_egg_count,
    c.genotype_v11_id,
    (
      SELECT count(*)
      FROM public.imaging_clutch_memberships m
      WHERE m.clutch_id = c.id
    )                           AS n_imaging_slots,
    (
      SELECT count(*)
      FROM public.imaging_clutch_memberships m
      WHERE m.clutch_id = c.id
    )                           AS n_rois
  FROM public.clutches c
),
treats AS (
  SELECT
    c.id AS clutch_id,
    string_agg(
      DISTINCT t.treat_code,
      '||' ORDER BY t.treat_code
    ) AS treat_codes,
    string_agg(
      DISTINCT cb.base_code,
      '||' ORDER BY cb.base_code
    ) AS treat_basecodes
  FROM public.clutches c
  LEFT JOIN public.join_clutch_treatments jct
    ON jct.clutch_id = c.id
  LEFT JOIN public.treatments t
    ON t.id = jct.treatment_id
  LEFT JOIN public.treatment_mixes tm
    ON tm.treatment_id = t.id
  LEFT JOIN public.treatment_mix_constructs tmc
    ON tmc.mix_id = tm.id
  LEFT JOIN public.constructs cb
    ON cb.id = tmc.construct_id
  GROUP BY c.id
),
expected AS (
  SELECT
    cg.clutch_id,
    string_agg(
      DISTINCT g.genotype_code,
      '||' ORDER BY g.genotype_code
    ) AS expected_genotype_codes,
    string_agg(
      DISTINCT g.genotype_basecodes,
      '||' ORDER BY g.genotype_basecodes
    ) AS expected_genotype_basecodes,
    string_agg(
      DISTINCT g.genotype_pretty,
      '||' ORDER BY g.genotype_pretty
    ) AS expected_genotype_pretty
  FROM public.clutch_genotypes_v11 cg
  JOIN public.genotypes_v11 g
    ON g.id = cg.genotype_v11_id
  GROUP BY cg.clutch_id
)
SELECT
  b.clutch_id,
  b.clutch_code,
  b.clutch_date,
  b.estimated_egg_count,
  b.n_imaging_slots,
  b.n_rois,
  g_main.genotype_code       AS genotype_v11_code,
  g_main.genotype_basecodes  AS genotype_v11_basecodes,
  g_main.genotype_pretty,
  t.treat_codes,
  t.treat_basecodes,
  e.expected_genotype_codes,
  e.expected_genotype_basecodes,
  e.expected_genotype_pretty
FROM tbase b
LEFT JOIN public.genotypes_v11 g_main
  ON g_main.id = b.genotype_v11_id
LEFT JOIN treats t
  ON t.clutch_id = b.clutch_id
LEFT JOIN expected e
  ON e.clutch_id = b.clutch_id
ORDER BY b.clutch_code;

COMMENT ON VIEW public.v11_clutch_star IS
'Clutch-level rollup for ALL clutches: one row per clutch_id with imaging slot / ROI counts, genotype_v11 rollup, treatment codes, and expected genotype rollups. Legacy imaging + new cross/clutch paths are unified here.';

COMMIT;
