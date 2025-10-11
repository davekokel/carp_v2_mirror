-- Rebuild the view cleanly to avoid column-rename mapping
DROP VIEW IF EXISTS public.vw_fish_overview_with_label;

WITH
-- First linked allele per fish (by allele_number asc, NULLS LAST)
linkx AS (
  SELECT
    f.id_uuid AS fish_id,
    fta.transgene_base_code AS l_base,
    fta.allele_number       AS l_num,
    ta.allele_code          AS l_code,
    ta.allele_name          AS l_name
  FROM public.fish f
  LEFT JOIN LATERAL (
    SELECT *
    FROM public.fish_transgene_alleles fta2
    WHERE fta2.fish_id = f.id_uuid
    ORDER BY fta2.allele_number NULLS LAST
    LIMIT 1
  ) fta ON TRUE
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = fta.transgene_base_code
   AND ta.allele_number       = fta.allele_number
),
-- Sidecar per fish (match by fish_code OR name to the same fish_id)
sidecar AS (
  SELECT
    f.id_uuid               AS fish_id,
    slul.transgene_base_code AS s_base,
    slul.allele_number       AS s_num,
    slul.allele_code         AS s_code
  FROM public.fish f
  LEFT JOIN public.seed_last_upload_links slul
    ON  UPPER(TRIM(slul.fish_code)) = UPPER(TRIM(f.fish_code))
     OR UPPER(TRIM(slul.fish_code)) = UPPER(TRIM(f.name))
)
CREATE VIEW public.vw_fish_overview_with_label AS
SELECT
  v.*,

  -- batch label via mapping
  COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,

  -- created_by enrichment
  COALESCE(NULLIF(TRIM(v.created_by),''), NULLIF(TRIM(f.created_by),'')) AS created_by_enriched,

  -- base code (TEXT): prefer v.*, then sidecar, then link-table
  COALESCE(
    NULLIF(TRIM(v.transgene_base_code), ''),
    s.s_base,
    l.l_base
  )::text AS transgene_base_code_filled,

  -- allele number (TEXT): prefer v.*, then sidecar, then link-table
  COALESCE(
    NULLIF(TRIM(v.allele_number::text), ''),
    (s.s_num)::text,
    (l.l_num)::text
  )::text AS allele_number_filled,

  -- human name (TEXT): prefer v.*, then transgenes name for chosen base, else base
  COALESCE(
    NULLIF(TRIM(v.transgene_name), ''),
    (
      SELECT COALESCE(tg.transgene_name, tg.name, COALESCE(s.s_base, l.l_base, NULLIF(TRIM(v.transgene_base_code), '')))
      FROM public.transgenes tg
      WHERE tg.transgene_base_code = COALESCE(s.s_base, l.l_base, NULLIF(TRIM(v.transgene_base_code), ''))
      LIMIT 1
    ),
    COALESCE(s.s_base, l.l_base, NULLIF(TRIM(v.transgene_base_code), ''))
  )::text AS transgene_name_filled,

  -- pretty: Tg(<lower(base with digits padded to 4)>)<code|name|number>
  (
    CASE
      WHEN COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), s.s_base, l.l_base) IS NOT NULL
       AND COALESCE(NULLIF(TRIM(v.allele_number::text), ''), (s.s_num)::text, (l.l_num)::text) IS NOT NULL
      THEN
        'Tg(' ||
        (
          -- letters + zero-padded trailing digits to 4 places
          regexp_replace(lower(COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), s.s_base, l.l_base)), '[0-9]+$', '')
          ||
          lpad(regexp_replace(lower(COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), s.s_base, l.l_base)), '^[A-Za-z]+', ''), 4, '0')
        ) || ')' ||
        COALESCE(
          NULLIF(TRIM(s.s_code), ''),
          NULLIF(TRIM(l.l_code), ''),
          NULLIF(TRIM(l.l_name), ''),
          NULLIF(TRIM(v.allele_number::text), ''),
          (s.s_num)::text,
          (l.l_num)::text
        )
      ELSE NULL
    END
  )::text AS transgene_pretty_filled,

  -- NEW (appended at end to avoid rename issues): allele_code_filled
  COALESCE(
    NULLIF(TRIM(s.s_code), ''),
    NULLIF(TRIM(l.l_code), ''),
    NULLIF(TRIM(l.l_name), ''),
    NULLIF(TRIM(v.allele_number::text), ''),
    (s.s_num)::text,
    (l.l_num)::text
  )::text AS allele_code_filled

FROM public.vw_fish_overview v
LEFT JOIN public.fish f
  ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))
LEFT JOIN public.fish_seed_batches fsb ON fsb.fish_id = f.id_uuid
LEFT JOIN public.seed_batches sb       ON sb.seed_batch_id = fsb.seed_batch_id
LEFT JOIN sidecar s                    ON s.fish_id = f.id_uuid
LEFT JOIN linkx   l                    ON l.fish_id = f.id_uuid;
