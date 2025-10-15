-- Rewrite views to no longer depend on clutch_plans.id_uuid

-- vw_clutches_concept_overview
CREATE OR REPLACE VIEW public.vw_clutches_concept_overview AS
WITH base AS (
  SELECT
    cp.id                         AS clutch_plan_id,
    pc.id                         AS planned_cross_id,
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
  SELECT c.planned_cross_id, count(*)::int AS n_instances,
         max(c.date_birth) AS latest_date_birth, count(c.cross_id)::int AS n_crosses
  FROM public.clutches c
  GROUP BY c.planned_cross_id
), cont AS (
  SELECT c.planned_cross_id, count(cc.*)::int AS n_containers
  FROM public.clutches c
  JOIN public.clutch_containers cc ON cc.clutch_id = c.id_uuid  -- clutches still uses id_uuid as row id in the view; harmless
  GROUP BY c.planned_cross_id
)
SELECT b.clutch_plan_id, b.planned_cross_id, b.clutch_code, b.clutch_name, b.clutch_nickname,
       b.date_planned, b.created_by, b.created_at, b.note,
       COALESCE(i.n_instances,0) AS n_instances,
       COALESCE(i.n_crosses,0)   AS n_crosses,
       COALESCE(ct.n_containers,0) AS n_containers,
       i.latest_date_birth
FROM base b
LEFT JOIN inst i ON i.planned_cross_id = b.planned_cross_id
LEFT JOIN cont ct ON ct.planned_cross_id = b.planned_cross_id
ORDER BY COALESCE(b.date_planned::timestamp, b.created_at) DESC NULLS LAST;

-- vw_clutches_overview_human
CREATE OR REPLACE VIEW public.vw_clutches_overview_human AS
WITH base AS (
  SELECT
    c.id_uuid               AS clutch_id,
    c.date_birth,
    c.created_by,
    c.created_at,
    c.note,
    c.batch_label,
    c.seed_batch_id,
    c.planned_cross_id,
    cp.clutch_code,
    cp.planned_name         AS clutch_name,
    COALESCE(mt.label, mt.tank_code) AS mom_tank_label,
    COALESCE(ft.label, ft.tank_code) AS dad_tank_label,
    c.cross_id
  FROM public.clutches c
  LEFT JOIN public.planned_crosses pc ON pc.id = c.planned_cross_id
  LEFT JOIN public.clutch_plans cp    ON cp.id = pc.clutch_id
  LEFT JOIN public.containers mt      ON mt.id = pc.mother_tank_id
  LEFT JOIN public.containers ft      ON ft.id = pc.father_tank_id
), instances AS (
  SELECT cc.clutch_id, count(*)::int AS n_instances
  FROM public.clutch_containers cc
  GROUP BY cc.clutch_id
), crosses_via_clutches AS (
  SELECT b.clutch_id, count(x.id_uuid)::int AS n_crosses
  FROM base b
  LEFT JOIN public.crosses x ON x.id_uuid = b.cross_id
  GROUP BY b.clutch_id
)
SELECT b.clutch_id, b.date_birth, b.created_by, b.created_at, b.note, b.batch_label, b.seed_batch_id,
       b.clutch_code, b.clutch_name,
       NULL::text AS clutch_nickname,
       b.mom_tank_label, b.dad_tank_label,
       COALESCE(i.n_instances,0) AS n_instances,
       COALESCE(cx.n_crosses,0) AS n_crosses
FROM base b
LEFT JOIN instances i ON i.clutch_id = b.clutch_id
LEFT JOIN crosses_via_clutches cx ON cx.clutch_id = b.clutch_id
ORDER BY COALESCE(b.date_birth::timestamp, b.created_at) DESC NULLS LAST;

-- vw_planned_clutches_overview
CREATE OR REPLACE VIEW public.vw_planned_clutches_overview AS
WITH x AS (
  SELECT
    cp.id               AS clutch_plan_id,
    pc.id               AS planned_cross_id,
    cp.clutch_code,
    cp.planned_name     AS clutch_name,
    cp.planned_nickname AS clutch_nickname,
    pc.cross_date,
    cp.created_by,
    cp.created_at,
    COALESCE(cp.note, pc.note) AS note
  FROM public.clutch_plans cp
  LEFT JOIN public.planned_crosses pc ON pc.clutch_id = cp.id
), tx AS (
  SELECT t.clutch_id AS clutch_plan_id, count(*)::int AS n_treatments
  FROM public.clutch_plan_treatments t
  GROUP BY t.clutch_id
)
SELECT x.clutch_plan_id, x.planned_cross_id, x.clutch_code, x.clutch_name, x.clutch_nickname,
       x.cross_date, x.created_by, x.created_at, x.note,
       COALESCE(tx.n_treatments,0) AS n_treatments
FROM x
LEFT JOIN tx ON tx.clutch_plan_id = x.clutch_plan_id
ORDER BY COALESCE(x.cross_date::timestamp, x.created_at) DESC NULLS LAST;
