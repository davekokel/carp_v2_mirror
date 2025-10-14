-- 1) Rewrite dependent views to remove clutch_plans.id_uuid usage
CREATE OR REPLACE VIEW public.vw_clutches_concept_overview AS
WITH base AS (
  SELECT
    cp.id AS clutch_plan_id,
    COALESCE(pc.id, pc.id_uuid) AS planned_cross_id,
    cp.clutch_code,
    cp.planned_name AS clutch_name,
    cp.planned_nickname AS clutch_nickname,
    pc.cross_date AS date_planned,
    COALESCE(cp.note, pc.note) AS note,
    cp.created_by,
    cp.created_at
  FROM public.clutch_plans cp
  LEFT JOIN public.planned_crosses pc ON pc.clutch_id = cp.id
), inst AS (
  SELECT c.planned_cross_id, count(*)::int AS n_instances,
         max(c.date_birth) AS latest_date_birth, count(c.cross_id)::int AS n_crosses
  FROM public.clutches c
  GROUP BY c.planned_cross_id
)
SELECT b.clutch_plan_id, b.planned_cross_id, b.clutch_code, b.clutch_name, b.clutch_nickname,
       b.date_planned, b.created_by, b.created_at, b.note,
       COALESCE(i.n_instances,0) AS n_instances,
       COALESCE(i.n_crosses,0) AS n_crosses,
       i.latest_date_birth
FROM base b
LEFT JOIN inst i ON i.planned_cross_id = b.planned_cross_id
ORDER BY COALESCE(b.date_planned::timestamp, b.created_at) DESC NULLS LAST;

CREATE OR REPLACE VIEW public.vw_clutches_overview_human AS
WITH base AS (
  SELECT
    c.id_uuid AS clutch_id,
    c.date_birth,
    c.created_by,
    c.created_at,
    c.note,
    c.batch_label,
    c.seed_batch_id,
    c.planned_cross_id,
    cp.clutch_code,
    cp.planned_name AS clutch_name,
    mt.label AS mom_tank_label,
    ft.label AS dad_tank_label,
    c.cross_id
  FROM public.clutches c
  LEFT JOIN public.planned_crosses pc ON pc.id = c.planned_cross_id
  LEFT JOIN public.clutch_plans cp ON cp.id = pc.clutch_id
  LEFT JOIN public.containers mt ON mt.id = pc.mother_tank_id
  LEFT JOIN public.containers ft ON ft.id = pc.father_tank_id
)
SELECT * FROM base;

CREATE OR REPLACE VIEW public.vw_planned_clutches_overview AS
WITH x AS (
  SELECT
    cp.id AS clutch_plan_id,
    COALESCE(pc.id, pc.id_uuid) AS planned_cross_id,
    cp.clutch_code,
    cp.planned_name AS clutch_name,
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

-- 2) Retry clutch_plans PK swap
ALTER TABLE ONLY public.clutch_plan_treatments DROP CONSTRAINT IF EXISTS clutch_plan_treatments_clutch_id_fkey;
ALTER TABLE ONLY public.planned_crosses DROP CONSTRAINT IF EXISTS planned_crosses_clutch_id_fkey;

ALTER TABLE public.clutch_plans DROP COLUMN IF EXISTS id_uuid CASCADE;

ALTER TABLE ONLY public.clutch_plan_treatments
  ADD CONSTRAINT clutch_plan_treatments_clutch_id_fkey
  FOREIGN KEY (clutch_id) REFERENCES public.clutch_plans(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.planned_crosses
  ADD CONSTRAINT planned_crosses_clutch_id_fkey
  FOREIGN KEY (clutch_id) REFERENCES public.clutch_plans(id) ON DELETE CASCADE;
