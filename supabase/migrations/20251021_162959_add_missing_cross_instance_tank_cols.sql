begin;

-- Add tank linkage columns used by tank-centric migrations
alter table if exists public.cross_instances
  add column if not exists mother_tank_id uuid,
  add column if not exists father_tank_id uuid;

comment on column public.cross_instances.mother_tank_id is 'FK → containers.id (mom tank)';
comment on column public.cross_instances.father_tank_id is 'FK → containers.id (dad tank)';

commit;
