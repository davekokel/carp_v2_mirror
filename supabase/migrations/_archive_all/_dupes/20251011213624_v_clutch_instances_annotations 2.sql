create or replace view public.v_clutch_instances_annotations as
select
  id::uuid                     as id,
  coalesce(label,'')           as label,
  coalesce(phenotype,'')       as phenotype,
  coalesce(notes,'')           as notes,
  coalesce(red_selected,false) as red_selected,
  coalesce(red_intensity,'')   as red_intensity,
  coalesce(red_note,'')        as red_note,
  coalesce(green_selected,false) as green_selected,
  coalesce(green_intensity,'') as green_intensity,
  coalesce(green_note,'')      as green_note,
  coalesce(annotated_by,'')    as annotated_by,
  annotated_at,
  created_at
from public.clutch_instances;
