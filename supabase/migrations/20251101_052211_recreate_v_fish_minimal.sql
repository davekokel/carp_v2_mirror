-- Recreate v_fish with a minimal, stable shape
-- (drop first so we aren't constrained by prior column names/order)
DROP VIEW IF EXISTS public.v_fish CASCADE;

CREATE VIEW public.v_fish AS
SELECT
  COALESCE(f.fish_code, '')::text AS fish_code,
  COALESCE(f.created_at, now())   AS created_at
FROM public.fish f;

COMMENT ON VIEW public.v_fish IS 'Minimal fish view: fish_code, created_at (from public.fish).';
