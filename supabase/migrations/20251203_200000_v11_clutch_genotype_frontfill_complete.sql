-- v11 clutch genotype frontfill (safe, idempotent)
-- Choose a primary genotype_v11_id per clutch based on expected_fraction + created_at,
-- and write it into clutches.genotype_v11_id only if it is currently NULL.

BEGIN;

WITH ranked AS (
  SELECT
    cg.clutch_id,
    cg.genotype_v11_id,
    cg.expected_fraction,
    cg.expected_percent_label,
    cg.created_at,
    ROW_NUMBER() OVER (
      PARTITION BY cg.clutch_id
      ORDER BY
        cg.expected_fraction DESC NULLS LAST,
        cg.created_at
    ) AS rn
  FROM public.clutch_genotypes_v11 cg
),

chosen AS (
  SELECT
    clutch_id,
    genotype_v11_id
  FROM ranked
  WHERE rn = 1
)

UPDATE public.clutches c
SET genotype_v11_id = ch.genotype_v11_id
FROM chosen ch
WHERE c.id = ch.clutch_id
  AND c.genotype_v11_id IS NULL;

COMMIT;
