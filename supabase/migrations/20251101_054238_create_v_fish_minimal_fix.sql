DROP VIEW IF EXISTS public.v_fish CASCADE;

CREATE VIEW public.v_fish AS
SELECT
  f.id::uuid               AS fish_uuid,
  f.fish_code::text        AS fish_code,
  COALESCE(t.tank_code,'') AS tank_code,
  f.created_at
FROM public.fish f
LEFT JOIN LATERAL (
  SELECT m.tank_id
  FROM public.fish_tank_memberships m
  WHERE m.fish_id = f.id
    AND (m.ended_at IS NULL OR m.ended_at > now())
  ORDER BY m.started_at DESC NULLS LAST
  LIMIT 1
) cur ON true
LEFT JOIN public.tanks t ON t.id = cur.tank_id;

COMMENT ON VIEW public.v_fish IS
'Minimal fish view: fish_uuid, fish_code, current tank_code (if any), created_at.';
