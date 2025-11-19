BEGIN;

----------------------------------------------------------------------
-- v8: Make genotype_fusions canonical and derive clutch_marker_fusions as a VIEW
--
-- Canonical:
--   genotype_fusions(genotype_code, fusion_id, source, source_detail)
--   treatment_fusions(treatment_id, fusion_id, source, source_detail) -- VIEW
--
-- clutch_marker_fusions VIEW:
--   For each clutch, union:
--     - fusions implied by its genotype (expected/observed)
--     - fusions delivered by treatments applied to that clutch
--
-- Output columns:
--   clutch_id    uuid
--   fusion_id    uuid
--   source       text          -- 'genotype' or tf.source ('plasmid','rna',...)
--   source_detail text
----------------------------------------------------------------------

-- 1. Drop legacy table if it exists
DROP TABLE IF EXISTS public.clutch_marker_fusions CASCADE;

-- 2. Drop any existing view with that name
DROP VIEW IF EXISTS public.clutch_marker_fusions CASCADE;

-- 3. Recreate as a VIEW
CREATE VIEW public.clutch_marker_fusions AS
  -- Genotype-derived fusions
  SELECT
    cl.id                    AS clutch_id,
    gf.fusion_id,
    'genotype'               AS source,
    gf.source_detail         AS source_detail
  FROM public.clutches cl
  LEFT JOIN public.crosses cr
    ON cr.id = cl.cross_id
  -- Choose observed genotype if present, otherwise expected genotype from cross
  LEFT JOIN public.genotypes gx
    ON gx.genotype_code = COALESCE(cl.observed_genotype_code,
                                   cr.expected_genotype_code)
  JOIN public.genotype_fusions gf
    ON gf.genotype_code = gx.genotype_code

  UNION ALL

  -- Treatment-derived fusions
  SELECT
    cl.id                    AS clutch_id,
    tf.fusion_id,
    tf.source                AS source,          -- 'plasmid', 'rna', ...
    tf.source_detail         AS source_detail
  FROM public.clutches cl
  JOIN public.join_clutch_treatments jct
    ON jct.clutch_id = cl.id
  JOIN public.treatment_fusions tf
    ON tf.treatment_id = jct.treatment_id;

COMMIT;
