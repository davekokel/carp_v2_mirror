create extension if not exists pgcrypto;

create or replace function public.trg_fish_autotank()
returns trigger language plpgsql as $$
declare
  v_tank_id uuid := gen_random_uuid();
  v_tank_code text;
begin
  v_tank_code := 'TANK-' || NEW.fish_code || '-#1';

  insert into public.tanks(tank_id, tank_code, rack, position, created_at, created_by)
  values (v_tank_id, v_tank_code, null, null, now(), coalesce(NEW.created_by, 'system'))
  on conflict do nothing;

  insert into public.tank_status_history(tank_id, status, reason, changed_at)
  values (v_tank_id, 'new_tank', 'auto-create on fish import', now());

  insert into public.fish_tank_memberships(id, container_id, fish_id, created_at, created_by)
  values (gen_random_uuid(), v_tank_id, NEW.id, now(), coalesce(NEW.created_by, 'system'));

  return NEW;
end;
$$;

drop trigger if exists bi_fish_autotank on public.fish;
create trigger bi_fish_autotank
after insert on public.fish
for each row execute function public.trg_fish_autotank();
