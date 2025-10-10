-- Simplified canonical view that avoids early dependency on fish_seed_batches_map.
-- Later migrations can replace/extend it.
CREATE OR REPLACE VIEW public.v_fish_overview_canonical AS
WITH links AS (
  SELECT
    fta.fish_id,
    fta.transgene_base_code,
    fta.allele_number,
    fta.zygosity,
    fta.created_at,
    (fta.transgene_base_code || '-' || fta.allele_number)::text AS allele_code,
    row_number() OVER (
      PARTITION BY fta.fish_id
      ORDER BY fta.created_at DESC NULLS LAST, fta.transgene_base_code, fta.allele_number
    ) AS rn
  FROM public.fish_transgene_alleles fta
),
agg AS (
  SELECT
    f.id_uuid,
    array_remove(array_agg(DISTINCT l.transgene_base_code), NULL) AS transgene_base_codes,
    array_remove(array_agg(DISTINCT l.allele_code),         NULL) AS allele_codes,
    array_remove(array_agg(DISTINCT l.zygosity),             NULL) AS zygosities,
    max(l.transgene_base_code) FILTER (WHERE l.rn = 1) AS primary_transgene_base_code,
    max(l.allele_code)          FILTER (WHERE l.rn = 1) AS primary_allele_code,
    max(l.zygosity)             FILTER (WHERE l.rn = 1) AS primary_zygosity
  FROM public.fish f
  LEFT JOIN links l ON l.fish_id = f.id_uuid
  GROUP BY f.id_uuid
),
lists AS (
  SELECT
    a.id_uuid,
    CASE WHEN a.transgene_base_codes IS NULL THEN NULL ELSE array_to_string(a.transgene_base_codes, ', ') END AS transgene_base_codes_list,
    CASE WHEN a.allele_codes         IS NULL THEN NULL ELSE array_to_string(a.allele_codes,         ', ') END AS allele_codes_list,
    CASE WHEN a.zygosities           IS NULL THEN NULL ELSE array_to_string(a.zygosities,           ', ') END AS zygosities_list
  FROM agg a
)
SELECT
  f.id_uuid,
  l.transgene_base_codes_list,
  l.allele_codes_list,
  l.zygosities_list,
  a.primary_transgene_base_code,
  a.primary_allele_code,
  a.primary_zygosity,
  NULL::text AS batch_label,
  NULL::text AS seed_batch_id
FROM public.fish f
LEFT JOIN lists l ON l.id_uuid = f.id_uuid
LEFT JOIN agg   a ON a.id_uuid = f.id_uuid;
