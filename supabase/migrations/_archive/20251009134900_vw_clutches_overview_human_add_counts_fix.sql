BEGIN;

DROP VIEW IF EXISTS public.vw_clutches_overview_human;

CREATE VIEW public.vw_clutches_overview_human AS
WITH base AS (
  SELECT
    c.id_uuid                         AS clutch_id,
    c.date_birth,
    c.created_by,
    c.created_at,
    c.note,
    c.batch_label,
    c.seed_batch_id,
    c.planned_cross_id,
    cp.clutch_code                    AS clutch_code,
    cp.planned_name                   AS clutch_name,
    COALESCE(mt.label, mt.tank_code)  AS mom_tank_label,
    COALESCE(ft.label, ft.tank_code)  AS dad_tank_label,
    c.cross_id
  FROM public.clutches c
  LEFT JOIN public.planned_crosses pc ON pc.id_uuid = c.planned_cross_id
  LEFT JOIN public.clutch_plans    cp ON cp.id_uuid = pc.clutch_id
  LEFT JOIN public.containers      mt ON mt.id_uuid = pc.mother_tank_id
  LEFT JOIN public.containers      ft ON ft.id_uuid = pc.father_tank_id
),
instances AS (
  SELECT cc.clutch_id, COUNT(*)::int AS n_instances
  FROM public.clutch_containers cc
  GROUP BY cc.clutch_id
),
crosses_via_clutches AS (
  -- 1 if clutches.cross_id links to a crosses row, else 0
  SELECT b.clutch_id, COUNT(x.id_uuid)::int AS n_crosses
  FROM base b
  LEFT JOIN public.crosses x ON x.id_uuid = b.cross_id
  GROUP BY b.clutch_id
)
SELECT
  b.clutch_id,
  b.date_birth,
  b.created_by,
  b.created_at,
  b.note,
  b.batch_label,
  b.seed_batch_id,
  b.clutch_code,
  b.clutch_name,
  NULL::text             AS clutch_nickname,
  b.mom_tank_label,
  b.dad_tank_label,
  COALESCE(i.n_instances, 0) AS n_instances,
  COALESCE(cx.n_crosses, 0)  AS n_crosses
FROM base b
LEFT JOIN instances           i  ON i.clutch_id = b.clutch_id
LEFT JOIN crosses_via_clutches cx ON cx.clutch_id = b.clutch_id
ORDER BY COALESCE(b.date_birth::timestamp, b.created_at) DESC NULLS LAST;

COMMIT;
