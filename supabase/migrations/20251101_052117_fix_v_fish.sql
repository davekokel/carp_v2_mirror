-- Fix v_fish: correct alias to use fish table (f), not t
CREATE OR REPLACE VIEW public.v_fish AS
SELECT
  f.id::uuid                  AS fish_uuid,
  COALESCE(f.fish_code,'')    AS fish_code,
  COALESCE(f.created_at, now()) AS created_at
FROM public.fish f;
