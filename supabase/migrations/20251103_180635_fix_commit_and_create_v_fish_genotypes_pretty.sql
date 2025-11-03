BEGIN;

DROP VIEW IF EXISTS public.v_fish_genotypes_pretty;

DO $$
DECLARE
  fish_col text;
BEGIN
  SELECT CASE
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='fish_id') THEN 'fish_id'
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='fish_uuid') THEN 'fish_uuid'
           ELSE NULL
         END INTO fish_col;

  IF fish_col IS NULL THEN
    RAISE EXCEPTION 'join_fish_transgene_alleles missing fish_id/fish_uuid';
  END IF;

  EXECUTE format($f$
    CREATE VIEW public.v_fish_genotypes_pretty AS
    SELECT
      j.%I::text AS fish_id,
      string_agg(j.transgene_base_code||'['||j.allele_number::text||']', ', ' ORDER BY j.transgene_base_code, j.allele_number) AS genotype_pretty
    FROM public.join_fish_transgene_alleles j
    GROUP BY j.%I
  $f$, fish_col, fish_col);
END$$;

COMMIT;
