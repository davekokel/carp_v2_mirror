-- Purge unused v_* views (all flagged no_dependents in inventory)
-- Conservative set: containers + clutch_counts + label_* only

drop view if exists public.v_clutch_counts RESTRICT;

drop view if exists public.v_containers RESTRICT;
drop view if exists public.v_containers_candidates RESTRICT;
drop view if exists public.v_containers_crossing_candidates RESTRICT;
drop view if exists public.v_containers_live RESTRICT;
drop view if exists public.v_containers_overview RESTRICT;

drop view if exists public.v_label_rows RESTRICT;
drop view if exists public.v_labels_recent RESTRICT;
