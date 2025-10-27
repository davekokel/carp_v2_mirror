BEGIN;

create or replace function public.fish_auto_tank()
returns trigger
language plpgsql
as $$
declare
  v_tank_uuid uuid;
begin
  if exists (select 1 from public.fish_tank_memberships m where m.fish_uuid = new.fish_uuid) then
    return new;
  end if;

  insert into public.tanks default values
  returning tank_uuid into v_tank_uuid;

  insert into public.fish_tank_memberships(fish_uuid, tank_uuid)
  values (new.fish_uuid, v_tank_uuid)
  on conflict do nothing;

  return new;
end
$$;

drop trigger if exists trg_fish_auto_tank on public.fish;
create trigger trg_fish_auto_tank
after insert on public.fish
for each row
execute function public.fish_auto_tank();

do $$
declare
  r record;
  v_tank_uuid uuid;
begin
  for r in
    select f.fish_uuid
    from public.fish f
    left join public.fish_tank_memberships m on m.fish_uuid = f.fish_uuid
    where m.fish_uuid is null
  loop
    insert into public.tanks default values
    returning tank_uuid into v_tank_uuid;

    insert into public.fish_tank_memberships(fish_uuid, tank_uuid)
    values (r.fish_uuid, v_tank_uuid)
    on conflict do nothing;
  end loop;
end
$$;

COMMIT;
