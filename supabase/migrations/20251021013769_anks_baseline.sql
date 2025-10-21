begin;

create extension if not exists pgcrypto;

do $$
begin
  if not exists (select 1 from pg_type t join pg_namespace n on n.oid=t.typnamespace where t.typname='tank_status' and n.nspname='public') then
    create type public.tank_status as enum ('new_tank','active','quarantined','retired','cleaning','broken','decommissioned');
  end if;
end$$;

create table if not exists public.tanks (
  id uuid primary key default gen_random_uuid(),
  fish_id uuid not null references public.fish(id) on delete cascade,
  tank_code text unique,
  status public.tank_status not null default 'new_tank',
  capacity integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz
);

create table if not exists public.tank_assignments (
  id uuid primary key default gen_random_uuid(),
  tank_id uuid not null references public.tanks(id) on delete cascade,
  fish_id uuid not null references public.fish(id) on delete cascade,
  assigned_at timestamptz not null default now(),
  released_at timestamptz,
  status_at_assignment public.tank_status
);

create or replace function public.fn_fish_autocreate_tank() returns trigger
language plpgsql as $$
begin
  if not exists (select 1 from public.tanks where fish_id = new.id) then
    insert into public.tanks (fish_id, status) values (new.id, 'new_tank');
  end if;
  return new;
end$$;

do $$
begin
  if not exists (select 1 from pg_trigger where tgname='trg_fish_autocreate_tank') then
    create trigger trg_fish_autocreate_tank
      after insert on public.fish
      for each row
      execute function public.fn_fish_autocreate_tank();
  end if;
end$$;

commit;
