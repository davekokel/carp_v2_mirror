begin;

-- 1) Add columns if missing
alter table public.bruker_mount
  add column if not exists clutch_instance_id uuid,
  add column if not exists time_mounted timestamptz;

-- 2) Backfill time_mounted from legacy date+time if present and time_mounted is null
update public.bruker_mount
set time_mounted = coalesce(
  time_mounted,
  coalesce(mount_date::timestamp, (now()::date)::timestamp)
  + coalesce((mount_time)::interval, interval '00:00')
)
where time_mounted is null
  and (mount_date is not null or mount_time is not null);

-- 3) Standardize column names (guarded blocks so it’s idempotent)
do $$ begin
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='bruker_mount' and column_name='mount_orientation'
  ) then
    execute 'alter table public.bruker_mount rename column mount_orientation to mounting_orientation';
  end if;
end $$;

do $$ begin
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='bruker_mount' and column_name='mount_top_n'
  ) then
    execute 'alter table public.bruker_mount rename column mount_top_n to n_top';
  end if;
end $$;

do $$ begin
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='bruker_mount' and column_name='mount_bottom_n'
  ) then
    execute 'alter table public.bruker_mount rename column mount_bottom_n to n_bottom';
  end if;
end $$;

-- 4) Useful defaults/index
alter table public.bruker_mount
  alter column time_mounted set default now();

create index if not exists ix_bruker_mount_ci_time
  on public.bruker_mount (clutch_instance_id, time_mounted desc);

commit;
