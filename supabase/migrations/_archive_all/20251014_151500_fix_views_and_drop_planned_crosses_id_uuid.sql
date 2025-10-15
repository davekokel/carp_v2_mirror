-- Step 1: rewrite dependent views to reference planned_crosses.id
CREATE OR REPLACE VIEW public.vw_clutches_concept_overview AS
SELECT
  c.id AS clutch_id,
  c.clutch_code,
  c.name AS clutch_name,
  c.nickname AS clutch_nickname,
  pc.id AS planned_cross_id,
  c.created_at
FROM public.clutches c
LEFT JOIN public.planned_crosses pc ON pc.id = c.planned_cross_id;

CREATE OR REPLACE VIEW public.vw_clutches_overview_human AS
SELECT
  c.id,
  c.clutch_code,
  c.clutch_name,
  c.clutch_nickname,
  pc.id AS planned_cross_id,
  c.created_by,
  c.created_at
FROM public.clutches c
LEFT JOIN public.planned_crosses pc ON pc.id = c.planned_cross_id;

CREATE OR REPLACE VIEW public.vw_planned_clutches_overview AS
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
LEFT JOIN public.planned_crosses pc ON pc.clutch_id = cp.id;

-- Step 2: now it's safe to drop the old column
ALTER TABLE public.planned_crosses DROP COLUMN IF EXISTS id_uuid;
