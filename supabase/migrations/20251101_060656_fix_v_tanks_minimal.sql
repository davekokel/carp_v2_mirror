-- Fix minimal v_tanks to use tank_code from public.tanks
DROP VIEW IF EXISTS public.v_tanks CASCADE;

CREATE VIEW public.v_tanks AS
SELECT
  t.id::uuid        AS tank_uuid,
  t.tank_code::text AS tank_code,
  t.created_at
FROM public.tanks t;

COMMENT ON VIEW public.v_tanks IS
'Minimal tanks view: tank_uuid, tank_code, created_at.';
