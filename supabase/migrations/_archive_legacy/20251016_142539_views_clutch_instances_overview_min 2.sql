begin;
create or replace view public.v_clutch_instances_overview as
with sel as (
    select
        cl.cross_instance_id,
        max(cl.annotated_at)::date as day_annotated,
        string_agg(
            trim(concat_ws(
                ' ',
                case when coalesce(cl.red_intensity, '') <> '' then 'red=' || cl.red_intensity end,
                case when coalesce(cl.green_intensity, '') <> '' then 'green=' || cl.green_intensity end,
                case when coalesce(cl.notes, '') <> '' then 'note=' || cl.notes end
            )), ' | ' order by cl.created_at
        ) as annotations_rollup
    from public.clutch_instances AS cl
    group by cl.cross_instance_id
)

select
    cp.clutch_code,
    ci.cross_run_code,
    ci.cross_date::date as birthday,
    sel.day_annotated,
    sel.annotations_rollup,
    x.mother_code as mom_code,
    x.father_code as dad_code,
    cm.label as mother_tank_code,
    cf.label as father_tank_code
from public.cross_instances AS ci
inner join public.crosses AS x on ci.cross_id = x.id
left join public.containers AS cm on ci.mother_tank_id = cm.id
left join public.containers AS cf on ci.father_tank_id = cf.id
left join public.planned_crosses AS pc on ci.cross_id = pc.cross_id
left join public.clutch_plans AS cp on pc.clutch_id = cp.id
left join sel AS on ci.id = sel.cross_instance_id;
commit;
