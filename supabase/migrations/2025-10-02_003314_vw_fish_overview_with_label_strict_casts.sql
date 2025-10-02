-- Robust casts so COALESCE types match across view, sidecar, and link tables
CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
SELECT
  v.*,

  -- batch label via mapping
  COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,

  -- created_by enrichment
  COALESCE(NULLIF(TRIM(v.created_by),''), NULLIF(TRIM(f.created_by),'')) AS created_by_enriched,

  /* =========================
     Filled transgene base code (TEXT)
     ========================= */
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

  /* =========================
     Filled allele number (INTEGER)
     - v.allele_number may be text in your view → cast to text, null-if-empty, then ::int
     - slul.allele_number may be text or int → cast to text, null-if-empty, then ::int
     - link-table value is already int
     ========================= */
  COALESCE(
    NULLIF(v.allele_number::text, '')::int,
    NULLIF(slul.allele_number::text, '')::int,
    (
      SELECT fta2.allele_number
      FROM public.fish_transgene_alleles fta2
      WHERE fta2.fish_id = f.id_uuid
      ORDER BY fta2.allele_number NULLS LAST
      LIMIT 1
    )
  ) AS allele_number_filled,

  /* =========================
     Filled transgene name (TEXT)
     - prefer v.transgene_name (text or castable to text)
     - else slul.transgene_name (if you add one later)
     - else resolve from transgenes.name/transgene_name, finally fall back to base code
     ========================= */
  COALESCE(
    NULLIF(TRIM(v.transgene_name), ''),
    NULLIF(TRIM(slul.transgene_name), ''),
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
