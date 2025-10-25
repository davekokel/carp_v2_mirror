begin;

create or replace view public.v_clutch_instance_treatments_effective as
with d as (
  select
    t.clutch_instance_id,
    lower(coalesce(t.material_type,'')) as mt,
    lower(coalesce(t.material_code,'')) as mc,
    max(t.created_at) as last_at
  from public.clutch_instance_treatments t
  group by t.clutch_instance_id, lower(coalesce(t.material_type,'')), lower(coalesce(t.material_code,''))
)
select
  ci.id as clutch_instance_id,
  count(d.mc)::int as treatments_count_effective,
  coalesce(string_agg(d.mc, ' + ' order by d.last_at desc), '') as treatments_pretty_effective
from public.clutch_instances ci
left join d on d.clutch_instance_id = ci.id
group by ci.id;

commit;
