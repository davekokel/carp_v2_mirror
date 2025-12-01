BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_construct_rollups AS
WITH base AS (
  SELECT
    fi.id                       AS fish_instance_id,
    fi.fish_code,
    c.base_code
  FROM public.fish_instances_v10 fi
  LEFT JOIN public.fish_transgene_alleles fta
    ON fta.fish_id = fi.id
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = fta.transgene_base_code
   AND ta.allele_number       = fta.allele_number
  LEFT JOIN public.constructs c
    ON c.base_code = ta.transgene_base_code
)
SELECT
  fish_instance_id,
  fish_code,
  COALESCE(
    string_agg(DISTINCT base_code, '||'),
    ''
  ) AS genotype_basecodes
FROM base
GROUP BY
  fish_instance_id,
  fish_code
ORDER BY
  fish_code;

COMMENT ON VIEW public.v11_fish_construct_rollups IS
  'v11: per fish_instance construct rollup: genotype_basecodes (construct base_codes).';

COMMIT;
