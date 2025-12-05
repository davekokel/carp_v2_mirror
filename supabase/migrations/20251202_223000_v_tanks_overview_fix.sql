BEGIN;

-- Drop the old view (no CASCADE; only UI relies on it)
DROP VIEW IF EXISTS public.v_tanks_overview;

CREATE VIEW public.v_tanks_overview AS
SELECT
  t.id::text                         AS tank_id,
  t.tank_code,
  COALESCE(t.status, '')             AS status,
  fi.fish_code                       AS fish_code,   -- FSH-… instance code
  fl.line_code                       AS line_code,   -- LINE-… line code
  t.created_at
FROM public.tanks t
LEFT JOIN public.fish_instances_v10 fi
  ON fi.id = t.fish_instance_id
LEFT JOIN public.fish_lines fl
  ON fl.id = fi.line_id
ORDER BY t.created_at DESC, t.tank_code;

COMMENT ON VIEW public.v_tanks_overview IS
'Tanks overview: one row per tank with canonical tank_code, status, FSH fish_code, line_code, created_at.';

COMMIT;
