BEGIN;

CREATE OR REPLACE VIEW public.v_tanks_overview_join_fish_instance AS
SELECT *
FROM public.v_tanks_overview;

COMMIT;
