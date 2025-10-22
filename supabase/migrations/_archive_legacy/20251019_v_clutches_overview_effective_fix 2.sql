begin;

create or replace view public.v_clutches_overview_effective as
with base as (
  select * from public.v_clutches_overview_final_enriched
),
ci_norm as (
  select
    ci.id,
    -- strip optional trailing "-NN" and ensure "CI-" prefix to match base.clutch_code
    case
      when ci.clutch_instance_code like 'CI-%'
        then regexp_replace(ci.clutch_instance_code, '-[0-9]{2}$', '')
      else 'CI-' || regexp_replace(ci.clutch_instance_code, '-[0-9]{2}$', '')
    end as ci_join_code
  from public.clutch_instances ci
)
select
  b.*,
  coalesce(v.treatments_count_effective, b.treatments_count_effective)::int         as treatments_count_effective_eff,
  coalesce(nullif(v.treatments_pretty_effective,''), b.treatments_pretty_effective) as treatments_pretty_effective_eff
from base b
left join ci_norm n
  on b.clutch_code = n.ci_join_code
left join public.v_clutch_instance_treatments_effective v
  on v.clutch_instance_id = n.id;

commit;
