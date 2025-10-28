BEGIN;

-- Preserve legacy shape; append fish_uuid after fish_code.
-- Final order: tank_uuid, tank_code, status, created_at, fish_code, fish_uuid, started_at, ended_at, is_active
CREATE OR REPLACE VIEW public.v_tanks
(tank_uuid, tank_code, status, created_at, fish_code, fish_uuid, started_at, ended_at, is_active) AS
SELECT
  t.tank_uuid,
  t.tank_code,
  CASE WHEN m.ended_at IS NULL THEN 'active'::text ELSE 'ended'::text END AS status,
  COALESCE(t.created_at, m.started_at) AS created_at,
  f.fish_code,
  m.fish_uuid,
  m.started_at,
  m.ended_at,
  (m.ended_at IS NULL) AS is_active
FROM public.fish_tank_memberships m
JOIN public.tanks t ON t.tank_uuid = m.tank_uuid
JOIN public.fish  f ON f.fish_uuid  = m.fish_uuid;

COMMIT;