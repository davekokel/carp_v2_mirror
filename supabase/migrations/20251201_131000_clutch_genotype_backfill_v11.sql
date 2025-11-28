BEGIN;

-- If the columns already exist, leave them alone. No adds here.

DROP TABLE IF EXISTS tmp_clutch_genotypes;
CREATE TEMP TABLE tmp_clutch_genotypes (
  legacy_clutch_key      text,
  genotype_base_codes    text,
  genotype_allele_codes  text
);

-- Load the legacy v9 sheet using COPY FROM PROGRAM (works inside migrations)
COPY tmp_clutch_genotypes
FROM PROGRAM 'cat seed_kits/legacy_wrangling_v2/working/legacy_imaging_annotations_for_db_v9.csv'
CSV HEADER;

-- Aggregate genotype information by clutch
WITH agg AS (
  SELECT
    legacy_clutch_key,
    string_agg(DISTINCT genotype_base_codes, ',' ORDER BY genotype_base_codes) AS base_codes,
    string_agg(DISTINCT genotype_allele_codes, ',' ORDER BY genotype_allele_codes) AS allele_codes
  FROM tmp_clutch_genotypes
  WHERE genotype_base_codes    IS NOT NULL
     OR genotype_allele_codes  IS NOT NULL
  GROUP BY legacy_clutch_key
)

UPDATE public.clutches c
SET
  genotype_base_codes   = a.base_codes,
  genotype_allele_codes = a.allele_codes
FROM agg a
WHERE c.clutch_code = a.legacy_clutch_key;

COMMIT;
