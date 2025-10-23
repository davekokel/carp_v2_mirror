BEGIN;

ALTER VIEW public.vw_fish_overview_with_label RENAME TO v_fish_overview_with_label;
CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS SELECT * FROM public.v_fish_overview_with_label;

ALTER VIEW public.vw_fish_standard RENAME TO v_fish_standard;
CREATE OR REPLACE VIEW public.vw_fish_standard AS SELECT * FROM public.v_fish_standard;

ALTER VIEW public.vw_plasmids_overview RENAME TO v_plasmids_overview;
CREATE OR REPLACE VIEW public.vw_plasmids_overview AS SELECT * FROM public.v_plasmids_overview;

COMMIT;
