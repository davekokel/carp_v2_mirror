begin;
create table if not exists public.bruker_mount (
  id uuid primary key default gen_random_uuid(),
  clutch_instance_id uuid not null references public.clutch_instances(id) on delete cascade,
  mount_code text not null,
  time_mounted timestamptz not null default now(),
  mounting_orientation text not null,
  n_top int not null default 0,
  n_bottom int not null default 0
);
create index if not exists ix_bruker_mount_ci_time on public.bruker_mount (clutch_instance_id, time_mounted desc);
commit;
