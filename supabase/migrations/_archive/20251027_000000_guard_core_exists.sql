-- 20251027_000000_guard_core_exists.sql
-- Make sure core tables/views exist before remodel/view rebuilds.

-- core tables (no-op if already there)
create table if not exists public.fish (dummy int);
create table if not exists public.tanks (dummy int);
create table if not exists public.fish_tank_memberships (dummy int);
create table if not exists public.cross_instances (dummy int);
create table if not exists public.clutch_instance_treatments (dummy int);

-- ensure key placeholder views so later DROP/CREATEs don't fail
create or replace view public.v_clutch_instances_display as
select 1 as dummy where false;
create or replace view public.v_tanks as select 1 as dummy where false;
create or replace view public.v_tank_pairs as select 1 as dummy where false;
create or replace view public.v_cross_clutch_instances as select 1 as dummy where false;
create or replace view public.v_fish_rich as select 1 as dummy where false;
