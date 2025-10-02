-- Recreate the view with explicit casts for slul.* so COALESCE types match

CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
SELECT
  v.*,

  -- batch label via mapping
  COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,

  -- created_by enrichment
  COALESCE(NULLIF(TRIM(v.created_by),''), NULLIF(TRIM(f.created_by),'')) AS created_by_enriched,

  -- Filled transgene columns: prefer v.*, else slul.*, else first linked allele

  -- base code (text everywhere)
  COALESCE(
    NULLIF(TRIM(v.transgene_base_code),''),
    NULLIF(TRIM(slul.transgene_base_code),''),
    (
      SELECT fta2.transgene_base_code
      FROM public.fish_transgene_alleles fta2
      WHERE fta2.fish_id = f.id_uuid
      ORDER BY fta2.allele_number NULLS LAST
      LIMIT 1
    )
  ) AS transgene_base_code_filled,

  -- allele number (ensure all args are integer)
  COALESCE(
    v.allele_number,
    NULLIF(TRIM(slul.allele_number),'')::int,
    (
      SELECT fta2.allele_number
      FROM public.fish_transgene_alleles fta2
      WHERE fta2.fish_id = f.id_uuid
      ORDER BY fta2.allele_number NULLS LAST
      LIMIT 1
    )
  ) AS allele_number_filled,

  -- transgene name (text everywhere; fall back to base code)
  COALESCE(
    NULLIF(TRIM(v.transgene_name),''),
    NULLIF(TRIM(slul.transgene_name),''),
    (
      SELECT COALESCE(tg.transgene_name, fta2.transgene_base_code)
      FROM public.fish_transgene_alleles fta2
      LEFT JOIN public.transgenes tg
             ON tg.transgene_base_code = fta2.transgene_base_code
      WHERE fta2.fish_id = f.id_uuid
      ORDER BY fta2.allele_number NULLS LAST
      LIMIT 1
    )
  ) AS transgene_name_filled

FROM public.vw_fish_overview v
LEFT JOIN public.fish f
  ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))

LEFT JOIN public.fish_seed_batches fsb
  ON fsb.fish_id = f.id_uuid
LEFT JOIN public.seed_batches sb
  ON sb.seed_batch_id = fsb.seed_batch_id

-- your “seed_last_upload_links” overlay (slul) — use text columns; we cast in COALESCE
LEFT JOIN public.seed_last_upload_links slul
  ON UPPER(TRIM(slul.fish_code)) = UPPER(TRIM(v.fish_code));
