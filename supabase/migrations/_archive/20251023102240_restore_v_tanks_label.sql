BEGIN;

CREATE OR REPLACE VIEW public.v_tanks
( tank_id, label, tank_code, status, tank_updated_at, tank_created_at ) AS
WITH last_status AS (
  SELECT
    s.tank_id,
    s.status,
    s.changed_at,
    row_number() OVER (PARTITION BY s.tank_id ORDER BY s.changed_at DESC) AS rn
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

COMMIT;
