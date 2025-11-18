BEGIN;

CREATE OR REPLACE VIEW public.v_tanks_overview AS
SELECT
  t.id,
  t.tank_code,
  NULL::text                   AS fish_code,
  COALESCE(t.status, '')::text AS status,
  t.created_at
FROM public.tanks t;

COMMIT;
