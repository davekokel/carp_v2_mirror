BEGIN;

-- Materialize normalized rows from raw links
CREATE TEMP TABLE _norm AS
SELECT DISTINCT
  LOWER(TRIM(fish_name)) AS fish_name_key,

  -- base_code: transgene_name -> Tg(...) inside allele_name -> text before '^'
  COALESCE(
    NULLIF(LOWER(TRIM(transgene_name)), ''),
    NULLIF(
      LOWER(TRIM(
        REGEXP_REPLACE(allele_name, '.*Tg\(([^)]+)\).*', '\1')
      )),
      ''
    ),
    NULLIF(LOWER(TRIM(SPLIT_PART(allele_name, '^', 1))), '')
  ) AS base_code,

  -- allele_number: text after '^'
  NULLIF(LOWER(TRIM(SPLIT_PART(allele_name, '^', 2))), '') AS allele_number
FROM raw.fish_links_has_transgenes_csv
WHERE COALESCE(TRIM(allele_name), '') <> '';

-- 1) Ensure transgenes exist
INSERT INTO public.transgenes (transgene_base_code)
SELECT DISTINCT n.base_code
FROM _norm n
LEFT JOIN public.transgenes g
  ON g.transgene_base_code = n.base_code
WHERE n.base_code IS NOT NULL
  AND g.transgene_base_code IS NULL;

-- 2) Ensure specific alleles exist
INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, description)
SELECT DISTINCT
  n.base_code,
  n.allele_number,
  NULL::text AS description
FROM _norm n
JOIN public.transgenes g
  ON g.transgene_base_code = n.base_code
WHERE n.base_code IS NOT NULL
  AND n.allele_number IS NOT NULL
ON CONFLICT (transgene_base_code, allele_number) DO NOTHING;

-- 3) Link fish to alleles
INSERT INTO public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
SELECT DISTINCT
  f.id,
  n.base_code,
  n.allele_number
FROM _norm n
JOIN public.fish f
  ON LOWER(TRIM(f.name)) = n.fish_name_key
   OR LOWER(TRIM(f.fish_code)) = n.fish_name_key
JOIN public.transgene_alleles a
  ON a.transgene_base_code = n.base_code
 AND a.allele_number       = n.allele_number
WHERE n.base_code IS NOT NULL
  AND n.allele_number IS NOT NULL
ON CONFLICT (fish_id, transgene_base_code, allele_number) DO NOTHING;

COMMIT;
