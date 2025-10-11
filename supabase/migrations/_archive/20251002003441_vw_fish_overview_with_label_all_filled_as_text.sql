CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
SELECT
  v.*,

  -- batch label via mapping
  COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,

  -- created_by enrichment
  COALESCE(NULLIF(TRIM(v.created_by),''), NULLIF(TRIM(f.created_by),'')) AS created_by_enriched,

  /* Filled base code (TEXT): prefer v.*, else sidecar, else first linked allele */
  COALESCE(
    NULLIF(TRIM(v.transgene_base_code), ''),
    NULLIF(TRIM(slul.transgene_base_code), ''),
    (
      SELECT fta2.transgene_base_code
      FROM public.fish_transgene_alleles fta2
      WHERE fta2.fish_id = f.id_uuid
      ORDER BY fta2.allele_number NULLS LAST
      LIMIT 1
    )
  )::text AS transgene_base_code_filled,

  /* Filled allele number (TEXT): cast every arg to text first */
  COALESCE(
    NULLIF(TRIM(v.allele_number::text), ''),
    NULLIF(TRIM(slul.allele_number::text), ''),
    NULLIF((
      SELECT fta2.allele_number::text
      FROM public.fish_transgene_alleles fta2
      WHERE fta2.fish_id = f.id_uuid
      ORDER BY fta2.allele_number NULLS LAST
      LIMIT 1
    ), '')
  )::text AS allele_number_filled,

  /* Filled name (TEXT): prefer v.*, else sidecar base→name, else link-table base→name */
  COALESCE(
    NULLIF(TRIM(v.transgene_name), ''),
    (
      SELECT COALESCE(tg.transgene_name, tg.name, slul.transgene_base_code)
      FROM (SELECT 1) _
      LEFT JOIN public.transgenes tg
        ON tg.transgene_base_code = slul.transgene_base_code
    ),
    (
      SELECT COALESCE(tg.transgene_name, tg.name, fta2.transgene_base_code)
      FROM public.fish_transgene_alleles fta2
      LEFT JOIN public.transgenes tg
        ON tg.transgene_base_code = fta2.transgene_base_code
      WHERE fta2.fish_id = f.id_uuid
      ORDER BY fta2.allele_number NULLS LAST
      LIMIT 1
    )
  )::text AS transgene_name_filled

FROM public.vw_fish_overview v
LEFT JOIN public.fish f
  ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))
LEFT JOIN public.fish_seed_batches fsb
  ON fsb.fish_id = f.id_uuid
LEFT JOIN public.seed_batches sb
  ON sb.seed_batch_id = fsb.seed_batch_id
LEFT JOIN public.seed_last_upload_links slul
  ON UPPER(TRIM(slul.fish_code)) = UPPER(TRIM(v.fish_code));
