-- Purge unused legacy vw_* views (no dependents)
drop view if exists public.vw_bruker_mounts_enriched RESTRICT;
drop view if exists public.vw_clutches_concept_overview RESTRICT;
drop view if exists public.vw_clutches_overview_human RESTRICT;
drop view if exists public.vw_cross_runs_overview RESTRICT;
drop view if exists public.vw_crosses_concept RESTRICT;
drop view if exists public.vw_label_rows RESTRICT;
drop view if exists public.vw_planned_clutches_overview RESTRICT;
