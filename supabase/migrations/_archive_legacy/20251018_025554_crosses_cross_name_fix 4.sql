-- Add cross_name if missing
alter table public.crosses
add column if not exists cross_name text;

-- Recreate a resilient filler trigger that doesn't assume other columns exist
create or replace function public.trg_cross_name_fill() returns trigger
language plpgsql as $$
declare
  v_name text;
begin
  -- Prefer an explicit name if provided
  if NEW.cross_name is not null and btrim(NEW.cross_name) <> '' then
    return NEW;
  end if;

  -- Try cross_name_code (if table has it)
  begin
    execute 'select ($1).cross_name_code::text' into v_name using NEW;
  exception when undefined_column then
    v_name := null;
  end;

  if v_name is null or btrim(v_name) = '' then
    -- Try cross_code
    begin
      execute 'select ($1).cross_code::text' into v_name using NEW;
    exception when undefined_column then
      v_name := null;
    end;
  end if;

  if v_name is null or btrim(v_name) = '' then
    -- Try mother_code × father_code
    declare
      v_m text; v_d text;
    begin
      begin execute 'select ($1).mother_code::text' into v_m using NEW; exception when undefined_column then v_m := null; end;
      begin execute 'select ($1).father_code::text' into v_d using NEW; exception when undefined_column then v_d := null; end;
      if v_m is not null and v_d is not null then
        v_name := v_m || '×' || v_d;
      end if;
    end;
  end if;

  NEW.cross_name := coalesce(v_name, NEW.cross_name, '');
  return NEW;
end$$;

drop trigger if exists trg_cross_name_fill on public.crosses;
create trigger trg_cross_name_fill
before insert or update on public.crosses
for each row execute function public.trg_cross_name_fill();
