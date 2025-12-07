BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_flat_overview;

CREATE VIEW public.v11_clutch_flat_overview AS
WITH base AS (
  -- this should be your existing definition minus the final SELECT;
  -- I'm just sketching the important piece here:
  SELECT
    c.id           AS clutch_id,
    c.clutch_code  AS clutch_code,
    c.clutch_date,
    c.source_system,
    -- existing modern parent label, if any
    x.parent_cross_pretty,
    ...
  FROM public.clutches c
  LEFT JOIN public.v11_clutch_star x
    ON x.clutch_id = c.id
  ...
),
legacy_parents AS (
  SELECT
    clutch_id,
    legacy_parents_pretty
  FROM public.v11_clutch_legacy_parents
)
SELECT
  b.*,
  -- unified Parents column:
  COALESCE(lp.legacy_parents_pretty, b.parent_cross_pretty) AS parents
FROM base b
LEFT JOIN legacy_parents lp
  ON lp.clutch_id = b.clutch_id;

COMMENT ON VIEW public.v11_clutch_flat_overview IS
'Flat clutch overview (clutch × treated_clutch × selection) with unified parent labels: tank-pair crosses for modern clutches, legacy parents for source_system=''legacy_imaging''.';
COMMIT;
