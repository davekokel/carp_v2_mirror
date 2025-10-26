create or replace view public.v_clutch_treatments as
select
  cit.clutch_instance_id,
  count(*)::int                                                                             as treatments_count,
  string_agg(coalesce(cit.material_code,''), ' + ' order by cit.created_at desc nulls last) as treatments_pretty,
  max(cit.created_at)                                                                       as last_treatment_at
from public.clutch_instance_treatments cit
group by cit.clutch_instance_id;
