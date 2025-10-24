begin;
create or replace function public.fn_insert_autotank_v2()
returns trigger
language plpgsql
as $$
begin
  if not exists (select 1 from public.tanks where fish_code = NEW.fish_code) then
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
  end if;
  return NEW;
end
$$;
commit;
