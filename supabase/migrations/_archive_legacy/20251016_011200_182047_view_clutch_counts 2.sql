begin;

-- Fast helpers (idempotent)
create index if not exists ix_planned_crosses_clutch_id on public.planned_crosses (clutch_id);
create index if not exists ix_planned_crosses_cross_id on public.planned_crosses (cross_id);
create index if not exists ix_cross_instances_cross_id on public.cross_instances (cross_id);
create index if not exists ix_clutch_instances_cross_instance_id on public.clutch_instances (cross_instance_id);

create or replace view public.v_clutch_counts as
with runs as (
    select
        cp.id as clutch_id,
        cp.clutch_code,
        COUNT(distinct ci.id) as runs_count,
        MAX(ci.cross_date) as last_run_date,
        MAX(ci.clutch_birthday) as last_birthday
    from public.clutch_plans AS cp
    left join public.planned_crosses AS pc on cp.id = pc.clutch_id
    left join public.cross_instances AS ci on pc.cross_id = ci.cross_id
    group by cp.id, cp.clutch_code
),

ann as (
    select
        cp.id as clutch_id,
        COUNT(distinct sel.id) as annotations_count,
        MAX(sel.annotated_at) as last_annotated_at
    from public.clutch_plans AS cp
    left join public.planned_crosses AS pc on cp.id = pc.clutch_id
    left join public.cross_instances AS ci on pc.cross_id = ci.cross_id
    left join public.clutch_instances AS sel on ci.id = sel.cross_instance_id
    group by cp.id
)

select
    cp.clutch_code,
    r.last_run_date,
    r.last_birthday,
    a.last_annotated_at,
    COALESCE(r.runs_count, 0) as runs_count,
    COALESCE(a.annotations_count, 0) as annotations_count
from public.clutch_plans AS cp
left join runs AS r on cp.id = r.clutch_id
left join ann AS a on cp.id = a.clutch_id;

commit;
