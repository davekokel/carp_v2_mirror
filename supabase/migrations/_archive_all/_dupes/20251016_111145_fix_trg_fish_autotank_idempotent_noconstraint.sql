begin;

create or replace function public.trg_fish_autotank()
returns trigger
language plpgsql
as $$
declare
  v_label text := coalesce(NEW.nickname, NEW.name, 'Holding Tank');
  v_container_id uuid;
  has_ended_at boolean;
  already_open boolean := false;
begin
  -- create holding tank and capture its id
  insert into public.containers (container_type, status, label, created_by)
  values ('holding_tank', 'new_tank', v_label, coalesce(NEW.created_by, 'system'))
  returning id into v_container_id;

  -- detect whether fish_tank_memberships has 'ended_at'
  select exists (
    select 1 from information_schema.columns  where table_schema='public' and table_name='fish_tank_memberships' and column_name='ended_at'
  ) into has_ended_at;

  -- is there an 'open' membership already?
  if has_ended_at then
    select exists (
      select 1 from public.fish_tank_memberships  where fish_id = NEW.id and ended_at is null
    ) into already_open;
  else
    -- no 'ended_at' column -> treat any row for this fish as 'open'
    select exists (
      select 1 from public.fish_tank_memberships  where fish_id = NEW.id
    ) into already_open;
  end if;

  if not already_open then
    begin
      insert into public.fish_tank_memberships (fish_id, container_id, started_at)
      values (NEW.id, v_container_id, now());
    exception when undefined_column then
      insert into public.fish_tank_memberships (fish_id, container_id, joined_at)
      values (NEW.id, v_container_id, now());
    end;
  end if;

  return NEW;
end $$;

-- reattach trigger
drop trigger if exists bi_fish_autotank on public.fish;
create trigger bi_fish_autotank
after insert on public.fish
for each row execute function public.trg_fish_autotank();

commit;
