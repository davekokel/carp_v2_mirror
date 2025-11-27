BEGIN;

-- Drop if they exist so the migration is idempotent
DROP VIEW IF EXISTS public.v_transgene_alleles_overview;
DROP VIEW IF EXISTS public.v_transgenes_overview;

-- Summary: one row per transgene with allele count
CREATE VIEW public.v_transgenes_overview AS
SELECT
  t.transgene_base_code,
  t.transgene_name,
  COUNT(a.*) AS n_alleles
FROM public.transgenes t
LEFT JOIN public.transgene_alleles a
  ON a.transgene_base_code = t.transgene_base_code
GROUP BY
  t.transgene_base_code,
  t.transgene_name
ORDER BY
  t.transgene_base_code;

-- Detail: alleles per transgene
CREATE VIEW public.v_transgene_alleles_overview AS
SELECT
  a.transgene_base_code,
  t.transgene_name,
  a.allele_number,
  a.allele_name,
  a.allele_nickname,
  a.notes,
  a.created_at
FROM public.transgene_alleles a
LEFT JOIN public.transgenes t
  ON t.transgene_base_code = a.transgene_base_code
ORDER BY
  a.transgene_base_code,
  a.allele_number;

COMMIT;
