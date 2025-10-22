-- Replace bi_fish_autotank with UUID-strict logic (no text fallback).

create or replace function public.trg_fish_autotank()
returns trigger
language plpgsql
as $$
declare
  v_tank_id   uuid := gen_random_uuid();
  v_tank_code text;
begin
  -- Derive tank_code from fish_code
  v_tank_code := 'TANK-' || NEW.fish_code || '-#1';

  -- Insert tank with created_by strictly uuid or null
  insert into public.tanks (tank_id, tank_code, rack, position, created_at, created_by)
  values (v_tank_id, v_tank_code, null, null, now(), NEW.created_by)
  on conflict do nothing;

  -- Status history (uuid only)
  insert into public.tank_status_history (tank_id, status, reason, changed_at, created_by)
  values (v_tank_id, 'new_tank', 'auto-create on fish import', now(), NEW.created_by)
  on conflict do nothing;

  -- Membership link
  insert into public.fish_tank_memberships (id, container_id, fish_id, created_at, created_by)
  values (gen_random_uuid(), v_tank_id, NEW.id, now(), NEW.created_by)
  on conflict do nothing;

  return NEW;
end;
$$;

drop trigger if exists bi_fish_autotank on public.fish;
create trigger bi_fish_autotank
  after insert on public.fish
  for each row
  execute function public.trg_fish_autotank();
