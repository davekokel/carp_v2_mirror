BEGIN;

CREATE OR REPLACE VIEW public.v_tanks_overview AS
SELECT
  t.id::text         AS tank_id,
  t.tank_code::text  AS tank_code,
  t.status::text     AS status,
  t.created_at,
  /* Extract fish_code from tank_code pattern: "(ABC123)" */
  regexp_replace(t.tank_code, '^.*\\(([^)]+)\\).*$', '\\1') AS fish_code
FROM public.tanks t
ORDER BY t.created_at, t.tank_code;

COMMIT;
