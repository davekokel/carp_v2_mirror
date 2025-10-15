begin;

-- view: v_clutch_instance_selections
create or replace view public.v_clutch_instance_selections as
select
  ci.id::uuid                 as selection_id,
  ci.cross_instance_id::uuid  as cross_instance_id,
  ci.created_at               as selection_created_at,
  ci.annotated_at             as selection_annotated_at,
  ci.red_intensity,
  ci.green_intensity,
  ci.notes,
  ci.annotated_by,
  ci.label
from public.clutch_instances ci;

-- view: vw_bruker_mounts_enriched (compute mount_code label on the fly)
create or replace view public.vw_bruker_mounts_enriched as
select
  ('BRUKER '||to_char(mount_date,'YYYY-MM-DD')||' #'||
   row_number() over (
     partition by mount_date
     order by mount_time nulls last, created_at
   )
  ) as mount_code,
  selection_id, mount_date, mount_time,
  n_top, n_bottom, orientation, created_at, created_by
from public.bruker_mounts;

commit;
