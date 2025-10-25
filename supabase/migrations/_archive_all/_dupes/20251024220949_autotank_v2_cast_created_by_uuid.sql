begin;

create or replace function public.fn_insert_autotank_v2()
returns trigger
language plpgsql
as $$
begin
  insert into public.tanks (tank_id, tank_code, fish_code, rack, position, created_at, created_by)
  values (
    gen_random_uuid(),
    'TANK-' || NEW.fish_code || '-#1',
    NEW.fish_code,
    null,
    null,
    now(),
    case
      when NEW.created_by is null or NEW.created_by = '' then null
      when NEW.created_by ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' then NEW.created_by::uuid
      else null
    end
  );
  return NEW;
end
$$;

drop trigger if exists trg_fish_autotank on public.fish;

create trigger trg_fish_autotank
  after insert on public.fish
  for each row
  execute function public.fn_insert_autotank_v2();

commit;

-- verify
select t.tgname, pg_get_triggerdef(t.oid)
from pg_trigger t
join pg_class c on c.oid=t.tgrelid
join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public' and c.relname='fish' and t.tgname='trg_fish_autotank';
