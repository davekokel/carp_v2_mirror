DROP VIEW IF EXISTS public.v_fish CASCADE;

CREATE VIEW public.v_fish AS
SELECT
  f.id::uuid        AS fish_uuid,
  f.fish_code::text AS fish_code,
  ''::text          AS tank_code,   -- placeholder (no dependency on memberships)
  f.created_at
FROM public.fish f;

COMMENT ON VIEW public.v_fish IS
'Minimal fish view: fish_uuid, fish_code, (no tank join yet), created_at.';
