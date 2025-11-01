-- Recreate v_tanks with only columns guaranteed by the baseline.
-- No references to non-existent fields like fish_code.

DROP VIEW IF EXISTS public.v_tanks;

CREATE OR REPLACE VIEW public.v_tanks AS
SELECT
  t.id::uuid           AS tank_uuid,
  t.tank_code::text    AS tank_code,
  t.created_at
FROM public.tanks t;

COMMENT ON VIEW public.v_tanks IS
'Minimal tanks view: (tank_uuid, tank_code, created_at) — matches baseline schema.';
