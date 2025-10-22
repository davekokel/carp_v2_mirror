-- Auto-generate public.fish.fish_code as FSH-YYNNNN (YY=year%100, NNNN=per-year counter)
-- Also safe to re-run (creates helpers if missing).

create extension if not exists pgcrypto;

-- Per-year counter table (recreated if it was purged)
create table if not exists public.fish_year_counters (
  yr          smallint primary key,
  next_serial integer      not null default 0,
  updated_at  timestamptz  not null default now()
);

-- Helper: get next serial for a given 2-digit year (atomic upsert+increment)
create or replace function public.next_fish_serial(p_year smallint)
returns integer
language plpgsql
as $$
declare
  v_next integer;
begin
  loop
    update public.fish_year_counters
       set next_serial = next_serial + 1,
           updated_at  = now()
     where yr = p_year
     returning next_serial into v_next;
    if found then
      return v_next;
    end if;

    begin
      insert into public.fish_year_counters(yr, next_serial) values (p_year, 1);
      return 1;
    exception when unique_violation then
      -- someone else just inserted; retry the UPDATE
      null;
    end;
  end loop;
end;
$$;

-- Ensure fish_code is unique
do $$
begin
  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and indexname='ux_fish_fish_code'
  ) then
    create unique index ux_fish_fish_code on public.fish (fish_code);
  end if;
end $$;

-- BEFORE INSERT trigger to fill NEW.fish_code if missing
create or replace function public.trg_fish_autocode()
returns trigger
language plpgsql
as $$
declare
  yy  smallint;
  seq integer;
begin
  if new.fish_code is null or new.fish_code = '' then
    yy := coalesce(extract(year from new.date_birth)::int, extract(year from now())::int) % 100;
    seq := public.next_fish_serial(yy);
    new.fish_code := 'FSH-' || lpad(yy::text, 2, '0') || lpad(seq::text, 4, '0');
  end if;
  return new;
end;
$$;

drop trigger if exists bi_fish_autocode on public.fish;
create trigger bi_fish_autocode
  before insert on public.fish
  for each row
  execute function public.trg_fish_autocode();
