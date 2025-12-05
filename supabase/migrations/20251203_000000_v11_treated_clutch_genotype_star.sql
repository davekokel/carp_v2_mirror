BEGIN;

DROP VIEW IF EXISTS public.v11_treated_clutch_genotype_star;

CREATE VIEW public.v11_treated_clutch_genotype_star AS
WITH base AS (
  SELECT
    tc.id                AS treated_clutch_id,
    tc.treated_clutch_code,
    c.id                 AS clutch_id,
    c.clutch_code
  FROM public.treated_clutches_v11 tc
  JOIN public.clutches c
    ON c.id = tc.clutch_id
),
cg AS (
  SELECT
    cg.id                AS clutch_genotype_id,
    cg.clutch_id,
    cg.genotype_v11_id,
    cg.is_enabled,
    cg.expected_fraction,
    cg.expected_percent_label,
    cg.notes,
    cg.created_at,
    cg.created_by
  FROM public.clutch_genotypes_v11 cg
),
has_narrowing AS (
  SELECT DISTINCT treated_clutch_id
  FROM public.treated_clutch_genotypes_v11
)
SELECT
  b.treated_clutch_id,
  b.treated_clutch_code,
  b.clutch_id,
  b.clutch_code,
  cg.clutch_genotype_id,
  g.id                  AS genotype_v11_id,
  g.genotype_code,
  g.genotype_basecodes  AS genotype_basecodes,
  g.genotype_pretty,
  cg.is_enabled,
  cg.expected_fraction,
  cg.expected_percent_label,
  cg.notes,
  cg.created_at,
  cg.created_by,
  (hn.treated_clutch_id IS NOT NULL)        AS is_narrowed,
  COALESCE(tcg.is_primary, false)           AS is_primary
FROM base b
JOIN cg
  ON cg.clutch_id = b.clutch_id
JOIN public.genotypes_v11 g
  ON g.id = cg.genotype_v11_id
LEFT JOIN public.treated_clutch_genotypes_v11 tcg
  ON tcg.treated_clutch_id = b.treated_clutch_id
 AND tcg.clutch_genotype_id = cg.clutch_genotype_id
LEFT JOIN has_narrowing hn
  ON hn.treated_clutch_id = b.treated_clutch_id
WHERE
  hn.treated_clutch_id IS NULL         -- no narrowing rows → keep all genotypes
  OR tcg.treated_clutch_id IS NOT NULL -- narrowing exists → only mapped genotypes
ORDER BY
  b.treated_clutch_code,
  g.genotype_code;

COMMENT ON VIEW public.v11_treated_clutch_genotype_star IS
'Treated-clutch × expected-genotype rollup. If a treated clutch has no rows in treated_clutch_genotypes_v11, all clutch_genotypes_v11 for its parent clutch are returned with is_narrowed=false. If narrowing rows exist, only those genotypes are returned for that treated clutch with is_narrowed=true and is_primary carried through.';

COMMIT;
