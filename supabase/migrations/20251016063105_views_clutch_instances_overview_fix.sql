begin;

create or replace view public.v_clutch_instances_overview as
with sel as (
  select
    cl.cross_instance_id,
    max(cl.annotated_at)::date as day_annotated,
    string_agg(
      trim(concat_ws(' ',
        case when coalesce(cl.red_intensity,'')   <> '' then 'red='   || cl.red_intensity   end,
        case when coalesce(cl.green_intensity,'') <> '' then 'green=' || cl.green_intensity end,
        case when coalesce(cl.notes,'')           <> '' then 'note='  || cl.notes          end
      )),
      ' | ' order by cl.created_at
    ) as annotations_rollup,
    max(cl.birthday)::date  as birthday_ci,
    max(cl.clutch_code)     as clutch_code_ci
  from public.clutch_instances cl
  group by cl.cross_instance_id
)
select
  coalesce(sel.clutch_code_ci, cp.clutch_code, pc.clutch_code) as clutch_code,
  ci.cross_run_code,
  coalesce(sel.birthday_ci, ci.cross_date::date) as birthday,
  sel.day_annotated,
  sel.annotations_rollup,
  x.mother_code  as mom_code,
  x.father_code  as dad_code,
  cm.label       as mother_tank_code,
  cf.label       as father_tank_code,
  cp.clutch_name,
  cp.clutch_nickname
from public.cross_instances ci
join public.crosses x on x.id = ci.cross_id
left join public.containers cm on cm.id = ci.mother_tank_id
left join public.containers cf on cf.id = ci.father_tank_id
left join public.planned_crosses pc on pc.cross_id = ci.cross_id
left join public.clutch_plans   cp on cp.id = pc.clutch_id
left join sel on sel.cross_instance_id = ci.id;

commit;
