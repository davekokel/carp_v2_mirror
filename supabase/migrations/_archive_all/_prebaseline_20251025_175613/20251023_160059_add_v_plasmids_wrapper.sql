-- Canonicalize: expose v_plasmids while vw_plasmids_overview still exists.
-- Keep column order as in vw_plasmids_overview.

CREATE OR REPLACE VIEW public.v_plasmids AS
SELECT * FROM public.vw_plasmids_overview;
