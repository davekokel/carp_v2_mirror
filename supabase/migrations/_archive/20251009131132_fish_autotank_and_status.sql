begin;

-- 1) Allow containers.status = new_tank (adjust CHECK constraint);

DO 28691  begin
  if exists (
    select 1 from pg_constraint
    where conname = containers_status_check and conrelid = public.containers::regclass
  ) then
    alter table public.containers drop constraint containers_status_check;
  end if;
end $$;
;
alter table public.containers
  add constraint containers_status_check
  check (status in (planned,new_tank,active,ready_to_kill,inactive));

-- 2) Trigger: when fish is inserted, auto-provision a holding tank (status=new_tank) and link it
create or replace function public.trg_fish_autotank() returns trigger language plpgsql as $$
declare
  v_container_id uuid;
  v_label text;
begin
  -- Only do this if there is no existing membership and no explicit container specified by the loader
  -- (we keep it simple: always create a fresh holding_tank for uploaded fish)
  v_label := case
              when new.fish_code is not null then format(TANK %s #1, new.fish_code)
              else null
            end;

  insert into public.containers (container_type, status, label, created_by)
  values (holding_tank, new_tank, v_label, coalesce(new.created_by, system))
  returning id_uuid into v_container_id;

  -- Link fish to the new container (handle schema differences for timestamp column name)
  begin
    insert into public.fish_tank_memberships (fish_id, container_id, started_at)
    values (new.id_uuid, v_container_id, now());
  exception when undefined_column then
    insert into public.fish_tank_memberships (fish_id, container_id, joined_at)
    values (new.id_uuid, v_container_id, now());
  end;

  return new;
end; $$;

drop trigger if exists trg_fish_autotank on public.fish;
create trigger trg_fish_autotank
after insert on public.fish
for each row execute function public.trg_fish_autotank();

-- 3) Trigger: when a container gains a human label, flip status new_tank -> active
create or replace function public.trg_containers_activate_on_label() returns trigger language plpgsql as $$
begin
  if (tg_op = UPDATE) and old.status = new_tank and new.label is not null and new.label is distinct from old.label then
    new.status := active;
    new.status_changed_at := now();
  end if;
  return new;
end; $$;

drop trigger if exists trg_containers_activate_on_label on public.containers;
create trigger trg_containers_activate_on_label
before update of label on public.containers
for each row execute function public.trg_containers_activate_on_label();

commit;
