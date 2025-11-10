BEGIN;

DROP VIEW IF EXISTS public.v_clutches_overview CASCADE;

CREATE VIEW public.v_clutches_overview AS
WITH base AS (
  SELECT
    ci.id                         AS clutch_instance_id,
    ci.clutch_instance_code       AS clutch_code,
    ci.created_at                 AS clutch_created_at,
    cr.id                         AS cross_id,
    cr.tank_pair_id               AS tank_pair_id,
    cr.tank_pair_id::text         AS tank_pair_code,   -- stringified for UI compatibility
    cr.cross_run_code,
    cr.cross_date
  FROM public.clutch_instances ci
  LEFT JOIN public.crosses cr ON cr.id = ci.cross_instance_id
),
tc AS (
  SELECT
    b.clutch_instance_id,
    tc.id AS treated_clutch_id,
    tc.treated_clutch_code
  FROM base b
  LEFT JOIN public.treated_clutches tc
    ON tc.clutch_instance_id = b.clutch_instance_id
),
tx AS (
  SELECT
    tc.clutch_instance_id,
    COALESCE(string_agg(DISTINCT t.name, ',' ORDER BY t.name), '') AS treatments,
    COUNT(DISTINCT t.id) AS n_treatments
  FROM tc
  LEFT JOIN public.join_clutch_treatments jct
    ON jct.treated_clutch_id = tc.treated_clutch_id
  LEFT JOIN public.treatments t
    ON t.id = jct.treatment_id
  GROUP BY tc.clutch_instance_id
)
SELECT
  b.clutch_code,
  b.clutch_instance_id,
  b.clutch_created_at,
  b.tank_pair_id,
  b.tank_pair_code,
  b.cross_run_code,
  b.cross_date,
  COALESCE(tx.treatments,'')   AS treatments,
  COALESCE(tx.n_treatments,0)  AS n_treatments
FROM base b
LEFT JOIN tx ON tx.clutch_instance_id = b.clutch_instance_id;

COMMIT;
