-- 1) Sidecar table keyed by fish_code (no FKs; simple and orthogonal)
CREATE TABLE IF NOT EXISTS public.seed_last_upload_links (
  fish_code            text PRIMARY KEY,
  transgene_base_code  text,
  allele_number        integer,
  zygosity             text,
  uploaded_at          timestamptz DEFAULT now()
);

-- 2) Recreate labeled overview to prefer sidecar when present,
--    then fall back to link table; keep your existing enrichments.
CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
SELECT
  v.*,

  -- batch label via fish_seed_batches
  COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,

  -- created_by enrichment
  COALESCE(NULLIF(TRIM(v.created_by),''), NULLIF(TRIM(f.created_by),'')) AS created_by_enriched,

  -- filled transgene columns: prefer sidecar by fish_code,
  -- else link-table (first allele), else whatever v.* had
  COALESCE(
    NULLIF(TRIM(v.transgene_base_code),''),
    slul.transgene_base_code,
    (
      SELECT fta.transgene_base_code
      FROM public.fish_transgene_alleles fta
      WHERE fta.fish_id = f.id_uuid
      ORDER BY fta.allele_number NULLS LAST
      LIMIT 1
    )
  ) AS transgene_base_code_filled,

  COALESCE(
    v.allele_number,
    slul.allele_number,
    (
      SELECT fta.allele_number
      FROM public.fish_transgene_alleles fta
      WHERE fta.fish_id = f.id_uuid
      ORDER BY fta.allele_number NULLS LAST
      LIMIT 1
    )
  ) AS allele_number_filled,

  COALESCE(
    NULLIF(TRIM(v.transgene_name),''),
    (
      SELECT COALESCE(tg.transgene_name, slul.transgene_base_code)
      FROM (SELECT 1) _
      LEFT JOIN public.transgenes tg
        ON tg.transgene_base_code = slul.transgene_base_code
    ),
    (
      SELECT COALESCE(tg.transgene_name, fta.transgene_base_code)
      FROM public.fish_transgene_alleles fta
      LEFT JOIN public.transgenes tg
        ON tg.transgene_base_code = fta.transgene_base_code
      WHERE fta.fish_id = f.id_uuid
      ORDER BY fta.allele_number NULLS LAST
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

LEFT JOIN public.seed_last_upload_links slul
  ON UPPER(TRIM(slul.fish_code)) = UPPER(TRIM(v.fish_code));
