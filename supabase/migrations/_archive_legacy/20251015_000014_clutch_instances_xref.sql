alter table public.clutch_instances
  add column if not exists cross_instance_id uuid;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'fk_clutch_instances_cross_instance_id'
      and conrelid = 'public.clutch_instances'::regclass
  ) then
    alter table public.clutch_instances
      add constraint fk_clutch_instances_cross_instance_id
      foreign key (cross_instance_id) references public.cross_instances(id)
      on delete cascade;
  end if;
end$$;

create index if not exists ix_clutch_instances_cross_instance_id
  on public.clutch_instances(cross_instance_id);
