BEGIN;

UPDATE public.transgene_alleles
SET allele_nickname = NULL
WHERE allele_nickname ILIKE 'nan';

COMMENT ON TABLE public.transgene_alleles IS
  'transgene alleles (allele_number, allele_name guN, optional allele_nickname); allele_nickname ''nan'' is normalized to NULL.';

COMMIT;
