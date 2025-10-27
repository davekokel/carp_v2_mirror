-- Drop legacy alias/vanity views (no business logic lives here)
drop view if exists public.vw_bruker_mounts_enriched cascade;
drop view if exists public.vw_clutches_concept_overview cascade;
drop view if exists public.vw_clutches_overview_human cascade;
drop view if exists public.vw_cross_runs_overview cascade;
drop view if exists public.vw_crosses_concept cascade;
drop view if exists public.vw_fish_overview_with_label cascade;
drop view if exists public.vw_fish_standard cascade;
drop view if exists public.vw_label_rows cascade;
drop view if exists public.vw_planned_clutches_overview cascade;
drop view if exists public.vw_plasmids_overview cascade;
