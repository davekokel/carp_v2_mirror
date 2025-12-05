BEGIN;

DROP VIEW IF EXISTS public.v11_treated_clutch_genotype_star;

CREATE VIEW public.v11_treated_clutch_genotype_star AS
SELECT
  tcg.id::text                 AS treated_clutch_genotype_id,
  tcg.treated_clutch_id::text  AS treated_clutch_id,
  cg.clutch_id::text           AS clutch_id,
  tcg.clutch_genotype_id::text AS clutch_genotype_id,
  tcg.is_primary               AS is_primary,
  cg.expected_fraction         AS expected_fraction,
  cg.expected_percent_label    AS expected_percent_label,
  cg.notes                     AS notes,
  gv.id::text                  AS genotype_v11_id,
  gv.genotype_code             AS genotype_code,
  gv.genotype_pretty           AS genotype_pretty,
  gv.genotype_basecodes        AS genotype_basecodes
FROM public.treated_clutch_genotypes_v11 tcg
JOIN public.clutch_genotypes_v11 cg
  ON cg.id = tcg.clutch_genotype_id
JOIN public.genotypes_v11 gv
  ON gv.id = cg.genotype_v11_id;

COMMENT ON VIEW public.v11_treated_clutch_genotype_star IS
'Minimal treated-clutch × genotype rollup. One row per (treated_clutch_id, clutch_genotype_id) defined in treated_clutch_genotypes_v11. If a treated_clutch_id has no rows here, treat that as “all clutch_genotypes_v11 for its clutch are in play” by convention in the UI.';
COMMIT;
