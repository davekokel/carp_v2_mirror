BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_legacy_parents;

CREATE VIEW public.v11_clutch_legacy_parents AS
SELECT
  c.id            AS clutch_id,
  c.clutch_code   AS clutch_code,
  lcp.parent_female_label,
  lcp.parent_male_label,
  -- pretty label: "mom × dad" (skips blanks cleanly)
  trim(
    BOTH ' '
    FROM concat_ws(
      ' × ',
      NULLIF(lcp.parent_female_label, ''),
      NULLIF(lcp.parent_male_label, '')
    )
  )              AS legacy_parents_pretty
FROM public.clutches c
LEFT JOIN raw.legacy_clutch_parents_v9 lcp
  ON lcp.clutch_code = c.clutch_code
WHERE c.source_system = 'legacy_imaging';

COMMENT ON VIEW public.v11_clutch_legacy_parents IS
'Legacy imaging only: one row per clutch with parent_female_label, parent_male_label, and a pretty "mom × dad" string.';

COMMIT;
