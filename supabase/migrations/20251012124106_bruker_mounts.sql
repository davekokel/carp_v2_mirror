create extension if not exists pgcrypto;

create table if not exists public.bruker_mounts (
  id               uuid primary key default gen_random_uuid(),
  selection_id     uuid not null references public.clutch_instances(id) on delete cascade,
  mount_date       date not null,
  mount_time       time not null,
  n_top            integer not null check (n_top >= 0),
  n_bottom         integer not null check (n_bottom >= 0),
  orientation      text not null check (orientation in ('dorsal','ventral','left','right','front','back','other')),
  created_at       timestamptz not null default now(),
  created_by       text
);

create index if not exists ix_bm_selection_id on public.bruker_mounts(selection_id);
create index if not exists ix_bm_mount_date on public.bruker_mounts(mount_date);

do $$
begin
  alter table public.bruker_mounts enable row level security;

  if not exists (
    select 1 from pg_policy where polrelid='public.bruker_mounts'::regclass and polname='app_rw_select_bm'
  ) then
    create policy app_rw_select_bm on public.bruker_mounts
      for select to app_rw using (true);
  end if;

  if not exists (
    select 1 from pg_policy where polrelid='public.bruker_mounts'::regclass and polname='app_rw_insert_bm'
  ) then
    create policy app_rw_insert_bm on public.bruker_mounts
      for insert to app_rw with check (true);
  end if;

  if not exists (
    select 1 from pg_policy where polrelid='public.bruker_mounts'::regclass and polname='app_rw_update_bm'
  ) then
    create policy app_rw_update_bm on public.bruker_mounts
      for update to app_rw using (true) with check (true);
  end if;
end$$;
