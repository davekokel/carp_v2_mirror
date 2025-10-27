BEGIN;
CREATE OR REPLACE VIEW public.v_fish_current_tank_counts AS
SELECT
  f.fish_uuid,
  COALESCE(COUNT(m.*),0)::int AS current_tanks
FROM public.fish f
LEFT JOIN public.fish_tank_memberships m
  ON m.fish_uuid = f.fish_uuid
GROUP BY f.fish_uuid;
COMMIT;
