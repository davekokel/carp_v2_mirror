BEGIN;

-- For clutches that already have clutch_genotypes_v11 rows,
-- choose a primary genotype and hook clutches.genotype_v11_id to it.

WITH ranked AS (
  SELECT
    cg.clutch_id,
    cg.genotype_v11_id,
    cg.expected_fraction,
    cg.created_at,
    row_number() OVER (
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
