-- Rewrite views to stop referencing clutches.id_uuid (use only .id; alias as needed)

-- v_clutches_concept_overview
CREATE OR REPLACE VIEW public.v_clutches_concept_overview AS
WITH base AS (
  SELECT
    cp.id                         AS clutch_plan_id,
    COALESCE(pc.id, pc.id_uuid)   AS planned_cross_id,
    cp.clutch_code,
    cp.planned_name               AS clutch_name,
    cp.planned_nickname           AS clutch_nickname,
    pc.cross_date                 AS date_planned,
    COALESCE(cp.note, pc.note)    AS note,
    cp.created_by,
    cp.created_at
  FROM public.clutch_plans cp
  LEFT JOIN public.planned_crosses pc ON pc.clutch_id = cp.id
), inst AS (
  SELECT c.planned_cross_id,
         COUNT(*)::int          AS n_instances,
         MAX(c.date_birth)      AS latest_date_birth,
         COUNT(c.cross_id)::int AS n_crosses
  FROM public.clutches c
  GROUP BY c.planned_cross_id
)
SELECT b.clutch_plan_id, b.planned_cross_id, b.clutch_code, b.clutch_name, b.clutch_nickname,
       b.date_planned, b.created_by, b.created_at, b.note,
       COALESCE(i.n_instances,0) AS n_instances,
       COALESCE(i.n_crosses,0)   AS n_crosses,
       i.latest_date_birth
FROM base b
LEFT JOIN inst i ON i.planned_cross_id = b.planned_cross_id
ORDER BY COALESCE(b.date_planned::timestamp, b.created_at) DESC NULLS LAST;

-- v_clutches_overview_human
CREATE OR REPLACE VIEW public.v_clutches_overview_human AS
WITH base AS (
  SELECT
    c.id                        AS clutch_id,
    c.date_birth,
    c.created_by,
    c.created_at,
    c.note,
    c.batch_label,
    c.seed_batch_id,
    c.planned_cross_id,
    cp.clutch_code,
    cp.planned_name            AS clutch_name,
    COALESCE(mt.label, mt.tank_code) AS mom_tank_label,
    COALESCE(ft.label, ft.tank_code) AS dad_tank_label,
    c.cross_id
  FROM public.clutches c
  LEFT JOIN public.planned_crosses pc ON pc.id = c.planned_cross_id
  LEFT JOIN public.clutch_plans cp    ON cp.id = pc.clutch_id
  LEFT JOIN public.containers mt      ON mt.id = pc.mother_tank_id
  LEFT JOIN public.containers ft      ON ft.id = pc.father_tank_id
), instances AS (
  SELECT cc.clutch_id, COUNT(*)::int AS n_instances
  FROM public.clutch_containers cc
  GROUP BY cc.clutch_id
), crosses_via_clutches AS (
  SELECT b.clutch_id, COUNT(x.id)::int AS n_crosses
  FROM base b
  LEFT JOIN public.crosses x ON x.id = b.cross_id
  GROUP BY b.clutch_id
)
SELECT b.clutch_id, b.date_birth, b.created_by, b.created_at, b.note, b.batch_label, b.seed_batch_id,
       b.clutch_code, b.clutch_name,
       NULL::text AS clutch_nickname,
       b.mom_tank_label, b.dad_tank_label,
       COALESCE(i.n_instances,0) AS n_instances,
       COALESCE(cx.n_crosses,0)  AS n_crosses
FROM base b
LEFT JOIN instances i ON i.clutch_id = b.clutch_id
LEFT JOIN crosses_via_clutches cx ON cx.clutch_id = b.clutch_id
ORDER BY COALESCE(b.date_birth::timestamp, b.created_at) DESC NULLS LAST;

-- v_cross_runs
CREATE OR REPLACE VIEW public.v_cross_runs AS
WITH cl AS (
  SELECT clutches.cross_instance_id, COUNT(*)::int AS n_clutches
  FROM public.clutches
  GROUP BY clutches.cross_instance_id
), cnt AS (
  SELECT c.cross_instance_id, COUNT(cc.*)::int AS n_containers
  FROM public.clutches c
  JOIN public.clutch_containers cc ON cc.clutch_id = c.id
  GROUP BY c.cross_instance_id
)
SELECT
  ci.id                AS cross_instance_id,
  ci.cross_run_code,
  ci.cross_date,
  x.id                 AS cross_id,
  COALESCE(x.cross_code, x.id::text) AS cross_code,
  x.mother_code        AS mom_code,
  x.father_code        AS dad_code,
  cm.label             AS mother_tank_label,
  cf.label             AS father_tank_label,
  ci.note              AS run_note,
  ci.created_by        AS run_created_by,
  ci.created_at        AS run_created_at,
  COALESCE(cl.n_clutches,0)    AS n_clutches,
  COALESCE(cnt.n_containers,0) AS n_containers
FROM public.cross_instances ci
JOIN public.crosses x          ON x.id = ci.cross_id
LEFT JOIN public.containers cm ON cm.id = ci.mother_tank_id
LEFT JOIN public.containers cf ON cf.id = ci.father_tank_id
LEFT JOIN cl ON cl.cross_instance_id = ci.id
LEFT JOIN cnt ON cnt.cross_instance_id = ci.id
ORDER BY ci.cross_date DESC, ci.created_at DESC;

-- v_crosses_concept
CREATE OR REPLACE VIEW public.v_crosses_concept AS
WITH runs AS (
  SELECT cross_instances.cross_id, COUNT(*)::int AS n_runs, MAX(cross_instances.cross_date) AS latest_cross_date
  FROM public.cross_instances
  GROUP BY cross_instances.cross_id
), cl AS (
  SELECT clutches.cross_id, COUNT(*)::int AS n_clutches
  FROM public.clutches
  GROUP BY clutches.cross_id
), cnt AS (
  SELECT c.cross_id, COUNT(cc.*)::int AS n_containers
  FROM public.clutches c
  JOIN public.clutch_containers cc ON cc.clutch_id = c.id
  GROUP BY c.cross_id
)
SELECT
  x.id                        AS cross_id,
  COALESCE(x.cross_code, x.id::text) AS cross_code,
  x.mother_code               AS mom_code,
  x.father_code               AS dad_code,
  x.created_by,
  x.created_at,
  COALESCE(runs.n_runs,0)     AS n_runs,
  runs.latest_cross_date,
  COALESCE(cl.n_clutches,0)   AS n_clutches,
  COALESCE(cnt.n_containers,0) AS n_containers
FROM public.crosses x
LEFT JOIN runs ON runs.cross_id = x.id
LEFT JOIN cl   ON cl.cross_id   = x.id
LEFT JOIN cnt  ON cnt.cross_id  = x.id
ORDER BY x.created_at DESC;
