-- Purge views (no deps, unused in active code)
drop view if exists public.seed_batches RESTRICT;
drop view if exists public.v_clutch_instance_treatments_effective RESTRICT;
drop view if exists public.v_clutches_overview_final_enriched RESTRICT;
drop view if exists public.v_crosses_status RESTRICT;
drop view if exists public.v_fish_living_tank_counts RESTRICT;
drop view if exists public.v_fish_overview_canonical RESTRICT;
drop view if exists public.v_fish_overview_human RESTRICT;
drop view if exists public.v_fish_standard RESTRICT;
drop view if exists public.v_overview_crosses RESTRICT;
drop view if exists public.v_plasmids RESTRICT;

-- Purge tables (no fks, no deps, unused in active code)
drop table if exists public._applied_sql_files RESTRICT;
drop table if exists public.fish_code_audit RESTRICT;
