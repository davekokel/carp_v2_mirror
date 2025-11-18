BEGIN;

CREATE OR REPLACE VIEW public.v_tanks_overview AS
SELECT
  t.id,
  t.tank_code,
  fi.fish_code,
  COALESCE(t.status, '')::text AS status,
  t.created_at
FROM public.tanks t
LEFT JOIN public.tank_memberships tm
       ON tm.tank_id = t.id
      AND tm.ended_at IS NULL
LEFT JOIN public.fish_instance fi
       ON fi.id = tm.fish_id;

COMMIT;
