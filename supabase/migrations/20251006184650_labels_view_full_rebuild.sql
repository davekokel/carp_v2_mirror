BEGIN;
DROP VIEW IF EXISTS public.vw_fish_overview_with_label;
CREATE VIEW public.vw_fish_overview_with_label AS
SELECT
  v.*,
  CASE WHEN v.date_birth IS NOT NULL
       THEN ((CURRENT_DATE - v.date_birth) / 7)::int
       ELSE NULL::int
  END AS age_weeks,
  fa.transgene_base_code_filled,
  fa.allele_code_filled,
  fa.allele_name_filled,
  mb.seed_batch_id,
  mb.seed_batch_id AS batch_label,
  NULL::text AS plasmid_injections_text,
  NULL::text AS rna_injections_text,
  COALESCE(f.created_by, '') AS created_by_enriched
FROM public.v_fish_overview v
LEFT JOIN public.fish f ON f.fish_code = v.fish_code
LEFT JOIN LATERAL (
  SELECT
    l.transgene_base_code  AS transgene_base_code_filled,
    l.allele_number::text  AS allele_code_filled,
    ta.allele_nickname     AS allele_name_filled
  FROM public.fish_transgene_alleles l
  JOIN public.fish f2 ON f2.id_uuid = l.fish_id
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = l.transgene_base_code
   AND ta.allele_number       = l.allele_number
  WHERE f2.fish_code = v.fish_code
  ORDER BY l.transgene_base_code, l.allele_number
  LIMIT 1
) fa ON TRUE
LEFT JOIN LATERAL (
  SELECT m.seed_batch_id
  FROM public.fish_seed_batches_map m
  JOIN public.fish f3 ON f3.id_uuid = m.fish_id
  WHERE f3.fish_code = v.fish_code
  ORDER BY m.logged_at DESC NULLS LAST, m.created_at DESC NULLS LAST
  LIMIT 1
) mb ON TRUE;
COMMIT;
