begin;

create or replace function public.fn_next_tank_suffix(p_fish_id uuid)
returns int
language plpgsql
as $$
declare
  next_n int;
begin
  select coalesce(max(regexp_replace(tank_code, '.*-#', '')::int), 0) + 1
    into next_n
  from public.tanks
  where fish_id = p_fish_id;
  return next_n;
end
$$;

create or replace function public.fn_fish_autocreate_tank()
returns trigger
language plpgsql
as $$
declare
  _n int;
  _tank_code text;
begin
  _n := public.fn_next_tank_suffix(new.id);
  _tank_code := format('TANK-%s-#%s', new.fish_code, _n);

  if not exists (select 1 from public.tanks where tank_code = _tank_code) then
    insert into public.tanks (fish_id, tank_code, status)
    values (new.id, _tank_code, 'new_tank');
  end if;

  return new;
end
$$;

do $$
begin
  if exists (select 1 from pg_trigger where tgname='trg_fish_autocreate_tank') then
    drop trigger trg_fish_autocreate_tank on public.fish;
  end if;
  create trigger trg_fish_autocreate_tank
    after insert on public.fish
    for each row
    execute function public.fn_fish_autocreate_tank();
end$$;

commit;
