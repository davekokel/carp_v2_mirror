CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
WITH tg AS (
  SELECT
    f.id_uuid AS fish_id,
    TRIM(f.fish_code) AS fish_code_norm,
    ARRAY_REMOVE(ARRAY_AGG(fta.transgene_base_code ORDER BY fta.allele_number NULLS LAST), NULL) AS bases,
    ARRAY_REMOVE(ARRAY_AGG(fta.allele_number ORDER BY fta.allele_number NULLS LAST), NULL) AS allele_nums,
    ARRAY_REMOVE(
      ARRAY_AGG(COALESCE(tg.transgene_name, tg.transgene_base_code) ORDER BY fta.allele_number NULLS LAST),
      NULL
    ) AS names
  FROM public.fish f
  LEFT JOIN public.fish_transgene_alleles fta ON fta.fish_id = f.id_uuid
  LEFT JOIN public.transgenes tg ON tg.transgene_base_code = fta.transgene_base_code
  GROUP BY f.id_uuid, f.fish_code
),
tg_first AS (
  SELECT
    fish_id,
    fish_code_norm,
    CASE WHEN array_length(bases,1) > 0 THEN bases[1] END AS tg_base_first,
    CASE WHEN array_length(allele_nums,1) > 0 THEN allele_nums[1] END AS allele_num_first,
    CASE WHEN array_length(names,1) > 0 THEN names[1] END AS tg_name_first
  FROM tg
)
SELECT
  v.*,
  COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,
  COALESCE(NULLIF(TRIM(v.created_by),''), NULLIF(TRIM(f.created_by),'')) AS created_by_enriched,
  COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), tgf.tg_base_first) AS transgene_base_code,
  COALESCE(v.allele_number, tgf.allele_num_first) AS allele_number,
  COALESCE(NULLIF(TRIM(v.transgene_name), ''), tgf.tg_name_first) AS transgene_name
FROM public.vw_fish_overview v
LEFT JOIN public.fish f ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))
LEFT JOIN public.fish_seed_batches fsb ON fsb.fish_id = f.id_uuid
LEFT JOIN public.seed_batches sb ON sb.seed_batch_id = fsb.seed_batch_id
LEFT JOIN tg_first tgf ON tgf.fish_id = f.id_uuid;
