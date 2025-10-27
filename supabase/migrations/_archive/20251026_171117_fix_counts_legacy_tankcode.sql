BEGIN;

CREATE INDEX IF NOT EXISTS idx_tanks_tank_code_like ON public.tanks (tank_code text_pattern_ops);

DROP VIEW IF EXISTS public.v_fish_current_tank_counts;
CREATE VIEW public.v_fish_current_tank_counts AS
SELECT
  f.fish_uuid,
  COALESCE((
    SELECT COUNT(*) FROM public.tanks t
    WHERE t.status = 'active'
      AND t.tank_code LIKE ('TANK(' || f.fish_code || ')#%')
  ), 0)::int AS current_tanks
FROM public.fish f;

COMMIT;
