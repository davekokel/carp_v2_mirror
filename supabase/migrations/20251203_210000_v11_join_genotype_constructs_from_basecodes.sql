BEGIN;

-- Seed join_genotype_constructs_v11 using genotype_basecodes as base_code → constructs.base_code

WITH geno AS (
  SELECT
    g.id::uuid          AS genotype_id,
    trim(g.genotype_basecodes) AS base_code
  FROM public.genotypes_v11 g
  WHERE g.genotype_basecodes IS NOT NULL
    AND g.genotype_basecodes <> ''
    -- simple case: no commas, single base code
    AND position(',' IN g.genotype_basecodes) = 0
),
pairs AS (
  SELECT
    geno.genotype_id,
    c.id::uuid AS construct_id
  FROM geno
  JOIN public.constructs c
    ON c.base_code = geno.base_code
)

INSERT INTO public.join_genotype_constructs_v11 (genotype_id, construct_id, created_at)
SELECT
  p.genotype_id,
  p.construct_id,
  now()
FROM pairs p
LEFT JOIN public.join_genotype_constructs_v11 j
  ON j.genotype_id = p.genotype_id
 AND j.construct_id = p.construct_id
WHERE j.genotype_id IS NULL;

COMMIT;
