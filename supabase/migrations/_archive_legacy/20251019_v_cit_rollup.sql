begin;

create or replace view public.v_cit_rollup as
select
  ci.clutch_instance_code,
  count(*)::int as treatments_count,
  string_agg(
    coalesce(t.material_type,'') || ':' || coalesce(t.material_code,''),
    '; ' order by t.created_at desc nulls last
  ) as treatments_pretty
from public.clutch_instance_treatments t
join public.clutch_instances ci on ci.id = t.clutch_instance_id
group by ci.clutch_instance_code;

commit;
