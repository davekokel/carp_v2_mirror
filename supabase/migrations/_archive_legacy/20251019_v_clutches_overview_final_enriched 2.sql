begin;

create or replace view public.v_clutches_overview_final_enriched as
select
  base.*,
  coalesce(cit.treatments_count,  base.treatments_count)   as treatments_count_effective,
  coalesce(cit.treatments_pretty, base.treatments_pretty)  as treatments_pretty_effective,
  -- Build a rollup from genotype + effective treatments
  trim(both ' +' from
    coalesce(base.clutch_genotype_pretty, '') ||
    case
      when coalesce(cit.treatments_pretty, base.treatments_pretty) is not null
           and coalesce(cit.treatments_pretty, base.treatments_pretty) <> '' then ' + '
      else ''
    end ||
    coalesce(cit.treatments_pretty, base.treatments_pretty, '')
  ) as genotype_treatment_rollup_effective
from public.v_clutches_overview_final base
left join public.v_cit_rollup cit
  on cit.clutch_instance_code = base.clutch_code;

commit;
