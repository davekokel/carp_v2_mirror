create or replace function public.trg_clutches_set_birthday()
returns trigger language plpgsql as $$
declare dt date;
begin
  if new.date_birth is not null then
    return new;
  end if;

  if new.cross_instance_id is null then
    return new;
  end if;

  select (ci.cross_date + interval '1 day')::date
  into dt
  from public.cross_instances AS ci
  where ci.id = new.cross_instance_id;

  if dt is not null then
    new.date_birth := dt;
  end if;

  return new;
end$$;

drop trigger if exists trg_clutches_set_birthday on public.clutches;
create trigger trg_clutches_set_birthday
before insert on public.clutches
for each row execute function public.trg_clutches_set_birthday();
