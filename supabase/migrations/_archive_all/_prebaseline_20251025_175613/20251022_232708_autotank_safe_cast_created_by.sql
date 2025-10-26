-- Hotfix: make bi_fish_autotank robust when NEW.created_by is text.
-- Attempts uuid cast; if invalid, uses NULL. Idempotent.

create or replace function public.trg_fish_autotank()
returns trigger
language plpgsql
as $$
declare
  v_tank_id   uuid := gen_random_uuid();
  v_tank_code text;
  v_creator   uuid;
begin
  -- try to cast whatever NEW.created_by is to uuid, else null
  begin
    v_creator := nullif(NEW.created_by::text, '')::uuid;
  exception when others then
    v_creator := null;
  end;

  v_tank_code := 'TANK-' || NEW.fish_code || '-#1';

  insert into public.tanks (tank_id, tank_code, rack, position, created_at, created_by)
  values (v_tank_id, v_tank_code, null, null, now(), v_creator)
  on conflict do nothing;

  insert into public.tank_status_history (tank_id, status, reason, changed_at, created_by)
  values (v_tank_id, 'new_tank', 'auto-create on fish import', now(), v_creator)
  on conflict do nothing;

  insert into public.fish_tank_memberships (id, container_id, fish_id, created_at, created_by)
  values (gen_random_uuid(), v_tank_id, NEW.id, now(), v_creator)
  on conflict do nothing;

  return NEW;
end;
$$;

drop trigger if exists bi_fish_autotank on public.fish;
create trigger bi_fish_autotank
  after insert on public.fish
  for each row
  execute function public.trg_fish_autotank();
