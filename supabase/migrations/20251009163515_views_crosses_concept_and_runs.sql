BEGIN;

-- ========== View: Concept-level crosses ==========
-- One row per entry in public.crosses (concept).
-- Includes counts of runs (cross_instances), latest run date,
-- total clutches produced across all runs, and total containers across those clutches.
CREATE OR REPLACE VIEW public.vw_crosses_concept AS
WITH runs AS (
  SELECT
    ci.cross_id,
    COUNT(*)::int               AS n_runs,
    MAX(ci.cross_date)          AS latest_cross_date
  FROM public.cross_instances ci
  GROUP BY ci.cross_id
),
cl AS (
  SELECT
    c.cross_id,
    COUNT(*)::int               AS n_clutches
  FROM public.clutches c
  GROUP BY c.cross_id
),
cnt AS (
  SELECT
    c.cross_id,
    COUNT(cc.*)::int            AS n_containers
  FROM public.clutches c
  JOIN public.clutch_containers cc ON cc.clutch_id = c.id_uuid
  GROUP BY c.cross_id
)
SELECT
  x.id_uuid                                         AS cross_id,
  COALESCE(x.cross_code, x.id_uuid::text)           AS cross_code,
  x.mother_code                                     AS mom_code,
  x.father_code                                     AS dad_code,
  x.created_by,
  x.created_at,
  COALESCE(runs.n_runs, 0)                          AS n_runs,
  runs.latest_cross_date                            AS latest_cross_date,
  COALESCE(cl.n_clutches, 0)                        AS n_clutches,
  COALESCE(cnt.n_containers, 0)                     AS n_containers
FROM public.crosses x
LEFT JOIN runs ON runs.cross_id = x.id_uuid
LEFT JOIN cl   ON cl.cross_id   = x.id_uuid
LEFT JOIN cnt  ON cnt.cross_id  = x.id_uuid
ORDER BY x.created_at DESC;

-- ========== View: Run-level crosses (instances) ==========
-- One row per public.cross_instances.
-- Includes concept cross_code, run code/date, parent tank labels,
-- clutches produced by this run, and containers from those clutches.
CREATE OR REPLACE VIEW public.vw_cross_runs_overview AS
WITH cl AS (
  SELECT
    c.cross_instance_id,
    COUNT(*)::int             AS n_clutches
  FROM public.clutches c
  GROUP BY c.cross_instance_id
),
cnt AS (
  SELECT
    c.cross_instance_id,
    COUNT(cc.*)::int          AS n_containers
  FROM public.clutches c
  JOIN public.clutch_containers cc ON cc.clutch_id = c.id_uuid
  GROUP BY c.cross_instance_id
)
SELECT
  ci.id_uuid                                      AS cross_instance_id,
  ci.cross_run_code,
  ci.cross_date,
  x.id_uuid                                       AS cross_id,
  COALESCE(x.cross_code, x.id_uuid::text)         AS cross_code,
  x.mother_code                                   AS mom_code,
  x.father_code                                   AS dad_code,
  cm.label                                        AS mother_tank_label,
  cf.label                                        AS father_tank_label,
  ci.note                                         AS run_note,
  ci.created_by                                   AS run_created_by,
  ci.created_at                                   AS run_created_at,
  COALESCE(cl.n_clutches, 0)                      AS n_clutches,
  COALESCE(cnt.n_containers, 0)                   AS n_containers
FROM public.cross_instances ci
JOIN public.crosses x           ON x.id_uuid = ci.cross_id
LEFT JOIN public.containers cm  ON cm.id_uuid = ci.mother_tank_id
LEFT JOIN public.containers cf  ON cf.id_uuid = ci.father_tank_id
LEFT JOIN cl                    ON cl.cross_instance_id  = ci.id_uuid
LEFT JOIN cnt                   ON cnt.cross_instance_id = ci.id_uuid
ORDER BY ci.cross_date DESC, ci.created_at DESC;

COMMIT;
