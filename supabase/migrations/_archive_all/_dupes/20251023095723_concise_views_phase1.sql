BEGIN;

CREATE OR REPLACE VIEW public.v_fish AS SELECT * FROM public.v_fish_overview_final;
CREATE OR REPLACE VIEW public.v_tank_labels AS SELECT * FROM public.v_fish_overview_with_label_final;
CREATE OR REPLACE VIEW public.v_tanks AS SELECT * FROM public.v_tanks_current_status_enriched;
CREATE OR REPLACE VIEW public.v_tank_pairs AS SELECT * FROM public.v_tank_pairs_base;
CREATE OR REPLACE VIEW public.v_plasmids AS SELECT * FROM public.v_plasmids_overview_final;
CREATE OR REPLACE VIEW public.v_clutch_annotations AS SELECT * FROM public.v_clutch_annotations_summary_enriched;
CREATE OR REPLACE VIEW public.v_clutch_treatments AS SELECT * FROM public.v_clutch_treatments_summary_enriched;

COMMIT;
