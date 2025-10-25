BEGIN;

CREATE OR REPLACE VIEW public.v_tanks
( tank_id, label, tank_code, status, tank_updated_at, tank_created_at, fish_code ) AS
WITH last_status AS (
  SELECT s.tank_id, s.status, s.changed_at,
         row_number() OVER (PARTITION BY s.tank_id ORDER BY s.changed_at DESC) rn
  FROM tank_status_history s
),
mem AS (
  SELECT m.tank_id, m.fish_code,
         row_number() OVER (PARTITION BY m.tank_id ORDER BY coalesce(m.updated_at, m.created_at) DESC) rn
  FROM tank_memberships m
),
asg AS (
  SELECT a.tank_id, a.fish_code,
         row_number() OVER (PARTITION BY a.tank_id ORDER BY coalesce(a.updated_at, a.created_at) DESC) rn
  FROM tank_assignments a
)
SELECT
  t.tank_id,
  t.tank_code AS label,
  t.tank_code AS tank_code,
  ls.status,
  ls.changed_at AS tank_updated_at,
  t.created_at AS tank_created_at,
  coalesce(m.fish_code, a.fish_code) AS fish_code
FROM tanks t
LEFT JOIN last_status ls ON ls.tank_id = t.tank_id AND ls.rn = 1
LEFT JOIN mem m ON m.tank_id = t.tank_id AND m.rn = 1
LEFT JOIN asg a ON a.tank_id = t.tank_id AND a.rn = 1;

COMMIT;
