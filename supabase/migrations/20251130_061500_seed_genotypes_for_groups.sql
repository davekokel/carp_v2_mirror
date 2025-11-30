BEGIN;

INSERT INTO public.genotypes_v11 (genotype_code, genotype_pretty, genotype_basecodes, created_at)
SELECT
  g.genotype_key       AS genotype_code,
  g.genotype_key       AS genotype_pretty,
  NULL                 AS genotype_basecodes,
  now()                AS created_at
FROM public.fish_groups g
LEFT JOIN public.genotypes_v11 gv
  ON gv.genotype_code = g.genotype_key
WHERE g.genotype_key IS NOT NULL
  AND gv.genotype_code IS NULL
GROUP BY g.genotype_key;

COMMIT;
