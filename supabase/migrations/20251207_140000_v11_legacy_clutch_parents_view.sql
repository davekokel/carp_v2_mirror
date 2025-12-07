BEGIN;

DROP VIEW IF EXISTS public.v11_legacy_clutch_parents_pretty;

CREATE VIEW public.v11_legacy_clutch_parents_pretty AS
SELECT
  c.id::uuid        AS clutch_id,
  c.clutch_code,
  -- "Dennis (F2 of allele 318) × Abe (F2 of allele 309)"
  TRIM(
    BOTH ' ' FROM
      COALESCE(lcp.parent_female_label, '') ||
      CASE
        WHEN lcp.parent_female_label IS NOT NULL
             AND lcp.parent_male_label IS NOT NULL
          THEN ' × '
        ELSE ''
      END ||
      COALESCE(lcp.parent_male_label, '')
  )                 AS parents_pretty,
  -- Optional: compact allele display, e.g. "pdqm-34(309/310); pdqm-36(318)"
  NULL::text        AS parents_genotype_allele_style
FROM public.clutches c
JOIN raw.legacy_clutch_parents_v9 lcp
  ON lcp.clutch_code = c.clutch_code
WHERE c.source_system = 'legacy_imaging';

COMMENT ON VIEW public.v11_legacy_clutch_parents_pretty IS
'Legacy-only clutch parent labels derived from raw.legacy_clutch_parents_v9 (text labels).';

COMMIT;
