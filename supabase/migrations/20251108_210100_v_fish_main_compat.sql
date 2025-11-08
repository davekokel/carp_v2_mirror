BEGIN;
CREATE OR REPLACE VIEW public.v_fish_main AS
SELECT
  f.fish_code,
  jfta.transgene_base_code,
  COALESCE(NULLIF(ta.allele_name,''), NULL) AS allele_nickname,
  jfta.allele_number,
  ta.allele_name,
  COALESCE(NULLIF(ta.allele_name,''), jfta.transgene_base_code||'-'||LPAD(jfta.allele_number::text,2,'0')) AS transgene_pretty_nickname,
  jfta.transgene_base_code AS transgene_pretty_name
FROM public.join_fish_transgene_alleles jfta
JOIN public.fish f
  ON f.id = jfta.fish_id
LEFT JOIN public.transgene_alleles ta
  ON ta.transgene_base_code = jfta.transgene_base_code
 AND ta.allele_number      = jfta.allele_number;
COMMIT;
