BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_flat_overview_with_parents;

CREATE VIEW public.v11_clutch_flat_overview_with_parents AS
SELECT
  f.*,
  COALESCE(lp.legacy_parents_pretty, f.parent_cross_pretty) AS parents
FROM public.v11_clutch_flat_overview f
LEFT JOIN public.v11_clutch_legacy_parents lp
  ON lp.clutch_code = f.clutch_code;

COMMENT ON VIEW public.v11_clutch_flat_overview_with_parents IS
'Wrapper over v11_clutch_flat_overview that adds a unified parents column:
 tank-pair parents for modern clutches (parent_cross_pretty),
 legacy parents for source_system = ''legacy_imaging''.';

COMMIT;
