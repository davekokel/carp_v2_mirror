BEGIN;
CREATE OR REPLACE VIEW public.v_tanks
(tank_uuid, tank_code, status, created_at, joined_at, left_at, fish_code, fish_uuid, is_active) AS
SELECT
  t.tank_uuid::uuid,
  t.tank_code::text,
  t.status::text,
  t.created_at::timestamptz,
  m.joined_at::timestamptz,
  m.left_at::timestamptz,
  f.fish_code::text,
  f.fish_uuid::uuid,
  (m.left_at IS NULL)
FROM public.fish_tank_memberships m
JOIN public.tanks t ON t.tank_uuid = m.tank_uuid AND t.status = 'active'
JOIN public.fish  f ON f.fish_uuid = m.fish_uuid
WHERE m.left_at IS NULL;
COMMIT;
