create table if not exists public.fish_year_counters (
  year int primary key,
  n int not null default 0
);

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
