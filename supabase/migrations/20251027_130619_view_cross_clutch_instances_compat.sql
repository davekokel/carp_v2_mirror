drop view if exists public.cross_clutch_instances;
create view public.cross_clutch_instances as
select * from public.v_cross_clutch_instances;
