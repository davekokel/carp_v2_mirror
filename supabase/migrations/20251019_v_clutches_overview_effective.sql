begin;
create or replace view public.v_clutches_overview_effective as
with base as (
  select * from public.v_clutches_overview_final_enriched
)
select
  b.*,
  coalesce(v.treatments_count_effective, b.treatments_count_effective)::int as treatments_count_effective_eff,
  coalesce(nullif(v.treatments_pretty_effective,''), b.treatments_pretty_effective) as treatments_pretty_effective_eff
from base b
left join public.clutch_instances ci
  on ci.clutch_instance_code = b.clutch_code
left join public.v_clutch_instance_treatments_effective v
  on v.clutch_instance_id = ci.id;
commit;
