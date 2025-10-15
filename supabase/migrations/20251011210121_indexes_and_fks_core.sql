-- indexes first (safe)
create index if not exists ix_cross_instances_cross_id   on public.cross_instances(cross_id);
create index if not exists ix_cross_instances_mother_id  on public.cross_instances(mother_tank_id);
create index if not exists ix_cross_instances_father_id  on public.cross_instances(father_tank_id);

create index if not exists ix_ftm_fish        on public.fish_tank_memberships(fish_id);
create index if not exists ix_ftm_container   on public.fish_tank_memberships(container_id);
create index if not exists ix_ftm_left_null   on public.fish_tank_memberships(left_at);

-- add FKs as NOT VALID so we don't break if there are orphans
DO $$
BEGIN
  if not exists (select 1 from pg_constraint where conname='fk_ci_cross') then
    alter table public.cross_instances
      add constraint fk_ci_cross foreign key (cross_id) references public.crosses(id_uuid) NOT VALID;
  end if;

  if not exists (select 1 from pg_constraint where conname='fk_ci_mother_container') then
    alter table public.cross_instances
      add constraint fk_ci_mother_container foreign key (mother_tank_id) references public.containers(id_uuid) NOT VALID;
  end if;

  if not exists (select 1 from pg_constraint where conname='fk_ci_father_container') then
    alter table public.cross_instances
      add constraint fk_ci_father_container foreign key (father_tank_id) references public.containers(id_uuid) NOT VALID;
  end if;
end$$;
