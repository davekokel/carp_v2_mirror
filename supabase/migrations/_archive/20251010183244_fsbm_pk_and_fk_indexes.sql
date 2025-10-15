alter table public.fish_seed_batches_map add column if not exists id uuid default gen_random_uuid();

do $$
begin
  if not exists (
    select 1
    from pg_index i
    join pg_class c on c.oid=i.indrelid
    where c.relname='fish_seed_batches_map' and i.indisprimary
  ) then
    execute 'alter table public.fish_seed_batches_map add primary key (id)';
  end if;
end$$;

alter table public.fish_seed_batches_map
  add constraint if not exists uq_fsbm_natural unique (fish_id, seed_batch_id);

create index if not exists idx_clutch_containers_container_id on public.clutch_containers(container_id);
create index if not exists idx_clutch_containers_source_container_id on public.clutch_containers(source_container_id);
create index if not exists idx_clutch_plan_treatments_clutch_id on public.clutch_plan_treatments(clutch_id);
create index if not exists idx_clutches_cross_instance_id on public.clutches(cross_instance_id);
create index if not exists idx_containers_request_id on public.containers(request_id);
create index if not exists idx_cross_instances_cross_id on public.cross_instances(cross_id);
create index if not exists idx_cross_instances_father_tank_id on public.cross_instances(father_tank_id);
create index if not exists idx_cross_instances_mother_tank_id on public.cross_instances(mother_tank_id);
create index if not exists idx_cross_plan_genotype_alleles_base_allele on public.cross_plan_genotype_alleles(transgene_base_code, allele_number);
create index if not exists idx_cross_plan_runs_tank_a_id on public.cross_plan_runs(tank_a_id);
create index if not exists idx_cross_plan_runs_tank_b_id on public.cross_plan_runs(tank_b_id);
create index if not exists idx_fish_seed_batches_fish_id on public.fish_seed_batches(fish_id);
create index if not exists idx_fish_transgene_alleles_base_allele on public.fish_transgene_alleles(transgene_base_code, allele_number);
create index if not exists idx_planned_crosses_cross_id on public.planned_crosses(cross_id);
create index if not exists idx_planned_crosses_cross_instance_id on public.planned_crosses(cross_instance_id);
create index if not exists idx_planned_crosses_father_tank_id on public.planned_crosses(father_tank_id);
create index if not exists idx_planned_crosses_mother_tank_id on public.planned_crosses(mother_tank_id);
create index if not exists idx_tank_requests_fish_id on public.tank_requests(fish_id);
