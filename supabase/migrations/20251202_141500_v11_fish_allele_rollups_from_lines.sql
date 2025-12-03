BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_allele_rollups AS
WITH line_alleles AS (
  SELECT
    fi.id                 AS fish_instance_id,   -- uuid, no cast
    c.construct_code      AS construct_code,
    j.allele_number       AS allele_number,
    ta.allele_name,
    ta.allele_nickname
  FROM public.fish_instances_v10 fi
  JOIN public.join_line_alleles j
    ON j.line_id = fi.line_id
  JOIN public.constructs c
    ON c.id = j.construct_id
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = c.construct_code
   AND ta.allele_number       = j.allele_number
),
base AS (
  SELECT
    la.fish_instance_id,
    (la.construct_code || ':' || la.allele_number::text) AS canon,
    (
      '#' || la.allele_number::text ||
      CASE
        WHEN la.allele_name IS NOT NULL AND la.allele_name <> '' THEN ' ' || la.allele_name
        ELSE ''
      END ||
      CASE
        WHEN la.allele_nickname IS NOT NULL AND la.allele_nickname <> '' THEN ' (' || la.allele_nickname || ')'
        ELSE ''
      END
    ) AS label
  FROM line_alleles la
)
SELECT
  fish_instance_id,
  string_agg(DISTINCT canon, ' + ' ORDER BY canon) AS allele_canonical_rollup,
  string_agg(DISTINCT label, ', ' ORDER BY label)  AS allele_label_rollup
FROM base
GROUP BY fish_instance_id;

COMMENT ON VIEW public.v11_fish_allele_rollups IS
'Per-fish_instance_v10 allele rollups derived from line-level join_line_alleles (Model A: group=basecode, line=allele, instance=stage/birthday).';

COMMIT;
