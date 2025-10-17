BEGIN;

alter table public.crosses
  add column if not exists cross_name text;

update public.crosses
set cross_name = coalesce(cross_nickname, public.gen_cross_name(mother_code, father_code))
where coalesce(nullif(cross_name,''), '') = '';

create or replace function public.trg_crosses_set_names()
returns trigger
language plpgsql
as $$
begin
  new.cross_name := coalesce(new.cross_nickname, public.gen_cross_name(new.mother_code, new.father_code));
  return new;
end
$$;

drop trigger if exists crosses_set_names on public.crosses;
create trigger crosses_set_names
before insert or update of mother_code, father_code, cross_nickname
on public.crosses
for each row
execute function public.trg_crosses_set_names();

alter table public.crosses
  alter column cross_name set not null;

create or replace view public.v_overview_crosses as
with latest_planned as (
  select distinct on (cp.id)
         cp.id as clutch_id,
         cp.clutch_code,
         cp.status,
         pc.id as planned_id,
         pc.created_at as planned_created_at,
         pc.cross_id,
         pc.mother_tank_id,
         pc.father_tank_id
  from public.clutch_plans cp
  left join public.planned_crosses pc on pc.clutch_id = cp.id
  order by cp.id, pc.created_at desc nulls last
),
counts as (
  select clutch_id, count(*)::int as planned_count
  from public.planned_crosses
  group by clutch_id
)
select
  cp.clutch_code,
  coalesce(x.cross_name, cp.planned_name, '') as name,
  coalesce(cp.planned_nickname, x.cross_nickname, '') as nickname,
  lp.status::text as status,
  coalesce(ct.planned_count,0) as planned_count,
  x.mother_code as mom_code,
  x.father_code as dad_code,
  cm.tank_code as mom_code_tank,
  cf.tank_code as dad_code_tank,
  cp.created_at,
  (cm.tank_code is not null and cf.tank_code is not null) as runnable
from public.clutch_plans cp
left join latest_planned lp on lp.clutch_id = cp.id
left join counts ct on ct.clutch_id = cp.id
left join public.crosses x on x.id = lp.cross_id
left join public.containers cm on cm.id = lp.mother_tank_id
left join public.containers cf on cf.id = lp.father_tank_id;

COMMIT;
