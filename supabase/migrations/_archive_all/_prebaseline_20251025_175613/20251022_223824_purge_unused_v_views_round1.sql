-- Purge unused v_* views (no code references; DB marked no_dependents)
drop view if exists public.v_bruker_mounts_enriched RESTRICT;
drop view if exists public.v_clutch_expected_genotype RESTRICT;
drop view if exists public.v_clutch_instance_selections RESTRICT;
drop view if exists public.v_clutch_instances_annotations RESTRICT;
drop view if exists public.v_clutch_instances_overview RESTRICT;
drop view if exists public.v_clutches_overview_effective RESTRICT;
drop view if exists public.v_cross_plan_runs_enriched RESTRICT;
drop view if exists public.v_cross_plans_enriched RESTRICT;
drop view if exists public.v_label_jobs_recent RESTRICT;
drop view if exists public.v_tank_pairs_overview RESTRICT;
