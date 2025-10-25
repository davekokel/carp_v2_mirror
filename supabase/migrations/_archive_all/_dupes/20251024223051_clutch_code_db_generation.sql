begin;

-- Per-year counter
create table if not exists public.clutch_code_counters (
  yy smallint primary key,
  next_serial integer not null default 1
);

-- Helper: left-pad to 3
create or replace function public._lpad3(i int) returns text
language sql immutable as $$ select lpad(i::text, 3, '0') $$;

-- Get the next CL-YY-NNN atomically for current year
create or replace function public.next_clutch_code() returns text
language plpgsql volatile as $$
declare
  v_yy smallint := extract(year from now())::int % 100;
  v_serial integer;
begin
  -- atomic UPSERT per year; the UPDATE returns new next_serial
  with up as (
    insert into public.clutch_code_counters(yy, next_serial)
    values (v_yy, 2)                              -- first issued will be 1 (returned below)
    on conflict (yy)
    do update set next_serial = public.clutch_code_counters.next_serial + 1
    returning next_serial
  )
  select next_serial - 1 into v_serial from up;   -- issue the previous value

  return 'CL-' || to_char(v_yy, 'FM00') || '-' || public._lpad3(v_serial);
end
$$;

-- Trigger: fill clutch_code when null
create or replace function public.trg_clutches_set_code()
returns trigger
language plpgsql as $$
begin
  if new.clutch_code is null or new.clutch_code = '' then
    new.clutch_code := public.next_clutch_code();
  end if;
  return new;
end
$$;

drop trigger if exists trg_clutches_set_code on public.clutches;
create trigger trg_clutches_set_code
before insert on public.clutches
for each row execute function public.trg_clutches_set_code();

-- Enforce uniqueness + format
do $$ begin
  if not exists (
    select 1 from pg_indexes where schemaname='public' and indexname='uq_clutches_clutch_code'
  ) then
    execute 'create unique index uq_clutches_clutch_code on public.clutches (clutch_code)';
  end if;
end $$;

alter table public.clutches
  drop constraint if exists clutch_code_format_chk;
alter table public.clutches
  add constraint clutch_code_format_chk
  check (clutch_code ~ '^CL-[0-9]{2}-[0-9]{3}$');

commit;
