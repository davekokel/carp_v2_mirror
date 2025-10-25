BEGIN;

-- Build the canonical body once
CREATE OR REPLACE VIEW public._v_tanks_canonical
( tank_id, label, tank_code, status, tank_updated_at, tank_created_at ) AS
WITH last_status AS (
  SELECT s.tank_id, s.status, s.changed_at,
         row_number() OVER (PARTITION BY s.tank_id ORDER BY s.changed_at DESC) rn
  FROM tank_status_history s
)
SELECT
  t.tank_id,
  t.tank_code AS label,
  t.tank_code AS tank_code,
  ls.status,
  ls.changed_at AS tank_updated_at,
  t.created_at AS tank_created_at
FROM tanks t
LEFT JOIN last_status ls
  ON ls.tank_id = t.tank_id AND ls.rn = 1;

DO $$
DECLARE
  deps int;
BEGIN
  SELECT count(*) INTO deps
  FROM information_schema.view_table_usage
  WHERE view_schema='public' AND table_name='v_tanks';

  IF deps = 0 THEN
    EXECUTE 'DROP VIEW IF EXISTS public.v_tanks';
    EXECUTE 'ALTER VIEW public._v_tanks_canonical RENAME TO v_tanks';
  ELSE
    RAISE EXCEPTION 'Cannot redefine v_tanks; still referenced by % dependent view(s). Update those dependents first.', deps;
  END IF;
END$$;

COMMIT;
