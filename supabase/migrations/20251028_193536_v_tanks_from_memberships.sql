-- v_tanks built from tanks + open memberships + fish (idempotent)
CREATE OR REPLACE VIEW public.v_tanks AS
SELECT
  t.tank_uuid::uuid         AS tank_uuid,
  t.tank_code::text         AS tank_code,
  t.status::text            AS status,
  t.created_at::timestamptz AS created_at,
  m.joined_at::timestamptz  AS joined_at,
  f.fish_uuid::uuid         AS fish_uuid,
  f.fish_code::text         AS fish_code
FROM public.tanks t
LEFT JOIN public.fish_tank_memberships m
  ON m.tank_uuid = t.tank_uuid
 AND m.left_at IS NULL                    -- only open memberships
LEFT JOIN public.fish f
  ON f.fish_uuid = m.fish_uuid
WHERE t.status = 'active';
