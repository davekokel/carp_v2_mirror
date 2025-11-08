BEGIN;

-- Drop old definition so we can change column list/order
DROP VIEW IF EXISTS public.v_tanks;

-- Recreate v_tanks using actual table columns; derive fish_code/tank_num from tank_code = 'TANK(<fish_code>)#<n>'
CREATE VIEW public.v_tanks AS
SELECT
  t.id::uuid                   AS tank_uuid,
  t.tank_code                  AS tank_code,
  COALESCE(l.code, ''::text)   AS location_code,
  COALESCE(
    NULLIF(regexp_replace(t.tank_code, '^.*\(([^)]+)\).*$', '\1'), ''),
    ''::text
  )                            AS fish_code,
  NULLIF(regexp_replace(t.tank_code, '^.*#([0-9]+).*$', '\1'), '')::int
                               AS tank_num,
  COALESCE(t.status, 'active') AS status,
  t.created_at                 AS created_at
FROM public.tanks AS t
LEFT JOIN public.locations AS l
  ON l.id = t.location_id;

COMMIT;
