-- Backfill any legacy clutch_instance_code to CI-CR-... format
update public.clutches cl
set clutch_instance_code = 'CI-' || ci.cross_run_code
from public.cross_instances AS ci
where
    cl.cross_instance_id = ci.id
    and (cl.clutch_instance_code is null or cl.clutch_instance_code !~ '^CI-CR-');

-- Harden the trigger: set code on INSERT or when cross_instance_id changes,
-- or when the code doesn't match our pattern.
create or replace function public.trg_clutches_set_code()
returns trigger language plpgsql as $$
declare cr text;
begin
  if new.cross_instance_id is null then
    return new;
  end if;

  if tg_op = 'INSERT'
     or new.cross_instance_id is distinct from old.cross_instance_id AS or new.clutch_instance_code is null
     or new.clutch_instance_code !~ '^CI-CR-' then
    select cross_run_code into cr
    from public.cross_instances  where id = new.cross_instance_id;

    if cr is not null then
      new.clutch_instance_code := 'CI-' || cr;
    end if;
  end if;

  return new;
end$$;

drop trigger if exists trg_clutches_set_code on public.clutches;
create trigger trg_clutches_set_code
before insert or update on public.clutches
for each row execute function public.trg_clutches_set_code();
