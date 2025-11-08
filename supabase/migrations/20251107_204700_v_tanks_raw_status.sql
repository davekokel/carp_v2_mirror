BEGIN;

-- Drop first so we can change the column list safely
DROP VIEW IF EXISTS public.v_tanks;

-- Recreate with raw status (no COALESCE), plus parsed fish_code and tank_num
CREATE VIEW public.v_tanks AS
SELECT
  t.id::uuid                                                  AS tank_uuid,
  t.tank_code                                                 AS tank_code,
  regexp_replace(t.tank_code, '^.*\(([^)]+)\).*$', '\1')::text         AS fish_code,
  NULLIF(regexp_replace(t.tank_code, '^.*#([0-9]+).*$', '\1'), '')::int AS tank_num,
  t.status::text                                              AS status,
  t.created_at
FROM public.tanks AS t;

COMMIT;
