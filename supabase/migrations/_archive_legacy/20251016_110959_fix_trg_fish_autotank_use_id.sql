begin;

-- Recreate the trigger function using id (not id_uuid)
create or replace function public.trg_fish_autotank()
returns trigger
language plpgsql
as $$
declare
  v_label text := coalesce(NEW.nickname, NEW.name, 'Holding Tank');
  v_container_id uuid;
begin
  -- Create a holding tank for the new fish and capture its id
  insert into public.containers (container_type, status, label, created_by)
  values ('holding_tank', 'new_tank', v_label, coalesce(NEW.created_by, 'system'))
  returning id into v_container_id;

  -- Link the fish to the new tank (handle old column names defensively)
  begin
    insert into public.fish_tank_memberships (fish_id, container_id, started_at)
    values (NEW.id, v_container_id, now());
  exception when undefined_column then
    insert into public.fish_tank_memberships (fish_id, container_id, joined_at)
    values (NEW.id, v_container_id, now());
  end;

  return NEW;
end $$;

-- Ensure the trigger is attached (no-op if already present)
drop trigger if exists bi_fish_autotank on public.fish;
create trigger bi_fish_autotank
after insert on public.fish
for each row execute function public.trg_fish_autotank();

commit;
