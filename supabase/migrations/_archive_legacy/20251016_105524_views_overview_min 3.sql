begin;

create or replace view public.v_containers_overview as
select
    c.id,
    c.container_type,
    c.label,
    c.tank_code,
    c.status,
    c.status_changed_at,
    c.created_at
from public.containers AS c;

create or replace view public.v_clutch_instances_overview as
select
    ci.id as cross_instance_id,
    ci.cross_run_code,
    ci.cross_date as birthday,
    c.clutch_code,
    cl.id as clutch_instance_id,
    cl.birthday as clutch_birthday,
    cl.created_by as clutch_created_by
from public.cross_instances AS ci
left join public.clutches AS c
    on ci.id = c.cross_instance_id
left join public.clutch_instances AS cl
    on ci.id = cl.cross_instance_id;

commit;
