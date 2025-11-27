BEGIN;

DROP VIEW IF EXISTS public.v_tanks_overview;

CREATE VIEW public.v_tanks_overview AS
SELECT
  t.id::text       AS tank_id,
  t.tank_code,
  fi.fish_code,
  t.status,
  t.created_at
FROM public.tanks t
LEFT JOIN public.fish_instances_v10 fi
  ON fi.id = t.fish_instance_id
ORDER BY t.created_at DESC, t.tank_code;

COMMIT;
