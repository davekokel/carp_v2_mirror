drop view if exists public.v_bruker_mounts_enriched cascade;

create view public.v_bruker_mounts_enriched as
with m as (
  select * from public.bruker_mounts
),
ci as (
  select
    coalesce(id::text, id_uuid::text) as selection_id,
    cross_instance_id,
    coalesce(label,'')                as selection_label
  from public.clutch_instances
),
r as (
  select
    cross_instance_id,
    cross_run_code,
    mom_code,
    dad_code
  from public.vw_cross_runs_overview
),
c as (
  select
    mom_code,
    dad_code,
    name     as clutch_name,
    nickname as clutch_nickname
  from public.v_cross_concepts_overview
),
ann as (
  select
    cross_instance_id,
    string_agg(
      nullif(
        trim(
          concat_ws(' ',
            case when coalesce(red_intensity,'')   <> '' then 'red='   || red_intensity   end,
            case when coalesce(green_intensity,'') <> '' then 'green=' || green_intensity end,
            case when coalesce(notes,'')           <> '' then 'note='  || notes          end
          )
        ),
        ''
      ),
      ' | ' order by created_at
    ) as annotations_rollup
  from public.clutch_instances
  group by cross_instance_id
)
select
  coalesce(
    m.mount_code,
    'BRUKER ' || to_char(m.mount_date,'YYYY-MM-DD') || ' #' ||
    row_number() over (
      partition by m.mount_date
      order by m.mount_time nulls last, m.created_at
    )
  ) as mount_code,
  m.mount_date,
  m.mount_time,
  ci.selection_label,
  r.cross_run_code,
  c.clutch_name,
  c.clutch_nickname,
  ann.annotations_rollup,
  m.n_top,
  m.n_bottom,
  m.orientation,
  m.created_at,
  m.created_by,
  m.selection_id,
  r.cross_instance_id
from m
left join ci  on ci.selection_id     = m.selection_id::text
left join r   on r.cross_instance_id = ci.cross_instance_id
left join c   on c.mom_code = r.mom_code and c.dad_code = r.dad_code
left join ann on ann.cross_instance_id = r.cross_instance_id;
