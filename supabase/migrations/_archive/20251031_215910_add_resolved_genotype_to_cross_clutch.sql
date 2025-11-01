-- Add a resolved clutch genotype to the cross+clutch overview view.
-- If your current view name differs, substitute accordingly.

CREATE OR REPLACE VIEW public.v_cross_clutch_instances AS
WITH base AS (
  SELECT
    ci.id                          AS cross_instance_id,
    ci.cross_run_code              AS cross_code,
    ci.cross_date                  AS cross_date,
    ci.tank_pair_code              AS tank_pair_code,
    cl.id                          AS clutch_instance_id,
    cl.clutch_instance_code        AS clutch_code,

    -- keep existing columns you already expose (mom/dad fish/tanks, etc.) …

    -- expose raw genotype sources for coalesce
    cl.observed_genotype_pretty,
    cl.expected_genotype_pretty,
    cl.clutch_genotype_pretty
  FROM public.cross_instances  ci
  LEFT JOIN public.clutch_instances cl ON cl.cross_instance_id = ci.id
)
SELECT
  b.*,

  -- resolved clutch genotype (observed → expected → legacy)
  COALESCE(NULLIF(b.observed_genotype_pretty,''),
           NULLIF(b.expected_genotype_pretty,''),
           NULLIF(b.clutch_genotype_pretty,''))                      AS clutch_genotype_resolved

FROM base b
ORDER BY b.cross_date DESC NULLS LAST, b.cross_code;
