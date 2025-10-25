begin;

create sequence if not exists public.clutch_b36_seq;

create or replace function public.next_clutch_code_b36()
returns text
language plpgsql
volatile
as $$
declare
  v bigint := nextval('public.clutch_b36_seq');
  b text;
begin
  b := public.to_base36(v);
  if length(b) < 5 then
    b := lpad(b, 5, '0');
  end if;
  return 'CL-' || b;
end
$$;

create or replace function public.trg_clutches_set_code()
returns trigger
language plpgsql
as $$
begin
  if new.clutch_code is null or new.clutch_code = '' then
    new.clutch_code := public.next_clutch_code_b36();
  end if;
  return new;
end
$$;

drop trigger if exists trg_clutches_set_code on public.clutches;
create trigger trg_clutches_set_code
before insert on public.clutches
for each row execute function public.trg_clutches_set_code();

do $$
begin
  if not exists (
    select 1 from pg_indexes where schemaname='public' and indexname='uq_clutches_clutch_code'
  ) then
    execute 'create unique index uq_clutches_clutch_code on public.clutches (clutch_code)';
  end if;
end
$$;

alter table public.clutches
  drop constraint if exists clutch_code_format_chk;

alter table public.clutches
  add constraint clutch_code_format_chk
  check (
    clutch_code ~ '^CL-[0-9A-Z]{5,}$'
    or clutch_code ~ '^CL-[0-9]{2}-?[0-9]{3}$'
  );

commit;
