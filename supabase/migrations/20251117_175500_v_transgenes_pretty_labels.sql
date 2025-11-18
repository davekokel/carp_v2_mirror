BEGIN;

CREATE OR REPLACE VIEW public.v_transgene_alleles_overview AS
SELECT
  ta.transgene_base_code,
  CASE
    WHEN COALESCE(ta.allele_nickname, '') <> '' THEN
      format('Tg(%s)%s', ta.transgene_base_code, ta.allele_nickname)
    WHEN COALESCE(ta.allele_name, '') <> '' THEN
      format('Tg(%s)%s', ta.transgene_base_code, ta.allele_name)
    ELSE
      format('Tg(%s)', ta.transgene_base_code)
  END AS transgene_name,
  ta.allele_number,
  COALESCE(ta.allele_name, '')     AS allele_name,
  COALESCE(ta.allele_nickname, '') AS allele_nickname
FROM public.transgene_alleles ta;

CREATE OR REPLACE VIEW public.v_transgenes_overview AS
SELECT
  t.transgene_base_code,
  COALESCE(
    MIN(
      CASE
        WHEN COALESCE(ta.allele_nickname, '') <> '' THEN
          format('Tg(%s)%s', t.transgene_base_code, ta.allele_nickname)
        WHEN COALESCE(ta.allele_name, '') <> '' THEN
          format('Tg(%s)%s', t.transgene_base_code, ta.allele_name)
        ELSE
          format('Tg(%s)', t.transgene_base_code)
      END
    ),
    format('Tg(%s)', t.transgene_base_code)
  ) AS transgene_name,
  COUNT(ta.*) AS n_alleles
FROM public.transgenes t
LEFT JOIN public.transgene_alleles ta
  ON ta.transgene_base_code = t.transgene_base_code
GROUP BY t.transgene_base_code
ORDER BY t.transgene_base_code;

COMMIT;
