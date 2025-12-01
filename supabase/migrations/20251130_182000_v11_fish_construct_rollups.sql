BEGIN;

DROP VIEW IF EXISTS public.v11_fish_construct_rollups;

-- Derive canonical construct / transgene-base-code rollups per fish instance
-- using the existing v11_fish_allele_rollups view.
CREATE VIEW public.v11_fish_construct_rollups AS
WITH pairs AS (
  SELECT
    fa.fish_instance_id,
    -- each "pair" looks like "transgene_base_code:alleleNameOrNumber"
    trim(split_part(pair, ':', 1)) AS transgene_base_code
  FROM public.v11_fish_allele_rollups fa
  CROSS JOIN LATERAL regexp_split_to_table(
    COALESCE(fa.allele_canonical_rollup, ''),
    ';'
  ) AS pair
  WHERE fa.allele_canonical_rollup IS NOT NULL
    AND fa.allele_canonical_rollup <> ''
),
agg AS (
  SELECT
    fish_instance_id,
    -- canonical, sorted, deduped list of transgene_base_code values
    string_agg(DISTINCT transgene_base_code, '||' ORDER BY transgene_base_code)
      AS genotype_basecodes
  FROM pairs
  WHERE transgene_base_code <> ''
  GROUP BY fish_instance_id
)
SELECT
  fi.id         AS fish_instance_id,
  fi.fish_code  AS fish_code,
  a.genotype_basecodes
FROM public.fish_instances_v10 fi
LEFT JOIN agg a
  ON a.fish_instance_id = fi.id;

COMMENT ON VIEW public.v11_fish_construct_rollups IS
  'Per-fish canonical construct/transgene-base-code rollup for v11 genotypes, derived from v11_fish_allele_rollups.';

COMMIT;
