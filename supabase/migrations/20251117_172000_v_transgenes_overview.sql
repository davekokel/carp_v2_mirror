BEGIN;

ALTER TABLE public.transgenes
  ADD COLUMN IF NOT EXISTS transgene_name text;

CREATE OR REPLACE VIEW public.v_transgenes_overview AS
SELECT
  t.transgene_base_code,
  COALESCE(t.transgene_name, '') AS transgene_name,
  COUNT(ta.*)                    AS n_alleles
FROM public.transgenes t
LEFT JOIN public.transgene_alleles ta
  ON ta.transgene_base_code = t.transgene_base_code
GROUP BY t.transgene_base_code, t.transgene_name
ORDER BY t.transgene_base_code;

CREATE OR REPLACE VIEW public.v_transgene_alleles_overview AS
SELECT
  ta.transgene_base_code,
  COALESCE(t.transgene_name, '') AS transgene_name,
  ta.allele_number,
  COALESCE(ta.allele_name, '')     AS allele_name,
  COALESCE(ta.allele_nickname, '') AS allele_nickname
FROM public.transgene_alleles ta
LEFT JOIN public.transgenes t
  ON t.transgene_base_code = ta.transgene_base_code;

COMMIT;
