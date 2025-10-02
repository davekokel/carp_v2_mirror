-- Robust labeled overview: resolve fish_id via code OR name, then fill fields
CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
SELECT
  v.*,

  -- batch label via mapping (uses resolved fish_id)
  COALESCE(sb.batch_label, fsb.seed_batch_id) AS batch_label,

  -- created_by enrichment (prefer view's created_by, else fish table)
  COALESCE(NULLIF(TRIM(v.created_by),''), NULLIF(TRIM(f.created_by),'')) AS created_by_enriched,

  -- Filled transgene columns (prefer v.*; else first linked allele for this fish_id)
  COALESCE(
    NULLIF(TRIM(v.transgene_base_code),''),
    (
      SELECT fta.transgene_base_code
      FROM public.fish_transgene_alleles fta
      WHERE fta.fish_id = fx.fish_id
      ORDER BY fta.allele_number NULLS LAST
      LIMIT 1
    )
  ) AS transgene_base_code_filled,

  COALESCE(
    v.allele_number,
    (
      SELECT fta.allele_number
      FROM public.fish_transgene_alleles fta
      WHERE fta.fish_id = fx.fish_id
      ORDER BY fta.allele_number NULLS LAST
      LIMIT 1
    )
  ) AS allele_number_filled,

  COALESCE(
    NULLIF(TRIM(v.transgene_name),''),
    (
      SELECT COALESCE(tg.transgene_name, fta.transgene_base_code)
      FROM public.fish_transgene_alleles fta
      LEFT JOIN public.transgenes tg
        ON tg.transgene_base_code = fta.transgene_base_code
      WHERE fta.fish_id = fx.fish_id
      ORDER BY fta.allele_number NULLS LAST
      LIMIT 1
    )
  ) AS transgene_name_filled

FROM public.vw_fish_overview v

-- LATERAL: resolve the fish_id for this row using fish_code OR fish_name
LEFT JOIN LATERAL (
  SELECT f.id_uuid AS fish_id
  FROM public.fish f
  WHERE
       (v.fish_code  IS NOT NULL AND UPPER(TRIM(f.fish_code)) = UPPER(TRIM(v.fish_code)))
    OR (v.fish_name IS NOT NULL AND UPPER(TRIM(f.name))      = UPPER(TRIM(v.fish_name)))
  LIMIT 1
) fx ON TRUE

-- Bring fish row only for created_by enrichment
LEFT JOIN public.fish f
  ON f.id_uuid = fx.fish_id

-- Batch label mapping from resolved fish_id
LEFT JOIN public.fish_seed_batches fsb
  ON fsb.fish_id = fx.fish_id
LEFT JOIN public.seed_batches sb
  ON sb.seed_batch_id = fsb.seed_batch_id;
