begin;

create or replace view public.v_clutches_overview_effective as
with base as (
  select * from public.v_clutches_overview_final_enriched
),
ci_norm as (
  select
    ci.id,
    case
      when ci.clutch_instance_code like 'CI-%'
        then regexp_replace(ci.clutch_instance_code, '-[0-9]{2}$', '')
      else 'CI-' || regexp_replace(ci.clutch_instance_code, '-[0-9]{2}$', '')
    end as ci_join_code
  from public.clutch_instances ci
)
select
  b.*,
  case
    when v.treatments_count_effective > 0 then v.treatments_count_effective
    else b.treatments_count_effective
  end::int as treatments_count_effective_eff,
  case
    when v.treatments_count_effective > 0 and coalesce(v.treatments_pretty_effective,'') <> ''
      then v.treatments_pretty_effective
    else b.treatments_pretty_effective
  end as treatments_pretty_effective_eff,
  case
    when v.treatments_count_effective > 0 then
      trim(both ' +' from concat_ws(' + ', b.clutch_genotype_pretty, v.treatments_pretty_effective))
    else b.genotype_treatment_rollup_effective
  end as genotype_treatment_rollup_effective_eff
from base b
left join ci_norm n
  on b.clutch_code = n.ci_join_code
left join public.v_clutch_instance_treatments_effective v
  on v.clutch_instance_id = n.id;

commit;
