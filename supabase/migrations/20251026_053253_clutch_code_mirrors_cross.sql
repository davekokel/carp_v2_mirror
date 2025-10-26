begin;

drop trigger if exists trg_clutch_instances_set_code on public.clutch_instances;
drop function if exists public.gen_clutch_instance_code();

create function public.gen_clutch_instance_code()
returns trigger
language plpgsql
as $$
declare
  _tp  text;
  _seq int;
begin
  if coalesce(new.tank_pair_code,'') = '' then
    raise exception 'tank_pair_code required for clutch code';
  end if;

  if coalesce(new.clutch_instance_code,'') <> '' then
    return new;
  end if;

  select ci.tank_pair_code,
         (regexp_match(ci.cross_run_code, '\((\d+)\)$'))[1]::int
    into _tp, _seq
  from public.cross_instances ci
  where ci.id = new.cross_instance_id;

  if _tp is null or _seq is null then
    raise exception 'linked cross not found or cross_run_code missing';
  end if;

  new.clutch_instance_code := format('CL(%s)(%s)', _tp, lpad(_seq::text, 2, '0'));
  return new;
end$$;

create trigger trg_clutch_instances_set_code
before insert on public.clutch_instances
for each row
execute function public.gen_clutch_instance_code();

with x as (
  select cl.id,
         ci.tank_pair_code as tp,
         (regexp_match(ci.cross_run_code, '\((\d+)\)$'))[1]::int as seq
  from public.clutch_instances cl
  join public.cross_instances ci on ci.id = cl.cross_instance_id
)
update public.clutch_instances cl
   set clutch_instance_code = format('CL(%s)(%s)', x.tp, lpad(x.seq::text, 2, '0'))
 from x
 where x.id = cl.id;

create unique index if not exists ux_clutch_instance_code
  on public.clutch_instances(clutch_instance_code);

commit;
