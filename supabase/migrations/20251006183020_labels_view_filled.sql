BEGIN;
DROP VIEW IF EXISTS public.vw_fish_overview_with_label;
CREATE VIEW public.vw_fish_overview_with_label AS
SELECT
  v.*,
  fa.transgene_base_code_filled,
  fa.allele_code_filled,
  fa.allele_name_filled
FROM public.v_fish_overview v
LEFT JOIN LATERAL (
  SELECT
    l.transgene_base_code                            AS transgene_base_code_filled,
    l.allele_number::text                            AS allele_code_filled,
    ta.allele_nickname                               AS allele_name_filled
  FROM public.fish_transgene_alleles l
  JOIN public.fish f2 ON f2.id_uuid = l.fish_id
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = l.transgene_base_code
   AND ta.allele_number       = l.allele_number
  WHERE f2.fish_code = v.fish_code
  ORDER BY l.transgene_base_code, l.allele_number
  LIMIT 1
) fa ON TRUE;
COMMIT;
