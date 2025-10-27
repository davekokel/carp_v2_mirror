create or replace view public.v_clutch_instances as
with t as (
  select
    cit.clutch_instance_id                              as ci_id,
    count(*)::int                                       as treatments_count_effective,
    coalesce(string_agg(distinct cit.material_code, ' + '), '') as treatments_pretty_effective
  from public.clutch_instance_treatments cit
  group by cit.clutch_instance_id
),
base as (
  select
    coalesce(ci.clutch_instance_code, 'CI-' || substr(ci.id::text,1,8))::text as clutch_code,
    (
      coalesce(x.cross_date::date, x.created_at::date, ci.created_at::date) + interval '1 day'
    )::date                                                                    as clutch_birthday,
    coalesce(x.cross_run_code, '')::text                                       as cross_name_pretty,
    ''::text                                                                   as clutch_name,
    ''::text                                                                   as clutch_genotype_pretty,
    ''::text                                                                   as clutch_strain_pretty,
    coalesce(t.treatments_count_effective, 0)::int                             as treatments_count_effective,
    coalesce(t.treatments_pretty_effective, '')::text                          as treatments_pretty_effective,
    nullif(trim(both ' ' from coalesce(t.treatments_pretty_effective,'')), '')::text
                                                                                as genotype_treatment_rollup_effective,
    coalesce(x.created_by::text, '')::text                                     as created_by_instance,
    ci.created_at::timestamptz                                                  as created_at_instance
  from public.clutch_instances ci
  left join public.cross_instances  x  on x.id = ci.cross_instance_id
  left join t on t.ci_id = ci.id
)
select
  clutch_code,
  clutch_birthday,
  cross_name_pretty,
  clutch_name,
  clutch_genotype_pretty,
  clutch_strain_pretty,
  treatments_count_effective,
  treatments_pretty_effective,
  genotype_treatment_rollup_effective,
  created_by_instance,
  created_at_instance
from base
order by created_at_instance desc nulls last, clutch_code;
