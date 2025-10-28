BEGIN;
CREATE OR REPLACE VIEW public.v_tanks AS
SELECT
  t.tank_uuid::uuid          AS tank_uuid,
  t.tank_code::text          AS tank_code,
  t.status::text             AS status,
  t.created_at::timestamptz  AS created_at,
  m.joined_at::timestamptz   AS joined_at,
  m.left_at::timestamptz     AS left_at,
  f.fish_code::text          AS fish_code,
  f.fish_uuid::uuid          AS fish_uuid,
  (m.left_at IS NULL)        AS is_active
FROM public.fish_tank_memberships m
JOIN public.tanks t ON t.tank_uuid = m.tank_uuid AND t.status = 'active'
JOIN public.fish  f ON f.fish_uuid = m.fish_uuid
WHERE m.left_at IS NULL;
COMMIT;
