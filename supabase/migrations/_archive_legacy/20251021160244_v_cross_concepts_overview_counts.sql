\set ON_ERROR_STOP on
BEGIN;

-- Canonical concepts view at concept grain (1 row per clutch_plans).
-- Adds mom_live_tanks_count, dad_live_tanks_count, and runnable.
CREATE OR REPLACE VIEW public.v_cross_concepts_overview AS
WITH mom_counts AS (
  SELECT f.fish_code, COUNT(*)::int AS mom_live_tanks_count
  FROM public.fish f
  JOIN public.v_tanks vt ON vt.fish_id = f.id
  WHERE vt.status::text IN ('active','new_tank')
  GROUP BY f.fish_code
),
dad_counts AS (
  SELECT f.fish_code, COUNT(*)::int AS dad_live_tanks_count
  FROM public.fish f
  JOIN public.v_tanks vt ON vt.fish_id = f.id
  WHERE vt.status::text IN ('active','new_tank')
  GROUP BY f.fish_code
),
pc_counts AS (
  SELECT clutch_id, COUNT(*)::int AS planned_count
  FROM public.planned_crosses
  GROUP BY clutch_id
)
SELECT
  cp.id,                           -- uuid
  cp.clutch_code,                  -- text
  cp.planned_name,                 -- text
  cp.planned_nickname,             -- text
  cp.mom_code,                     -- text
  cp.dad_code,                     -- text
  cp.status,                       -- text (draft/ready/scheduled/closed)
  cp.created_at,                   -- timestamptz
  COALESCE(pc.planned_count, 0)               AS planned_count,          -- int
  COALESCE(mc.mom_live_tanks_count, 0)        AS mom_live_tanks_count,   -- int
  COALESCE(dc.dad_live_tanks_count, 0)        AS dad_live_tanks_count,   -- int
  (COALESCE(mc.mom_live_tanks_count,0) > 0
   AND COALESCE(dc.dad_live_tanks_count,0) > 0) AS runnable,             -- boolean
  cp.created_by                                 -- text (if present)
FROM public.clutch_plans cp
LEFT JOIN pc_counts  pc ON pc.clutch_id = cp.id
LEFT JOIN mom_counts mc ON mc.fish_code = cp.mom_code
LEFT JOIN dad_counts dc ON dc.fish_code = cp.dad_code
ORDER BY cp.created_at DESC NULLS LAST;

COMMIT;
