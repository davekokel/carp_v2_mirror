CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
WITH first_link AS (
  -- first allele per fish by allele_number asc (NULLS LAST)
  SELECT
    f.id_uuid               AS fish_id,
    fta.transgene_base_code AS base,
    fta.allele_number       AS num,
    ta.allele_code          AS acode,
    ta.allele_name          AS aname
  FROM public.fish f
  LEFT JOIN LATERAL (
    SELECT *
    FROM public.fish_transgene_alleles x
    WHERE x.fish_id = f.id_uuid
    ORDER BY x.allele_number NULLS LAST
    LIMIT 1
  ) fta ON TRUE
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = fta.transgene_base_code
   AND ta.allele_number       = fta.allele_number
)
SELECT
  v.*,

  COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,
  COALESCE(NULLIF(TRIM(v.created_by),''), NULLIF(TRIM(f.created_by),'')) AS created_by_enriched,

  COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), fl.base)::text           AS transgene_base_code_filled,
  COALESCE(NULLIF(TRIM(v.allele_number::text), ''), (fl.num)::text)::text    AS allele_number_filled,
  COALESCE(fl.acode, fl.aname, NULLIF(TRIM(v.transgene_name), ''), fl.base)::text AS allele_code_filled,

  (
    CASE
      WHEN COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), fl.base) IS NOT NULL
       AND COALESCE(NULLIF(TRIM(v.allele_number::text), ''), (fl.num)::text) IS NOT NULL
      THEN
        'Tg(' ||
        (
          regexp_replace(lower(COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), fl.base)), '[0-9]+$', '')
          ||
          lpad(regexp_replace(lower(COALESCE(NULLIF(TRIM(v.transgene_base_code), ''), fl.base)), '^[A-Za-z]+', ''), 4, '0')
        ) || ')' ||
        COALESCE(fl.acode, fl.aname, (fl.num)::text)
      ELSE NULL
    END
  )::text AS transgene_pretty_filled

FROM public.vw_fish_overview v
LEFT JOIN public.fish f
  ON UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code))
LEFT JOIN public.fish_seed_batches fsb ON fsb.fish_id = f.id_uuid
LEFT JOIN public.seed_batches sb       ON sb.seed_batch_id = fsb.seed_batch_id
LEFT JOIN first_link fl                ON fl.fish_id = f.id_uuid;
