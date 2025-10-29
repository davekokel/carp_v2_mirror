-- Finalize: use v_tanks (by fish_code, status='active') for counts
CREATE OR REPLACE VIEW public.v_fish_current_tank_counts AS
SELECT
  f.fish_uuid,
  COALESCE((
    SELECT COUNT(*) FROM public.v_tanks t
    WHERE t.status = 'active'
      AND t.fish_code = f.fish_code
  ), 0)::int AS current_tanks
FROM public.fish f;
