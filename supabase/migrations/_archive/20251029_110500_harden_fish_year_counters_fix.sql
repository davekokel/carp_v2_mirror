do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='fish_year_counters' and column_name='n'
  ) then
    alter table public.fish_year_counters add column n int not null default 0;
  end if;

  if not exists (
    select 1 from information_schema.table_constraints
    where table_schema='public' and table_name='fish_year_counters' and constraint_type='PRIMARY KEY'
  ) then
    begin
      alter table only public.fish_year_counters add primary key (year);
    exception when duplicate_object then
      null;
    end;
  end if;
end
$$;

insert into public.fish_year_counters(year, n)
select extract(year from now())::int, 0
on conflict (year) do nothing;

create or replace function public.fish_before_insert_code()
returns trigger
language plpgsql
security definer
as $$
declare
  y int := extract(year from coalesce(new.date_birth, now()))::int;
  seq int;
begin
  insert into public.fish_year_counters(year, n) values (y, 0)
  on conflict (year) do nothing;

  update public.fish_year_counters
     set n = n + 1
   where year = y
  returning n into seq;

  new.fish_code := make_fish_code_yy_seq36(clock_timestamp(), y, seq);
  return new;
end
$$;
