alter table public.clutches
add column if not exists clutch_code text;

update public.clutches cl
set clutch_code = cp.clutch_code
from public.cross_instances AS ci
inner join public.crosses AS x on ci.cross_id = x.id
left join public.planned_crosses AS pc on x.id = pc.cross_id
left join public.clutch_plans AS cp on pc.clutch_id = cp.id
where
    cl.cross_instance_id = ci.id
    and cl.clutch_code is null
    and cp.clutch_code is not null;

create unique index if not exists uq_clutches_run_code
on public.clutches (cross_instance_id, coalesce(clutch_code, ''));
