BEGIN;

CREATE OR REPLACE VIEW public.v_tanks AS
SELECT
  t.id::uuid AS tank_uuid,
  t.tank_code AS tank_code,
  regexp_replace(t.tank_code, '^.*\(([^)]+)\).*$', '\1')::text AS fish_code,
  NULLIF(regexp_replace(t.tank_code, '^.*#([0-9]+).*$', '\1'), '')::int AS tank_num,
  t.status::text AS status,
  t.created_at
FROM public.tanks t;

COMMIT;
