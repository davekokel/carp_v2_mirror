BEGIN;
DROP VIEW IF EXISTS public.vw_fish_overview_with_label;
CREATE VIEW public.vw_fish_overview_with_label AS
WITH base AS (
  SELECT
    f.fish_code,
    f.name,
    f.nickname,
    f.line_building_stage,
    f.date_birth,
    f.genetic_background,
    f.created_at
  FROM public.fish f
),
allele AS (
  SELECT
    f2.fish_code,
    l.transgene_base_code,
    l.allele_number,
    ta.allele_nickname
  FROM public.fish_transgene_alleles l
  JOIN public.fish f2 ON f2.id_uuid = l.fish_id
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = l.transgene_base_code
   AND ta.allele_number       = l.allele_number
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY f2.fish_code
    ORDER BY l.transgene_base_code, l.allele_number
  ) = 1
),
batch AS (
  SELECT
    f3.fish_code,
    m.seed_batch_id
  FROM public.fish_seed_batches_map m
  JOIN public.fish f3 ON f3.id_uuid = m.fish_id
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY f3.fish_code
    ORDER BY m.logged_at DESC NULLS LAST, m.created_at DESC NULLS LAST
  ) = 1
)
SELECT
  b.*,
  /* “filled” fields for downstream use */
  a.transgene_base_code              AS transgene_base_code_filled,
  a.allele_number::text              AS allele_code_filled,
  a.allele_nickname                  AS allele_name_filled,
  batch.seed_batch_id,
  batch.seed_batch_id                AS batch_label,
  /* print-ready (coalesced) fields */
  COALESCE(b.nickname, '')           AS nickname_print,
  COALESCE(b.genetic_background, '') AS genetic_background_print,
  COALESCE(b.line_building_stage, '')AS line_building_stage_print,
  COALESCE(TO_CHAR(b.date_birth, 'YYYY-MM-DD'), '') AS date_birth_print,
  CASE
    WHEN a.transgene_base_code IS NULL THEN ''
    WHEN a.allele_number IS NOT NULL  THEN a.transgene_base_code || '-' || a.allele_number::text
    WHEN a.allele_nickname IS NOT NULL THEN a.transgene_base_code || ' ' || a.allele_nickname
    ELSE a.transgene_base_code
  END AS genotype_print,
  /* convenience */
  ((CURRENT_DATE - b.date_birth)/7)::int AS age_weeks
FROM base b
LEFT JOIN allele a USING (fish_code)
LEFT JOIN batch  USING (fish_code)
ORDER BY b.fish_code;
COMMIT;
