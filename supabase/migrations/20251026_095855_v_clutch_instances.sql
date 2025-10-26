create or replace view public.v_clutch_instances as
with t as (
  select
    cit.clutch_instance_id,
    count(*)::int                                                                             as treatments_count_effective,
    string_agg(coalesce(cit.material_code,''), ' + ' order by cit.created_at desc nulls last) as treatments_pretty_effective
  from public.clutch_instance_treatments cit
  group by cit.clutch_instance_id
)
select
  ci.clutch_instance_code                         as clutch_code,
  null::date                                      as clutch_birthday,
  x.cross_run_code                                as cross_name_pretty,
  pc.name                                         as clutch_name,
  null::text                                      as clutch_genotype_pretty,
  null::text                                      as clutch_strain_pretty,
  coalesce(t.treatments_count_effective, 0)       as treatments_count_effective,
  coalesce(t.treatments_pretty_effective, '')     as treatments_pretty_effective,
  case when coalesce(t.treatments_pretty_effective,'') <> '' 
       then t.treatments_pretty_effective 
       else '' end                                 as genotype_treatment_rollup_effective,
  coalesce(x.created_by,'')                       as created_by_instance,
  ci.created_at                                   as created_at_instance
from public.clutch_instances ci
join public.cross_instances  x  on x.id = ci.cross_instance_id
join public.crosses          c  on c.id = x.cross_id
join public.planned_crosses  pc on pc.cross_id = c.id
left join t on t.clutch_instance_id = ci.id;
