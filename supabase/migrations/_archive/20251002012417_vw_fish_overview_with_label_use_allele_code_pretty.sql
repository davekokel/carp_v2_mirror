CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
SELECT
  v.*,

  -- batch & created_by enrichments (unchanged)
  COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,
  COALESCE(NULLIF(TRIM(v.created_by),''), NULLIF(TRIM(f.created_by),'')) AS created_by_enriched,

  -- Sidecar match (code OR name → same fish)
  sx.slul_base AS transgene_base_code_from_sidecar,
  sx.slul_num  AS allele_number_from_sidecar,
  sx.slul_code AS allele_code_from_sidecar,

  -- Filled base
  COALESCE(
    NULLIF(TRIM(v.transgene_base_code), ''),
    sx.slul_base,
    (SELECT fta2.transgene_base_code FROM public.fish_transgene_alleles fta2
      WHERE fta2.fish_id = f.id_uuid
      ORDER BY fta2.allele_number NULLS LAST LIMIT 1)
  )::text AS transgene_base_code_filled,

  -- Filled allele_code (prefer sidecar → link-table → v.legacy/number)
  COALESCE(
    NULLIF(TRIM(sx.slul_code), ''),
    (SELECT ta.allele_code FROM public.fish_transgene_alleles fta2
       JOIN public.transgene_alleles ta
         ON ta.transgene_base_code = fta2.transgene_base_code
        AND ta.allele_number       = fta2.allele_number
      WHERE fta2.fish_id = f.id_uuid
      ORDER BY fta2.allele_number NULLS LAST LIMIT 1),
    NULLIF(TRIM(v.allele_number::text), ''),
    NULLIF(TRIM(v.transgene_name), '')
  )::text AS allele_code_filled,

  -- Filled allele_number (kept for reference)
  COALESCE(
    NULLIF(TRIM(v.allele_number::text), ''),
    sx.slul_num::text,
    (SELECT fta2.allele_number::text FROM public.fish_transgene_alleles fta2
      WHERE fta2.fish_id = f.id_uuid
      ORDER BY fta2.allele_number NULLS LAST LIMIT 1)
  )::text AS allele_number_filled,

  -- Human name (kept, fallback chain)
  COALESCE(
    NULLIF(TRIM(v.transgene_name), ''),
    (SELECT tg.transgene_name FROM public.transgenes tg
      WHERE tg.transgene_base_code = sx.slul_base LIMIT 1),
    NULLIF(TRIM(v.transgene_base_code), '')
  )::text AS transgene_name_filled,

  -- Pretty: Tg(<lower(base with padded digits)>)<allele_code>
  CASE
    WHEN
      COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), sx.slul_base) IS NOT NULL
      AND COALESCE(NULLIF(TRIM(sx.slul_code), ''), NULLIF(TRIM(v.allele_number::text), ''), NULLIF(TRIM(v.transgene_name), '')) IS NOT NULL
    THEN
      'Tg(' ||
      lower(
        COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), sx.slul_base)
      ) ||
      ')' ||
      COALESCE(NULLIF(TRIM(sx.slul_code), ''), NULLIF(TRIM(v.allele_number::text), ''), NULLIF(TRIM(v.transgene_name), ''))
    ELSE
      NULL
  END::text AS transgene_pretty_filled

FROM public.vw_fish_overview v
LEFT JOIN public.fish f
  ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))

LEFT JOIN public.fish_seed_batches fsb
  ON fsb.fish_id = f.id_uuid
LEFT JOIN public.seed_batches sb
  ON sb.seed_batch_id = fsb.seed_batch_id

-- Sidecar (match same fish via code OR name)
LEFT JOIN LATERAL (
  SELECT
    slul.transgene_base_code AS slul_base,
    slul.allele_number       AS slul_num,
    slul.allele_code         AS slul_code
  FROM public.seed_last_upload_links slul
  JOIN public.fish f2
    ON  UPPER(TRIM(f2.fish_code)) = UPPER(TRIM(slul.fish_code))
     OR UPPER(TRIM(f2.name))      = UPPER(TRIM(slul.fish_code))
  WHERE f2.id_uuid = f.id_uuid
  LIMIT 1
) sx ON TRUE;
